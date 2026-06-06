import time
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.table import Table

import papercli.crawlers  # noqa: F401
from papercli.base import REGISTRY, get_crawler, all_supported_venue_years
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


@app.command()
def download(venue: str | None = None, year: int | None = None, delay: float = 0.5):
    store = Store()
    rows = store.pending_pdfs(venue, year)
    console.print(f"{len(rows)} PDFs to fetch.")
    for row in rows:
        dest = PDF_DIR / row["source"] / str(row["year"])
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{row['id']}.pdf"
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
def venue_years():
    supported = set(all_supported_venue_years())
    store = Store()
    db_rows = store.venue_years()

    db_stats = {
        (row["venue"], row["year"]): {
            "count": row["count"],
            "local_count": row["local_count"],
            "to_download_count": row["to_download_count"],
        }
        for row in db_rows
    }

    all_keys = sorted(supported.union(db_stats.keys()))

    table = Table(title="Venue-Years Status")
    table.add_column("Venue", style="cyan")
    table.add_column("Year", style="magenta")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Local PDFs", style="blue", justify="right")
    table.add_column("To Download", style="yellow", justify="right")
    table.add_column("Progress", style="cyan", justify="right")

    total_papers = 0
    total_local = 0
    total_to_dl = 0

    for venue, year in all_keys:
        stats = db_stats.get((venue, year))
        if stats:
            count = stats["count"]
            local = stats["local_count"]
            to_dl = stats["to_download_count"]
            total_dl = local + to_dl
            if total_dl > 0:
                pct = (local / total_dl) * 100
                progress = f"{pct:.1f}% ({local:,}/{total_dl:,})"
            else:
                progress = "-"
        else:
            count = 0
            local = 0
            to_dl = 0
            progress = "-"

        total_papers += count
        total_local += local
        total_to_dl += to_dl

        table.add_row(
            venue,
            str(year),
            f"{count:,}" if count > 0 else "0",
            f"{local:,}" if local > 0 else "0",
            f"{to_dl:,}" if to_dl > 0 else "0",
            progress,
        )

    table.add_section()
    overall_dl = total_local + total_to_dl
    if overall_dl > 0:
        pct = (total_local / overall_dl) * 100
        overall_progress = f"{pct:.1f}% ({total_local:,}/{overall_dl:,})"
    else:
        overall_progress = "-"

    table.add_row(
        "Total",
        "",
        f"{total_papers:,}",
        f"{total_local:,}",
        f"{total_to_dl:,}",
        overall_progress,
    )

    console.print(table)


@app.command()
def index():
    store = Store()
    completed = store.get_completed_crawls()
    for venue, year in all_supported_venue_years():
        if (venue, year) in completed:
            console.print(f"[yellow]Skipping already indexed {venue} {year}[/]")
            continue
        try:
            with console.status(f"Crawling {venue} {year}..."):
                total = _crawl_one(venue, year)
            console.print(f"[green]Indexed {total} papers from {venue} {year}.[/]")
        except Exception as e:
            console.print(f"[red]Error crawling {venue} {year}: {e}[/]")


if __name__ == "__main__":
    app()
