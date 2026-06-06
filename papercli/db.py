import sqlite3
from pathlib import Path

from papercli.models import Paper

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / ".paper-cli" / "papers.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id        TEXT PRIMARY KEY,
    title     TEXT NOT NULL,
    authors   TEXT,
    abstract  TEXT,
    venue     TEXT NOT NULL,
    year      INTEGER NOT NULL,
    track     TEXT,
    source    TEXT NOT NULL,
    pdf_url   TEXT,
    forum_url TEXT,
    pdf_path  TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title, abstract, authors,
    content='papers', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, abstract, authors)
    VALUES (new.rowid, new.title, new.abstract, new.authors);
END;
CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, authors)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.authors);
END;
CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, authors)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.authors);
    INSERT INTO papers_fts(rowid, title, abstract, authors)
    VALUES (new.rowid, new.title, new.abstract, new.authors);
END;
CREATE TABLE IF NOT EXISTS completed_crawls (
    venue TEXT NOT NULL,
    year  INTEGER NOT NULL,
    PRIMARY KEY (venue, year)
);
"""


class Store:
    def __init__(self, path: Path = DEFAULT_DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO completed_crawls (venue, year) SELECT DISTINCT venue, year FROM papers"
            )

    def upsert(self, papers: list[Paper]) -> int:
        rows = [p.to_row() for p in papers]
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
        sql = (
            f"INSERT INTO papers ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        with self.conn:
            self.conn.executemany(sql, rows)
        return len(rows)

    def search(
        self, query: str, venue: str | None = None, limit: int = 20
    ) -> list[sqlite3.Row]:
        sql = (
            "SELECT p.* FROM papers_fts f JOIN papers p ON p.rowid = f.rowid "
            "WHERE papers_fts MATCH ?"
        )
        args: list = [query]
        if venue:
            sql += " AND p.venue = ?"
            args.append(venue)
        sql += " ORDER BY rank LIMIT ?"
        args.append(limit)
        return self.conn.execute(sql, args).fetchall()

    def pending_pdfs(
        self, venue: str | None = None, year: int | None = None
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM papers WHERE pdf_path IS NULL AND pdf_url != ''"
        args: list = []
        if venue:
            sql += " AND venue = ?"
            args.append(venue)
        if year:
            sql += " AND year = ?"
            args.append(year)
        return self.conn.execute(sql, args).fetchall()

    def set_pdf_path(self, paper_id: str, path: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE papers SET pdf_path=? WHERE id=?", (path, paper_id)
            )

    def venue_years(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT venue, year, COUNT(*) as count FROM papers GROUP BY venue, year ORDER BY venue, year"
        ).fetchall()

    def mark_complete(self, venue: str, year: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO completed_crawls (venue, year) VALUES (?, ?)",
                (venue, year),
            )

    def get_completed_crawls(self) -> set[tuple[str, int]]:
        rows = self.conn.execute("SELECT venue, year FROM completed_crawls").fetchall()
        return {(row["venue"], row["year"]) for row in rows}
