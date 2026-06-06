from pathlib import Path
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq

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
]


def export_parquet(out: Path, db_path: Path = DEFAULT_DB) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM papers").fetchall()
    conn.close()

    table = pa.table({col: [row[col] for row in rows] for col in COLUMNS})
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out)
    return len(rows)
