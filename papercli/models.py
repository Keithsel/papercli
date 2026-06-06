import hashlib
from dataclasses import dataclass, field, asdict


@dataclass
class Paper:
    title: str
    authors: list[str]
    venue: str
    year: int
    source: str
    pdf_url: str
    abstract: str | None = None
    track: str | None = None
    forum_url: str | None = None
    pdf_path: str | None = None
    id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.id:
            raw = f"{self.source}:{self.venue}:{self.year}:{self.title.strip().lower()}"
            self.id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_row(self) -> dict:
        row = asdict(self)
        row["authors"] = "; ".join(self.authors)
        return row
