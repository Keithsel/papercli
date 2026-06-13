import time
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.table import Table

import papercli.crawlers  # noqa: F401
from papercli.base import (
    REGISTRY,
    get_crawler,
    all_supported_venue_years,
    _venue_year_key,
)
from papercli.db import Store, DEFAULT_DB
from papercli.export import export_parquet

app = typer.Typer(help="Crawl, index and search AI conference/journal papers.")
console = Console()
PDF_DIR = DEFAULT_DB.parent / "pdfs"
DEFAULT_PARQUET = DEFAULT_DB.parent / "papers.parquet"


def _crawl_one(venue: str, year: int) -> int:
    store = Store()
    crawler = get_crawler(venue)
    batch: list = []
    total = 0
    for paper in crawler.fetch(venue, year):
        batch.append(paper)
        if len(batch) >= 500:
            total += store.upsert(batch)
            batch = []
    total += store.upsert(batch)
    store.mark_complete(venue, year)
    return total


@app.command()
def crawl(venue: str, year: int):
    with console.status(f"Crawling {venue} {year}..."):
        total = _crawl_one(venue, year)
    console.print(f"[green]Indexed {total} papers from {venue} {year}.[/]")


def get_repo_id(venue_lower: str) -> str:
    import os

    env_key = f"HF_DATASET_SLUG_{venue_lower.upper().replace('-', '_')}"
    if env_key in os.environ:
        return os.environ[env_key]
    base_slug = os.environ.get("HF_DATASET_SLUG", "ClosedUni/papercli-papers")
    return f"{base_slug}-{venue_lower}"


def reorganize_pdfs(pdf_dir: Path, db_path: Path = DEFAULT_DB) -> None:
    if not pdf_dir.exists():
        return

    import sqlite3

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


@app.command()
def download(venue: str | None = None, year: int | None = None, delay: float = 0.5):
    reorganize_pdfs(PDF_DIR)
    store = Store()
    rows = store.pending_pdfs(venue, year)
    console.print(f"{len(rows)} PDFs to fetch.")
    for row in rows:
        pid = row["id"]
        venue_lower = row["venue"].lower()
        dest = PDF_DIR / venue_lower / str(row["year"]) / pid[:2]
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{pid}.pdf"
        try:
            resp = requests.get(row["pdf_url"], timeout=60)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            store.set_pdf_path(row["id"], str(path))
            console.print(f"[green]ok[/] {row['title'][:70]}")
        except Exception as exc:
            console.print(f"[red]fail[/] {row['title'][:50]}: {exc}")
        time.sleep(delay)


@app.command()
def search(query: str, venue: str | None = None, limit: int = 20):
    store = Store()
    rows = store.search(query, venue=venue, limit=limit)
    table = Table()
    for col in ("Venue", "Year", "Title", "PDF"):
        table.add_column(col)
    for row in rows:
        if row["pdf_path"]:
            if row["pdf_path"].startswith("hf://"):
                pdf = "hf"
            else:
                pdf = "local"
        elif row["pdf_url"]:
            pdf = "url"
        else:
            pdf = "-"
        table.add_row(row["venue"], str(row["year"]), row["title"][:80], pdf)
    console.print(table)


@app.command()
def export(out: str = str(DEFAULT_PARQUET)):
    n = export_parquet(Path(out))
    console.print(f"[green]Exported {n} papers -> {out}[/]")


@app.command()
def venues():
    console.print(sorted(REGISTRY.keys()))


