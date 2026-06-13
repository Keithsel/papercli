import sqlite3
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import HfApi

from papercli.db import DEFAULT_DB

COLUMNS = [
    "id",
    "title",
    "authors",
    "abstract",
    "venue",
    "year",
    "track",
    "source",
    "pdf_url",
    "forum_url",
    "hf_pdf_path",
]


def export_parquet(out: Path, db_path: Path = DEFAULT_DB) -> int:
    from papercli.cli import get_repo_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    db_cols = [c for c in COLUMNS if c != "hf_pdf_path"]
    if "pdf_path" not in db_cols:
        db_cols.append("pdf_path")
    rows = conn.execute(f"SELECT {', '.join(db_cols)} FROM papers").fetchall()
    conn.close()

    api = HfApi()
    repo_remote_files = {}
    active_venues = {row["venue"].lower() for row in rows}
    for venue_lower in active_venues:
        r_id = get_repo_id(venue_lower)
        try:
            repo_remote_files[r_id] = set(
                api.list_repo_files(r_id, repo_type="dataset")
            )
        except Exception:
            repo_remote_files[r_id] = set()

    data = {}
    for col in COLUMNS:
        if col == "hf_pdf_path":
            data[col] = []
            for row in rows:
                pid = row["id"]
                venue_lower = row["venue"].lower()
                r_id = get_repo_id(venue_lower)
                expected_path = f"pdfs/{venue_lower}/{row['year']}/{pid[:2]}/{pid}.pdf"
                if row["pdf_path"]:
                    if row["pdf_path"].startswith("hf://"):
                        data[col].append(row["pdf_path"][5:])
                    else:
                        data[col].append(expected_path)
                elif expected_path in repo_remote_files[r_id]:
                    data[col].append(expected_path)
                else:
                    data[col].append(None)
        else:
            data[col] = [row[col] for row in rows]

    table = pa.table(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out)
    return len(rows)


def _snippet(text: str | None, n: int = 200) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:n] + "…" if len(text) > n else text


def export_browse_by_venue_year(
    out_dir: Path, db_path: Path = DEFAULT_DB
) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    pairs = conn.execute(
        "SELECT DISTINCT venue, year FROM papers ORDER BY venue, year"
    ).fetchall()

    counts: dict[str, int] = {}
    for venue, year in [(r["venue"], r["year"]) for r in pairs]:
        rows = conn.execute(
            "SELECT venue, year, title, abstract, forum_url, pdf_url "
            "FROM papers WHERE venue=? AND year=? ORDER BY title",
            (venue, year),
        ).fetchall()
        table = pa.table(
            {
                "venue": [r["venue"] for r in rows],
                "year": [r["year"] for r in rows],
                "title": [r["title"] for r in rows],
                "snippet": [_snippet(r["abstract"]) for r in rows],
                "url": [r["forum_url"] or r["pdf_url"] for r in rows],
            }
        )
        dest = out_dir / venue.lower() / f"{year}.parquet"
        dest.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, dest)
        counts[f"{venue}-{year}"] = len(rows)
    conn.close()
    return counts
