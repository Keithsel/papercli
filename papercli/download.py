import concurrent.futures
import json
import os
import random
import time
from urllib.parse import urlparse
from collections import defaultdict
import requests
from rich.console import Console

from papercli.db import Store, DEFAULT_DB
from papercli.pdf import reorganize_pdfs

console = Console()
PDF_DIR = DEFAULT_DB.parent / "pdfs"


def get_mullvad_proxies() -> list[str]:
    cache_path = DEFAULT_DB.parent / "mullvad_proxies.json"
    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            if time.time() - os.path.getmtime(cache_path) < 86400:
                if data:
                    return data
        except Exception:
            pass

    try:
        resp = requests.get("https://api.mullvad.net/app/v1/relays", timeout=10)
        resp.raise_for_status()
        relays = resp.json().get("wireguard", {}).get("relays", [])
        proxies = []
        for r in relays:
            if r.get("active"):
                hn = r.get("hostname")
                if hn and "-wg-" in hn:
                    p = hn.split("-wg-")
                    proxies.append(f"{p[0]}-wg-socks5-{p[1]}.relays.mullvad.net")
        if proxies:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(proxies, f)
            return proxies
    except Exception as exc:
        console.print(
            f"[yellow]Warning: Could not fetch Mullvad proxies, error: {exc}[/]"
        )

    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception:
            pass

    return []


def download_pdfs(
    venue: str | None = None,
    year: int | None = None,
    delay: float = 0.5,
    mullvad: bool = False,
) -> None:
    reorganize_pdfs(PDF_DIR)
    store = Store()
    rows = []
    if venue and "," in venue:
        for v in venue.split(","):
            rows.extend(store.pending_pdfs(v.strip(), year))
    else:
        rows = store.pending_pdfs(venue, year)

    console.print(f"{len(rows)} PDFs to fetch.")

    proxy_list = []
    if mullvad:
        proxy_list = get_mullvad_proxies()
        if not proxy_list:
            console.print(
                "[red]Error: No Mullvad proxies found or failed to fetch. Proceeding without proxies.[/]"
            )
            mullvad = False

    if mullvad:
        domain_to_rows = defaultdict(list)
        for row in rows:
            if row["pdf_url"]:
                domain = urlparse(row["pdf_url"]).netloc
                domain_to_rows[domain].append(row)

        console.print(
            f"Downloading concurrently across {len(domain_to_rows)} domain thread pools..."
        )

        def run_domain(domain, group):
            num_workers = min(len(group), (os.cpu_count() or 1) * 4)

            def worker(index_and_row):
                idx, row = index_and_row
                pid = row["id"]
                venue_lower = row["venue"].lower()
                dest = PDF_DIR / venue_lower / str(row["year"]) / pid[:2]
                dest.mkdir(parents=True, exist_ok=True)
                path = dest / f"{pid}.pdf"

                max_retries = 5
                for attempt in range(max_retries):
                    p_host = proxy_list[idx % len(proxy_list)]
                    proxies = {
                        "http": f"socks5h://{p_host}:1080",
                        "https": f"socks5h://{p_host}:1080",
                    }
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                        resp = requests.get(
                            row["pdf_url"], headers=headers, proxies=proxies, timeout=60
                        )
                        resp.raise_for_status()
                        path.write_bytes(resp.content)

                        import sqlite3

                        conn = sqlite3.connect(DEFAULT_DB, timeout=60.0)
                        with conn:
                            conn.execute(
                                "UPDATE papers SET pdf_path=? WHERE id=?",
                                (str(path), row["id"]),
                            )
                        conn.close()
                        proxy_str = f" via {p_host}"
                        console.print(f"[green]ok[/] {row['title'][:70]}{proxy_str}")
                        break
                    except Exception as exc:
                        if attempt < max_retries - 1:
                            p_host = random.choice(proxy_list)
                            continue
                        else:
                            console.print(f"[red]fail[/] {row['title'][:50]}: {exc}")

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=num_workers
            ) as executor:
                executor.map(worker, enumerate(group))

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(domain_to_rows)
        ) as parent_executor:
            futures = [
                parent_executor.submit(run_domain, domain, group)
                for domain, group in domain_to_rows.items()
            ]
            concurrent.futures.wait(futures)
    else:
        for row in rows:
            pid = row["id"]
            venue_lower = row["venue"].lower()
            dest = PDF_DIR / venue_lower / str(row["year"]) / pid[:2]
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / f"{pid}.pdf"
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                resp = requests.get(row["pdf_url"], headers=headers, timeout=60)
                resp.raise_for_status()
                path.write_bytes(resp.content)
                store.set_pdf_path(row["id"], str(path))
                console.print(f"[green]ok[/] {row['title'][:70]}")
            except Exception as exc:
                console.print(f"[red]fail[/] {row['title'][:50]}: {exc}")

            time.sleep(delay)
