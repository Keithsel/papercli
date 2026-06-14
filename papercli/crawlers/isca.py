from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register, fetch_abstracts_for_papers
from papercli.models import Paper

BASE = "https://www.isca-archive.org"

YEARS = {
    ("Interspeech", 2025): 2025,
    ("Interspeech", 2024): 2024,
    ("Interspeech", 2023): 2023,
}


@register
class ISCACrawler(Crawler):
    name = "isca"
    venues = ["Interspeech"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(YEARS.keys())

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        proc_year = YEARS.get((venue, year))
        if proc_year is None:
            raise KeyError(
                f"Unknown Interspeech year for {venue} {year}; add it to YEARS"
            )
        base_url = f"{BASE}/interspeech_{proc_year}/"
        resp = requests.get(base_url, timeout=120)
        resp.raise_for_status()

        papers = list(self._parse(resp.text, venue, year, base_url))

        def parse_abs(html: str) -> str | None:
            tree = HTMLParser(html)
            el = tree.css_first("#abstract")
            return el.text(strip=True) if el else None

        fetch_abstracts_for_papers(papers, parse_abs)
        yield from papers

    def _parse(
        self, html: str, venue: str, year: int, base_url: str
    ) -> Iterator[Paper]:
        tree = HTMLParser(html)
        seen: set[str] = set()

        for a in tree.css("a.w3-text"):
            href = a.attributes.get("href") or ""
            if not href.endswith("_interspeech.html"):
                continue
            stem = href[: -len(".html")]
            if stem in seen:
                continue
            seen.add(stem)

            p = a.css_first("p")
            if p is None:
                continue
            span = p.css_first("span")
            authors = (
                [x.strip() for x in span.text().split(",") if x.strip()] if span else []
            )
            full = p.text(separator="\n").strip()
            author_text = span.text().strip() if span else ""
            title = " ".join(full.replace(author_text, "").split())
            if not title:
                continue

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue=venue,
                year=year,
                track="main",
                source="isca",
                pdf_url=base_url + stem + ".pdf",
                forum_url=base_url + href,
            )
