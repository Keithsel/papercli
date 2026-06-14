import json
from huggingface_hub import HfApi, create_repo
from huggingface_hub.errors import RepositoryNotFoundError
from rich.console import Console

from papercli.db import Store, DEFAULT_DB
from papercli.pdf import reorganize_pdfs
from papercli.base import get_repo_id

console = Console()
PDF_DIR = DEFAULT_DB.parent / "pdfs"


def _sync_hf_logic() -> None:
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


def sync_hf_dataset() -> None:
    with console.status("Syncing with Hugging Face dataset..."):
        _sync_hf_logic()
