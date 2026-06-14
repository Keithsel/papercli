import sqlite3
from pathlib import Path
from rich.console import Console

from papercli.db import DEFAULT_DB

console = Console()


def reorganize_pdfs(pdf_dir: Path, db_path: Path = DEFAULT_DB) -> None:
    if not pdf_dir.exists():
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    count = 0
    for file_path in list(pdf_dir.rglob("*.pdf")):
        pid = file_path.stem
        cursor.execute("SELECT venue, year FROM papers WHERE id=?", (pid,))
        row = cursor.fetchone()
        if row:
            venue_lower = row["venue"].lower()
            year = row["year"]
            expected_dir = pdf_dir / venue_lower / str(year) / pid[:2]
            expected_path = expected_dir / f"{pid}.pdf"
            if file_path != expected_path:
                expected_dir.mkdir(parents=True, exist_ok=True)
                file_path.rename(expected_path)
                count += 1

    for d in sorted(pdf_dir.glob("**"), reverse=True):
        if d.is_dir() and d != pdf_dir:
            try:
                d.rmdir()
            except OSError:
                pass

    if count > 0:
        console.print(f"Reorganized {count} local PDFs into venue-based structure.")

    rows = cursor.execute(
        "SELECT id, venue, year, pdf_path FROM papers WHERE pdf_path IS NOT NULL"
    ).fetchall()
    updates = []
    for row in rows:
        pid = row["id"]
        venue_lower = row["venue"].lower()
        year = row["year"]
        old_path = row["pdf_path"]

        if old_path.startswith("hf://"):
            new_path = f"hf://pdfs/{venue_lower}/{year}/{pid[:2]}/{pid}.pdf"
        else:
            new_path = str(pdf_dir / venue_lower / str(year) / pid[:2] / f"{pid}.pdf")

        if old_path != new_path:
            updates.append((new_path, pid))

    if updates:
        with conn:
            conn.executemany("UPDATE papers SET pdf_path=? WHERE id=?", updates)
        console.print(f"Migrated {len(updates)} PDF paths in the database.")

    conn.close()
