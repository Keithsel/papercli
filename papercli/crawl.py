import os
import random
import subprocess
import typer
from rich.console import Console

from papercli.base import get_crawler, all_supported_venue_years
from papercli.db import Store
from papercli.download import get_mullvad_proxies

console = Console()


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


def crawl_venue(
    venue: str | None = None,
    year: int | None = None,
    parallel: bool = False,
    mullvad: bool = False,
) -> None:
    targets = []
    for v, y in all_supported_venue_years():
        if venue and v.lower() != venue.lower():
            continue
        if year and y != year:
            continue
        targets.append((v, y))

    if not targets:
        console.print(
            "[red]Error: No supported venue-years found matching the criteria.[/]"
        )
        raise typer.Exit(code=1)

    if parallel:
        console.print(f"Starting parallel crawling of {len(targets)} venue-years...")
        processes = []
        for v, y in targets:
            cmd = ["uv", "run", "papers", "crawl", v, str(y)]
            if mullvad:
                cmd.append("--mullvad")
            proc = subprocess.Popen(cmd)
            processes.append((f"{v} {y}", proc))

        failed = []
        for label, proc in processes:
            exit_code = proc.wait()
            if exit_code != 0:
                console.print(f"[red]Failed:[/] {label} (exit code {exit_code})")
                failed.append(label)
            else:
                console.print(f"[green]Completed:[/] {label}")
        if failed:
            raise typer.Exit(code=1)
    else:
        for v, y in targets:
            if mullvad:
                proxy_list = get_mullvad_proxies()
                if proxy_list:
                    p_host = random.choice(proxy_list)
                    proxy_url = f"socks5h://{p_host}:1080"
                    os.environ["HTTP_PROXY"] = proxy_url
                    os.environ["HTTPS_PROXY"] = proxy_url
                    console.print(f"[green]Proxy routing active via {p_host}[/]")
            with console.status(f"Crawling {v} {y}..."):
                total = _crawl_one(v, y)
            console.print(f"[green]Indexed {total} papers from {v} {y}.[/]")


def index_all(
    reindex: bool = False,
    sync_hf: bool = False,
    parallel: bool = False,
    mullvad: bool = False,
) -> None:
    from papercli.sync import _sync_hf_logic

    store = Store()
    completed = store.get_completed_crawls()

    targets = []
    for venue, year in all_supported_venue_years():
        if (venue, year) in completed and not reindex:
            console.print(f"[yellow]Skipping already indexed {venue} {year}[/]")
            continue
        targets.append((venue, year))

    if not targets:
        console.print("[yellow]All supported venue-years are already indexed.[/]")
    else:
        if parallel:
            console.print(
                f"Starting parallel indexing of {len(targets)} venue-years..."
            )
            processes = []
            for v, y in targets:
                cmd = ["uv", "run", "papers", "crawl", v, str(y)]
                if mullvad:
                    cmd.append("--mullvad")
                proc = subprocess.Popen(cmd)
                processes.append((f"{v} {y}", proc))

            failed = []
            for label, proc in processes:
                exit_code = proc.wait()
                if exit_code != 0:
                    console.print(f"[red]Failed:[/] {label} (exit code {exit_code})")
                    failed.append(label)
                else:
                    console.print(f"[green]Completed:[/] {label}")
            if failed:
                raise typer.Exit(code=1)
        else:
            for v, y in targets:
                if mullvad:
                    proxy_list = get_mullvad_proxies()
                    if proxy_list:
                        p_host = random.choice(proxy_list)
                        proxy_url = f"socks5h://{p_host}:1080"
                        os.environ["HTTP_PROXY"] = proxy_url
                        os.environ["HTTPS_PROXY"] = proxy_url
                        console.print(f"[green]Proxy routing active via {p_host}[/]")
                try:
                    with console.status(f"Crawling {v} {y}..."):
                        total = _crawl_one(v, y)
                    console.print(f"[green]Indexed {total} papers from {v} {y}.[/]")
                except Exception as e:
                    console.print(f"[red]Error crawling {v} {y}: {e}[/]")

    if sync_hf:
        with console.status("Syncing with Hugging Face dataset..."):
            _sync_hf_logic()
