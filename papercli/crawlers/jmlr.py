from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register, fetch_abstracts_for_papers
from papercli.models import Paper

BASE = "https://jmlr.org"

VOLUMES = {
    ("JMLR", 2025): 26,
    ("JMLR", 2024): 25,
    ("JMLR", 2023): 24,
    ("JMLR", 2022): 23,
}


@register
class JMLRCrawler(Crawler):
    name = "jmlr"
    venues = ["JMLR"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(VOLUMES.keys())

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        vol = VOLUMES.get((venue, year))
        if vol is None:
            raise KeyError(f"Unknown JMLR volume for {venue} {year}; add it to VOLUMES")

        url = f"{BASE}/papers/v{vol}/"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()

        papers = list(self._parse(resp.text, venue, year))

        def parse_abs(html: str) -> str | None:
            tree = HTMLParser(html)
            el = tree.css_first("p.abstract")
            return el.text(strip=True) if el else None

        fetch_abstracts_for_papers(papers, parse_abs)
        yield from papers

    def _parse(self, html: str, venue: str, year: int) -> Iterator[Paper]:
        vol = VOLUMES.get((venue, year))
        fallback_url = f"{BASE}/papers/v{vol}/" if vol else BASE
        tree = HTMLParser(html)

        for dl in tree.css("dl"):
            dt = dl.css_first("dt")
            dd = dl.css_first("dd")
            if dt is None or dd is None:
                continue
            title = dt.text(strip=True)
            if not title:
                continue

            authors_node = dd.css_first("i")
            authors = (
                [a.strip() for a in authors_node.text().split(",") if a.strip()]
                if authors_node
                else []
            )

            pdf_url = ""
            abs_url = ""
            for a in dd.css("a"):
                label = a.text(strip=True)
                href = a.attributes.get("href") or ""
                if label == "pdf" and href:
                    pdf_url = href if href.startswith("http") else BASE + href
                elif label == "abs" and href:
                    abs_url = href if href.startswith("http") else BASE + href

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue=venue,
                year=year,
                track="main",
                source="jmlr",
                pdf_url=pdf_url,
                forum_url=abs_url or fallback_url,
            )
