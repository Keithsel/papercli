from collections.abc import Iterator

from papercli.base import Crawler, register
from papercli.models import Paper

EVENT_IDS = {
    ("ACL", 2025): "acl-2025",
    ("EMNLP", 2025): "emnlp-2025",
    ("NAACL", 2025): "naacl-2025",
}


@register
class ACLCrawler(Crawler):
    name = "acl"
    venues = ["ACL", "EMNLP", "NAACL"]

    @property
    def supported_venue_years(self) -> list[tuple[str, int]]:
        return list(EVENT_IDS.keys())

    def __init__(self):
        self._anthology = None

    @property
    def anthology(self):
        if self._anthology is None:
            import logging
            import warnings

            from acl_anthology import Anthology

            warnings.filterwarnings("ignore", module="acl_anthology")
            logging.getLogger("acl-anthology").setLevel(logging.ERROR)
            logging.getLogger("acl_anthology").setLevel(logging.ERROR)

            self._anthology = Anthology.from_repo()
        return self._anthology

    def _author_name(self, name_spec) -> str:
        try:
            return str(self.anthology.resolve(name_spec).name)
        except Exception:
            return str(name_spec.name)

    def fetch(self, venue: str, year: int) -> Iterator[Paper]:
        event_id = EVENT_IDS.get((venue, year))
        if event_id is None:
            raise KeyError(f"Unknown event id for {venue} {year}; add it to EVENT_IDS")

        event = self.anthology.get_event(event_id)
        for volume in event.volumes():
            track = str(volume.title) if volume.title else None
            for paper in volume.papers():
                if paper.pdf is None:
                    continue
                yield Paper(
                    title=str(paper.title),
                    authors=[self._author_name(a) for a in paper.authors],
                    abstract=str(paper.abstract) if paper.abstract else None,
                    venue=venue,
                    year=year,
                    track=track,
                    source="acl",
                    pdf_url=paper.pdf.url,
                    forum_url=f"https://aclanthology.org/{paper.full_id}/",
                )