@app.command(name="venue-years")
def venue_years(
    include: str | None = typer.Option(
        None, "--include", "-i", help="Comma-separated list of venues/years to include"
    ),
    exclude: str | None = typer.Option(
        None, "--exclude", "-e", help="Comma-separated list of venues/years to exclude"
    ),
):
    import json
    from collections import defaultdict

    hf_ids = set()
    for cache_file in DEFAULT_DB.parent.glob("hf_cache_*.json"):
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
            for file_path in cached_data.get("files", []):
                if file_path.startswith("pdfs/") and file_path.endswith(".pdf"):
                    parts = file_path.split("/")
                    if parts:
                        hf_ids.add(parts[-1][:-4])
        except Exception:
            pass

    supported = set(all_supported_venue_years())
    store = Store()
    conn = store.conn
    cursor = conn.cursor()
    db_rows = cursor.execute(
        "SELECT id, venue, year, pdf_path, pdf_url FROM papers"
    ).fetchall()

    db_stats = defaultdict(lambda: {"count": 0, "local": 0, "hf": 0, "to_dl": 0})
    for row in db_rows:
        pid = row["id"]
        venue = row["venue"]
        year = row["year"]
        path = row["pdf_path"]
        url = row["pdf_url"]

        is_local = bool(path and not path.startswith("hf://"))
        is_hf = bool(pid in hf_ids or (path and path.startswith("hf://")))
        has_pdf = is_local or is_hf
        needs_dl = not has_pdf and bool(url)

        stats = db_stats[(venue, year)]
        stats["count"] += 1
        if is_local:
            stats["local"] += 1
        if is_hf:
            stats["hf"] += 1
        if needs_dl:
            stats["to_dl"] += 1

    all_keys = sorted(supported.union(db_stats.keys()), key=_venue_year_key)

    def matches_any(venue: str, year: int, terms: list[str]) -> bool:
        target = f"{venue} {year}".lower().replace("-", " ").replace("_", " ")
        for term in terms:
            normalized_term = term.lower().replace("-", " ").replace("_", " ")
            if normalized_term in target:
                return True
        return False

    if include:
        include_terms = [t.strip() for t in include.split(",") if t.strip()]
        if include_terms:
            all_keys = [(v, y) for v, y in all_keys if matches_any(v, y, include_terms)]

    if exclude:
        exclude_terms = [t.strip() for t in exclude.split(",") if t.strip()]
        if exclude_terms:
            all_keys = [
                (v, y) for v, y in all_keys if not matches_any(v, y, exclude_terms)
            ]

    table = Table(title="Venue-Years Status")
    table.add_column("Crawler / Base", style="green")
    table.add_column("Venue", style="cyan")
    table.add_column("Year", style="magenta")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Local PDFs", style="blue", justify="right")
    table.add_column("HF PDFs", style="cyan", justify="right")
    table.add_column("Diff (L-H)", style="yellow", justify="right")
    table.add_column("To Download", style="yellow", justify="right")
    table.add_column("Progress", style="magenta", justify="right")

    total_papers = 0
    total_local = 0
    total_hf = 0
    total_to_dl = 0
    last_crawler_base = None

    for venue, year in all_keys:
        try:
            crawler = get_crawler(venue)
            cname = crawler.name
            base = crawler.base_url.replace("https://", "").replace("www.", "")
            crawler_base = f"{cname} ({base})"
        except Exception:
            crawler_base = "-"

        display_crawler_base = crawler_base
        if crawler_base == last_crawler_base:
            display_crawler_base = ""
        else:
            last_crawler_base = crawler_base

        stats = db_stats.get((venue, year))
        if stats:
            count = stats["count"]
            local = stats["local"]
            hf = stats["hf"]
            to_dl = stats["to_dl"]
            available = count - to_dl
            if count > 0:
                pct = (available / count) * 100
                progress = f"{pct:.1f}% ({available:,}/{count:,})"
            else:
                progress = "-"
        else:
            count = 0
            local = 0
            hf = 0
            to_dl = 0
            progress = "-"

        total_papers += count
        total_local += local
        total_hf += hf
        total_to_dl += to_dl

        diff = local - hf
        if diff > 0:
            diff_str = f"[green]+{diff:,}[/]"
        elif diff < 0:
            diff_str = f"[red]{diff:,}[/]"
        else:
            diff_str = "[white]0[/]"

        table.add_row(
            display_crawler_base,
            venue,
            str(year),
            f"{count:,}" if count > 0 else "0",
            f"{local:,}" if local > 0 else "0",
            f"{hf:,}" if hf > 0 else "0",
            diff_str,
            f"{to_dl:,}" if to_dl > 0 else "0",
            progress,
        )

    table.add_section()
    total_available = total_papers - total_to_dl
    if total_papers > 0:
        pct = (total_available / total_papers) * 100
        overall_progress = f"{pct:.1f}% ({total_available:,}/{total_papers:,})"
    else:
        overall_progress = "-"

    total_diff = total_local - total_hf
    if total_diff > 0:
        total_diff_str = f"[green]+{total_diff:,}[/]"
    elif total_diff < 0:
        total_diff_str = f"[red]{total_diff:,}[/]"
    else:
        total_diff_str = "[white]0[/]"

    table.add_row(
        "Total",
        "",
        "",
        f"{total_papers:,}",
        f"{total_local:,}",
        f"{total_hf:,}",
        total_diff_str,
        f"{total_to_dl:,}",
        overall_progress,
    )

    console.print(table)


