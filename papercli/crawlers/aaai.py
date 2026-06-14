import re
import time
from collections.abc import Iterator

import requests
from selectolax.parser import HTMLParser

from papercli.base import Crawler, register, fetch_abstracts_for_papers
from papercli.models import Paper

BASE = "https://ojs.aaai.org"
ARCHIVE = f"{BASE}/index.php/AAAI/issue/archive"

VOLUME_MAPPING = {
    2026: 40,
    2025: 39,
    2024: 38,
    2023: 37,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_VOL_RE = re.compile(r"Vol\.?\s*(\d+)", re.IGNORECASE)


@register
class AAAICrawler(Crawler):
    name = "aaai"
    venues = ["AAAI"]

    _archive_cache: list[tuple[int, str]] | None = None

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return [("AAAI", year) for year in VOLUME_MAPPING.keys()]

    def _all_issues(self) -> list[tuple[int, str]]:
        if self._archive_cache is not None:
            return self._archive_cache

        out: list[tuple[int, str]] = []
        page = 1
        while True:
            page_url = ARCHIVE if page == 1 else f"{ARCHIVE}/{page}"
            resp = requests.get(page_url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            tree = HTMLParser(resp.text)

            found_any = False
            page_vols = []
            for summary in tree.css("div.obj_issue_summary"):
                link = summary.css_first("a.title, h2 a, h3.title a")
                series_el = summary.css_first("div.series")
                if link and series_el:
                    found_any = True
                    href = link.attributes.get("href") or ""
                    url = href if href.startswith("http") else BASE + href
                    series_text = (series_el.text() or "").strip()
                    m = _VOL_RE.search(series_text)
                    if m:
                        vol = int(m.group(1))
                        out.append((vol, url))
                        page_vols.append(vol)

            if not found_any:
                break

            if page_vols and max(page_vols) < 37:
                break

            page += 1
            time.sleep(0.5)

        self._archive_cache = out
        return out

    def _parse_issue(self, html: str, year: int) -> Iterator[Paper]:
        tree = HTMLParser(html)
        for art in tree.css("div.obj_article_summary"):
            title_el = art.css_first("h3.title a")
            if title_el is None:
                continue
            title = " ".join((title_el.text() or "").split())
            forum_url = title_el.attributes.get("href", "") or ""

            authors_el = art.css_first("div.authors")
            authors: list[str] = []
            if authors_el is not None:
                raw = (authors_el.text() or "").strip()
                authors = [a.strip() for a in raw.split(",") if a.strip()]

            pdf_el = art.css_first("a.obj_galley_link.pdf")
            pdf_url = ""
            if pdf_el is not None:
                href = pdf_el.attributes.get("href", "") or ""
                pdf_url = href if href.startswith("http") else BASE + href

            if not title or not pdf_url:
                continue

            yield Paper(
                title=title,
                authors=authors,
                abstract=None,
                venue="AAAI",
                year=year,
                track="main",
                source="aaai",
                pdf_url=pdf_url,
                forum_url=forum_url,
            )

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        target_vol = VOLUME_MAPPING.get(year)
        if target_vol is None:
            raise KeyError(
                f"No AAAI volume mapping for {venue} {year}; add it to VOLUME_MAPPING in aaai.py"
            )

        issue_urls = [url for vol, url in self._all_issues() if vol == target_vol]
        for issue_url in issue_urls:
            resp = requests.get(issue_url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            papers = list(self._parse_issue(resp.text, year))

            def parse_abs(html: str) -> str | None:
                tree = HTMLParser(html)
                for tag in [
                    "section.abstract",
                    "div.abstract",
                    "div.article-abstract",
                    "div.abstract-content",
                    ".abstract",
                ]:
                    el = tree.css_first(tag)
                    if el:
                        text = el.text(strip=True)
                        if text.startswith("Abstract"):
                            text = text[len("Abstract") :].strip()
                        return text
                return None

            fetch_abstracts_for_papers(papers, parse_abs)
            yield from papers
            time.sleep(0.5)
