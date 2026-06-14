import os
from collections import defaultdict
from huggingface_hub import HfApi, create_repo
from rich.console import Console

from papercli.db import DEFAULT_DB
from papercli.base import all_supported_venue_years, get_repo_id
from papercli.pdf import reorganize_pdfs
from papercli.export import export_parquet, export_browse_by_venue_year

console = Console()
PDF_DIR = DEFAULT_DB.parent / "pdfs"


def build_readme() -> str:
    by_venue: dict[str, list[int]] = defaultdict(list)
    for venue, year in all_supported_venue_years():
        by_venue[venue].append(year)

    lines = [
        "---",
        "license: cc-by-4.0",
        "pretty_name: AI Conference & Journal Papers",
        "configs:",
    ]
    for venue in sorted(by_venue):
        lines.append(f"  - config_name: {venue.lower()}")
        lines.append("    data_files:")
        for year in sorted(by_venue[venue], reverse=True):
            lines.append(f'      - split: "{year}"')
            lines.append(f"        path: browse/{venue.lower()}/{year}.parquet")
    lines += [
        "---",
        "",
        "# AI Conference & Journal Papers",
        "",
        "Searchable metadata for papers from top AI venues "
        "(NeurIPS, ICML, ICLR, CVPR, ICCV, WACV, ACL, EMNLP, NAACL).",
        "",
        "- `papers.parquet`: the full dataset (all fields, all venues).",
        "- Per-venue browse views: pick a venue in **Subset**, a year in **Split**.",
        "",
        "### Dataset Structure",
        "",
        "- `ClosedUni/papercli-papers` (main entrypoint): Contains the full index metadata parquet (`papers.parquet`) and the per-venue browse parquet views (`browse/`).",
        "- `ClosedUni/papercli-papers-[venue]`: Contains the sharded PDF files of that specific venue (no metadata parquet).",
        "",
        "### PDF Storage",
        "",
        "PDF files are sharded across separate datasets by venue to keep repository sizes optimal:",
        "- `ClosedUni/papercli-papers-[venue]` (e.g. `ClosedUni/papercli-papers-cvpr` for CVPR PDFs)",
        "",
        "To download a mirrored PDF:",
        "```python",
        "from huggingface_hub import hf_hub_download",
        "",
        "repo_id = f\"ClosedUni/papercli-papers-{row['venue'].lower()}\"",
        "path = hf_hub_download(",
        "    repo_id=repo_id,",
        '    filename=row["hf_pdf_path"],',
        '    repo_type="dataset",',
        ")",
        "```",
        "",
        "Built with [papercli](https://github.com/Keithsel/papercli).",
    ]
    return "\n".join(lines)


def publish_dataset(venue: str | None = None, year: int | None = None) -> None:
    repo_id = os.environ.get("HF_DATASET_SLUG", "ClosedUni/papercli-papers")
    parquet_path = DEFAULT_DB.parent / "papers.parquet"
    browse_dir = DEFAULT_DB.parent / "browse"
    hf_readme_path = DEFAULT_DB.parent.parent / "HF_README.md"

    venue_filters = [v.strip().lower() for v in venue.split(",")] if venue else []
    year_filter = year if year else None

    reorganize_pdfs(PDF_DIR, DEFAULT_DB)
    api = HfApi()
    create_repo(repo_id, repo_type="dataset", exist_ok=True)

    if PDF_DIR.exists() and any(PDF_DIR.rglob("*.pdf")):
        for venue_dir in PDF_DIR.iterdir():
            if venue_dir.is_dir():
                venue_lower = venue_dir.name
                if venue_filters and venue_lower not in venue_filters:
                    continue

                venue_repo_id = get_repo_id(venue_lower)

                if year_filter:
                    year_dir = venue_dir / str(year_filter)
                    if year_dir.exists():
                        console.print(
                            f"Uploading PDFs for venue: {venue_lower} ({year_filter}) -> {venue_repo_id}..."
                        )
                        create_repo(venue_repo_id, repo_type="dataset", exist_ok=True)
                        api.upload_large_folder(
                            repo_id=venue_repo_id,
                            repo_type="dataset",
                            folder_path=str(PDF_DIR.parent),
                            allow_patterns=f"pdfs/{venue_lower}/{year_filter}/**/*",
                        )
                else:
                    console.print(
                        f"Uploading PDFs for venue: {venue_lower} -> {venue_repo_id}..."
                    )
                    create_repo(venue_repo_id, repo_type="dataset", exist_ok=True)
                    api.upload_large_folder(
                        repo_id=venue_repo_id,
                        repo_type="dataset",
                        folder_path=str(PDF_DIR.parent),
                        allow_patterns=f"pdfs/{venue_lower}/**/*",
                    )
        console.print(f"Uploaded PDFs from {PDF_DIR}")
    else:
        console.print("No local PDFs to upload; skipping.")

    n = export_parquet(parquet_path)
    api.upload_file(
        path_or_fileobj=str(parquet_path),
        path_in_repo="papers.parquet",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Update full index ({n} papers)",
    )
    console.print(f"Uploaded full parquet ({n} papers)")

    counts = export_browse_by_venue_year(browse_dir)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(browse_dir),
        path_in_repo="browse",
        commit_message=f"Update browse views ({sum(counts.values())} rows)",
    )
    console.print(f"Uploaded browse views ({len(counts)} venue-years)")

    readme_content = build_readme()
    hf_readme_path.write_text(readme_content, encoding="utf-8")
    console.print(f"Saved dataset card to {hf_readme_path}")

    api.upload_file(
        path_or_fileobj=str(hf_readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Update dataset card",
    )
    console.print(f"Published -> https://huggingface.co/datasets/{repo_id}")
