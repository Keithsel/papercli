import json
from collections import defaultdict
from rich.console import Console
from rich.table import Table

from papercli.db import DEFAULT_DB, Store
from papercli.base import all_supported_venue_years, get_crawler, _venue_year_key

console = Console()


def show_venue_years(include: str | None = None, exclude: str | None = None) -> None:
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
