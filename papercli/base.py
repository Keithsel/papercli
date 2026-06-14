from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TypeVar

from papercli.models import Paper

REGISTRY: dict[str, "Crawler"] = {}


class Crawler(ABC):
    name: str
    venues: list[str]

    @abstractmethod
    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        pass

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return []

    @property
    def base_url(self) -> str:
        cname = self.name.lower()
        mapping = {
            "aaai": "https://ojs.aaai.org",
            "acl": "https://aclanthology.org",
            "cvf": "https://openaccess.thecvf.com",
            "ecva": "https://www.ecva.net",
            "ijcai": "https://www.ijcai.org",
            "isca": "https://www.isca-archive.org",
            "jmlr": "https://jmlr.org",
            "openreview": "https://openreview.net",
        }
        return mapping.get(cname, "")


T = TypeVar("T", bound="Crawler")


def register(cls: type[T]) -> type[T]:
    inst = cls()
    for v in inst.venues:
        REGISTRY[v.lower()] = inst
    return cls


def get_crawler(venue: str) -> Crawler:
    crawler = REGISTRY.get(venue.lower())
    if crawler is None:
        raise KeyError(f"No crawler for venue {venue!r}. Known: {sorted(REGISTRY)}")
    return crawler


def _venue_year_key(vy: tuple[str, int]) -> tuple[str, str, int]:
    venue, year = vy
    try:
        crawler = get_crawler(venue)
        cname = crawler.name.lower()
    except KeyError:
        cname = venue.lower()
    return (cname, venue.lower(), year)


def all_supported_venue_years() -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    seen: set[int] = set()
    for crawler in REGISTRY.values():
        if id(crawler) not in seen:
            seen.add(id(crawler))
            out.extend(crawler.supported_venue_years)
    return sorted(out, key=_venue_year_key)


def get_repo_id(venue_lower: str) -> str:
    import os

    env_key = f"HF_DATASET_SLUG_{venue_lower.upper().replace('-', '_')}"
    if env_key in os.environ:
        return os.environ[env_key]
    base_slug = os.environ.get("HF_DATASET_SLUG", "GenAI4ELab/papercli-papers")
    return f"{base_slug}-{venue_lower}"


def fetch_abstracts_for_papers(
    papers: list[Paper], parse_callback, max_workers: int = 16
) -> None:
    import os
    from concurrent.futures import ThreadPoolExecutor
    import requests

    has_proxy = bool(os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"))

    def fetch_one(paper: Paper) -> None:
        if not paper.forum_url:
            return
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            }
            resp = requests.get(paper.forum_url, headers=headers, timeout=60)
            resp.raise_for_status()
            abstract = parse_callback(resp.text)
            if abstract:
                paper.abstract = abstract.strip()
        except Exception as e:
            from papercli.logging import logger

            logger.debug(
                f"Failed to fetch abstract for '{paper.title}' from {paper.forum_url}: {e}",
                exc_info=True,
            )

    if has_proxy:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(fetch_one, papers)
    else:
        for paper in papers:
            fetch_one(paper)
