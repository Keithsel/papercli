from abc import ABC, abstractmethod
from collections.abc import Iterator

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


def register(cls: type[Crawler]) -> type[Crawler]:
    inst = cls()
    for v in inst.venues:
        REGISTRY[v.lower()] = inst
    return cls


def get_crawler(venue: str) -> Crawler:
    crawler = REGISTRY.get(venue.lower())
    if crawler is None:
        raise KeyError(f"No crawler for venue {venue!r}. Known: {sorted(REGISTRY)}")
    return crawler


def all_supported_venue_years() -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    seen: set[int] = set()
    for crawler in REGISTRY.values():
        if id(crawler) not in seen:
            seen.add(id(crawler))
            out.extend(crawler.supported_venue_years)
    return sorted(out, key=lambda vy: (vy[0].lower(), vy[1]))
