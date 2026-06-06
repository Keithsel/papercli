from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register
from papercli.models import Paper

BASE = "https://openaccess.thecvf.com"

LISTING = {
    ("CVPR", 2025): f"{BASE}/CVPR2025?day=all",
    ("CVPR", 2024): f"{BASE}/CVPR2024?day=all",
    ("ICCV", 2025): f"{BASE}/ICCV2025?day=all",
    ("ICCV", 2023): f"{BASE}/ICCV2023?day=all",
    ("WACV", 2025): f"{BASE}/WACV2025",
    ("WACV", 2024): f"{BASE}/WACV2024",
}


@register
class CVFCrawler(Crawler):
    name = "cvf"
    venues = ["CVPR", "ICCV", "WACV"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(LISTING.keys())

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        url = LISTING.get((venue, year))
        if url is None:
            raise KeyError(f"No CVF listing URL for {venue} {year}; add it to LISTING")

        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        for dt in tree.css("dt.ptitle"):
            title_a = dt.css_first("a")
            if title_a is None:
                continue
            title = title_a.text(strip=True)
            if not title:
                continue
            forum_url = BASE + (title_a.attributes.get("href") or "")

            authors: list[str] = []
            pdf_url = ""
            node = dt.next
            while node is not None and node.tag != "dt":
                if node.tag == "dd":
                    for inp in node.css('input[name="query_author"]'):
                        value = inp.attributes.get("value")
                        if value:
                            authors.append(value)
                    for a in node.css("a"):
                        if a.text(strip=True) == "pdf":
                            href = a.attributes.get("href") or ""
                            if href:
                                pdf_url = BASE + href
                node = node.next

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue=venue,
                year=year,
                track="main",
                source="cvf",
                pdf_url=pdf_url,
                forum_url=forum_url,
            )
