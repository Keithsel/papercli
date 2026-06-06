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
    supported = all_supported_venue_years()
    table_supported = Table(title="Supported Venue-Years")
    table_supported.add_column("Venue", style="cyan")
    table_supported.add_column("Year", style="magenta")
    for venue, year in supported:
        table_supported.add_row(venue, str(year))

    console.print(table_supported)
    console.print()

    table_indexed = Table(title="Indexed Venue-Years in Database")
    table_indexed.add_column("Venue", style="cyan")
    table_indexed.add_column("Year", style="magenta")
    table_indexed.add_column("Count", style="green", justify="right")

    store = Store()
    rows = store.venue_years()
    for row in rows:
        table_indexed.add_row(row["venue"], str(row["year"]), f"{row['count']:,}")

    console.print(table_indexed)


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
