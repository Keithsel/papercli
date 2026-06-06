from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register
from papercli.models import Paper

BASE = "https://www.ijcai.org"

YEARS = {
    ("IJCAI", 2025): 2025,
    ("IJCAI", 2024): 2024,
    ("IJCAI", 2023): 2023,
}


@register
class IJCAICrawler(Crawler):
    name = "ijcai"
    venues = ["IJCAI"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(YEARS.keys())

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        proc_year = YEARS.get((venue, year))
        if proc_year is None:
            raise KeyError(f"Unknown IJCAI year for {venue} {year}; add it to YEARS")

        base_url = f"{BASE}/proceedings/{proc_year}/"
        resp = requests.get(base_url, timeout=120)
        resp.raise_for_status()
        yield from self._parse(resp.text, venue, year)

    def _parse(self, html: str, venue: str, year: int) -> Iterator[Paper]:
        proc_year = YEARS.get((venue, year))
        base_url = f"{BASE}/proceedings/{proc_year}/" if proc_year else BASE
        tree = HTMLParser(html)

        for wrapper in tree.css("div.paper_wrapper"):
            title_node = wrapper.css_first("div.title")
            if title_node is None:
                continue
            title = title_node.text(strip=True)
            if not title:
                continue

            authors_node = wrapper.css_first("div.authors")
            authors = (
                [a.strip() for a in authors_node.text().split(",") if a.strip()]
                if authors_node
                else []
            )

            pdf_url = ""
            details_url = ""
            details = wrapper.css_first("div.details")
            if details is not None:
                for a in details.css("a"):
                    label = a.text(strip=True).lower()
                    href = a.attributes.get("href") or ""
                    if not href:
                        continue
                    full = (
                        href
                        if href.startswith("http")
                        else (BASE + href if href.startswith("/") else base_url + href)
                    )
                    if label == "pdf" or href.lower().endswith(".pdf"):
                        pdf_url = full
                    elif label == "details":
                        details_url = full

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue=venue,
                year=year,
                track="main",
                source="ijcai",
                pdf_url=pdf_url,
                forum_url=details_url or base_url,
            )
