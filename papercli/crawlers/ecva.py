import re
from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register, fetch_abstracts_for_papers
from papercli.models import Paper

BASE = "https://www.ecva.net"
URL = f"{BASE}/papers.php"

YEARS = {
    ("ECCV", 2024): "ECCV 2024 Papers",
    ("ECCV", 2022): "ECCV 2022 Papers",
    ("ECCV", 2020): "ECCV 2020 Papers",
}


@register
class ECVACrawler(Crawler):
    name = "ecva"
    venues = ["ECCV"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(YEARS.keys())

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        section = YEARS.get((venue, year))
        if section is None:
            raise KeyError(f"Unknown ECCV section for {venue} {year}; add it to YEARS")
        resp = requests.get(URL, timeout=180)
        resp.raise_for_status()

        papers = list(self._parse(resp.text, venue, year, section))

        def parse_abs(html: str) -> str | None:
            tree = HTMLParser(html)
            el = tree.css_first("#abstract")
            return el.text(strip=True) if el else None

        fetch_abstracts_for_papers(papers, parse_abs)
        yield from papers

    def _parse(self, html: str, venue: str, year: int, section: str) -> Iterator[Paper]:
        tree = HTMLParser(html)

        content = None
        for button in tree.css("button.accordion"):
            if button.text(strip=True) == section:
                node = button.next
                while node is not None:
                    cls = node.attributes.get("class") or ""
                    if "accordion-content" in cls:
                        content = node
                        break
                    node = node.next
                break
        if content is None:
            return

        for dt in content.css("dt.ptitle"):
            title_a = dt.css_first("a")
            if title_a is None:
                continue
            title = " ".join(title_a.text().split())
            if not title:
                continue
            href = (title_a.attributes.get("href") or "").lstrip("/")
            forum_url = f"{BASE}/{href}" if href else URL

            authors: list[str] = []
            pdf_url = ""
            node = dt.next
            while node is not None and node.tag != "dt":
                if node.tag == "dd":
                    links = node.css("a")
                    if not links and node.text(strip=True):
                        authors = [
                            re.sub(r"\*+$", "", a.strip())
                            for a in node.text().split(",")
                            if a.strip()
                        ]
                    for a in links:
                        if a.text(strip=True) == "pdf":
                            ph = (a.attributes.get("href") or "").lstrip("/")
                            if ph:
                                pdf_url = f"{BASE}/{ph}"
                node = node.next

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue=venue,
                year=year,
                track="main",
                source="ecva",
                pdf_url=pdf_url,
                forum_url=forum_url,
            )
