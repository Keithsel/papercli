from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

import papercli.crawlers  # noqa: F401
from papercli.base import REGISTRY
from papercli.db import Store, DEFAULT_DB
from papercli.logging import setup_logging
from papercli.export import export_parquet
from papercli.crawl import crawl_venue, index_all
from papercli.download import download_pdfs
from papercli.venue_years import show_venue_years
from papercli.sync import sync_hf_dataset
from papercli.publish import publish_dataset

setup_logging()


app = typer.Typer(help="Crawl, index and search AI conference/journal papers.")
console = Console()
DEFAULT_PARQUET = DEFAULT_DB.parent / "papers.parquet"


@app.command()
def crawl(
    venue: str = typer.Argument(
        None, help="Venue to crawl (e.g. ACL). Crawls all if not specified."
    ),
    year: int = typer.Argument(
        None, help="Year to crawl (e.g. 2025). Crawls all if not specified."
    ),
    mullvad: bool = typer.Option(
        False, "--mullvad", "-m", help="Use rotating Mullvad SOCKS5 proxies"
    ),
):
    crawl_venue(venue=venue, year=year, mullvad=mullvad)


@app.command()
def download(
    venue: str | None = typer.Option(
        None,
        "--venue",
        "-v",
        help="Limit to a specific venue or comma-separated list of venues",
    ),
    year: int | None = typer.Option(
        None, "--year", "-y", help="Limit to a specific year"
    ),
    delay: float = typer.Option(
        0.5, "--delay", "-d", help="Delay between requests in seconds"
    ),
    mullvad: bool = typer.Option(
        False, "--mullvad", "-m", help="Use rotating Mullvad SOCKS5 proxies"
    ),
):
    download_pdfs(venue=venue, year=year, delay=delay, mullvad=mullvad)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    venue: str | None = typer.Option(
        None, "--venue", "-v", help="Filter search by venue"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
):
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
    show_venue_years(include=include, exclude=exclude)


@app.command(name="sync-hf")
def sync_hf():
    """Sync missing local PDF paths with those uploaded to Hugging Face."""
    sync_hf_dataset()


@app.command()
def index(
    reindex: bool = typer.Option(
        False,
        "--reindex",
        "-r",
        help="Re-crawl and reindex even if already marked completed",
    ),
    sync_hf: bool = typer.Option(
        False,
        "--sync-hf",
        "-s",
        help="Sync with HF dataset PDFs after indexing",
    ),
    mullvad: bool = typer.Option(
        False, "--mullvad", "-m", help="Use rotating Mullvad SOCKS5 proxies"
    ),
):
    index_all(reindex=reindex, sync_hf=sync_hf, mullvad=mullvad)


@app.command()
def publish(
    venue: str | None = typer.Option(
        None, "--venue", "-v", help="Specific venue to upload PDFs for"
    ),
    year: int | None = typer.Option(
        None, "--year", "-y", help="Specific year to upload PDFs for"
    ),
):
    """Publish papers and PDFs to Hugging Face."""
    publish_dataset(venue=venue, year=year)


if __name__ == "__main__":
    app()