def _sync_hf_logic():
    import json
    from huggingface_hub import HfApi, create_repo
    from huggingface_hub.errors import RepositoryNotFoundError

    reorganize_pdfs(PDF_DIR)

    legacy_cache = DEFAULT_DB.parent / "hf_cache.json"
    if legacy_cache.exists():
        try:
            legacy_cache.unlink()
        except Exception:
            pass

    store = Store()
    conn = store.conn
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, pdf_path, venue, year FROM papers").fetchall()

    venues = sorted(list({row["venue"] for row in rows}))

    api = HfApi()
    hf_pdfs = {}

    for venue in venues:
        venue_lower = venue.lower()
        repo_id = get_repo_id(venue_lower)

        cache_file = DEFAULT_DB.parent / f"hf_cache_{venue_lower}.json"
        sha = None
        remote_files = []

        try:
            repo_info = api.repo_info(repo_id, repo_type="dataset")
            sha = repo_info.sha
        except RepositoryNotFoundError:
            console.print(f"[yellow]Repository {repo_id} not found. Creating it...[/]")
            try:
                create_repo(repo_id, repo_type="dataset", exist_ok=True)
                repo_info = api.repo_info(repo_id, repo_type="dataset")
                sha = repo_info.sha
            except Exception as create_err:
                console.print(
                    f"[red]Could not create HF repository {repo_id}: {create_err}. Skipping sync for this venue.[/]"
                )
                continue
        except Exception as e:
            console.print(
                f"[yellow]Could not fetch HF repo info for {repo_id}: {e}. Falling back to listing directly.[/]"
            )

        if sha and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                if (
                    cached_data.get("repo_id") == repo_id
                    and cached_data.get("sha") == sha
                ):
                    remote_files = cached_data.get("files", [])
            except Exception:
                pass

        if not remote_files:
            console.print(f"Fetching remote file list from HF repository: {repo_id}...")
            try:
                remote_files = api.list_repo_files(repo_id, repo_type="dataset")
                if sha:
                    with open(cache_file, "w") as f:
                        json.dump(
                            {"repo_id": repo_id, "sha": sha, "files": remote_files}, f
                        )
            except Exception as e:
                console.print(f"[red]Error fetching from HF for {repo_id}: {e}[/]")
                continue

        for f in remote_files:
            if f.startswith("pdfs/") and f.endswith(".pdf"):
                parts = f.split("/")
                if len(parts) == 5:
                    paper_id = parts[4][:-4]
                    hf_pdfs[paper_id] = f

    updates = []
    for row in rows:
        pid = row["id"]
        path = row["pdf_path"]
        venue_lower = row["venue"].lower()
        year = row["year"]

        expected_local = (
            DEFAULT_DB.parent
            / "pdfs"
            / venue_lower
            / str(year)
            / pid[:2]
            / f"{pid}.pdf"
        )
        if expected_local.exists():
            local_path_str = str(expected_local)
            if path != local_path_str:
                updates.append((local_path_str, pid))
        else:
            if pid in hf_pdfs:
                hf_path = f"hf://{hf_pdfs[pid]}"
                if path != hf_path:
                    updates.append((hf_path, pid))
            elif path:
                updates.append((None, pid))

    if updates:
        console.print(f"Updating {len(updates)} papers with corrected PDF paths...")
        with conn:
            conn.executemany("UPDATE papers SET pdf_path=? WHERE id=?", updates)
        console.print("[green]Sync complete.[/]")
    else:
        console.print("[green]All PDF paths are already up to date.[/]")


@app.command(name="sync-hf")
def sync_hf():
    """Sync missing local PDF paths with those uploaded to Hugging Face."""
    with console.status("Syncing with Hugging Face dataset..."):
        _sync_hf_logic()


@app.command()
def index(
    reindex: bool = typer.Option(
        False, "--reindex", help="Re-crawl and reindex even if already marked completed"
    ),
    sync_hf: bool = typer.Option(
        False, "--sync-hf", help="Sync with HF dataset PDFs after indexing"
    ),
):
    store = Store()
    completed = store.get_completed_crawls()
    for venue, year in all_supported_venue_years():
        if (venue, year) in completed and not reindex:
            console.print(f"[yellow]Skipping already indexed {venue} {year}[/]")
            continue
        try:
            with console.status(f"Crawling {venue} {year}..."):
                total = _crawl_one(venue, year)
            console.print(f"[green]Indexed {total} papers from {venue} {year}.[/]")
        except Exception as e:
            console.print(f"[red]Error crawling {venue} {year}: {e}[/]")

    if sync_hf:
        with console.status("Syncing with Hugging Face dataset..."):
            _sync_hf_logic()


if __name__ == "__main__":
    app()
