import os
from collections import defaultdict

from huggingface_hub import HfApi, create_repo

import papercli.crawlers  # noqa: F401
from papercli.base import all_supported_venue_years
from papercli.db import DEFAULT_DB
from papercli.export import export_parquet, export_browse_by_venue_year

REPO_ID = os.environ.get("HF_DATASET_SLUG", "ClosedUni/papercli-papers")
PDF_DIR = DEFAULT_DB.parent / "pdfs"
PARQUET = DEFAULT_DB.parent / "papers.parquet"
BROWSE_DIR = DEFAULT_DB.parent / "browse"
HF_README_PATH = DEFAULT_DB.parent.parent / "HF_README.md"


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
        "Built with [paper-cli](https://github.com/Keithsel/paper-cli).",
    ]
    return "\n".join(lines)


def main() -> None:
    api = HfApi()
    create_repo(REPO_ID, repo_type="dataset", exist_ok=True)

    if PDF_DIR.exists() and any(PDF_DIR.rglob("*.pdf")):
        api.upload_large_folder(
            repo_id=REPO_ID,
            repo_type="dataset",
            folder_path=str(DEFAULT_DB.parent),
            allow_patterns="pdfs/**/*",
        )
        print(f"Uploaded PDFs from {PDF_DIR}")
    else:
        print("No local PDFs to upload; skipping.")

    n = export_parquet(PARQUET)
    api.upload_file(
        path_or_fileobj=str(PARQUET),
        path_in_repo="papers.parquet",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message=f"Update full index ({n} papers)",
    )
    print(f"Uploaded full parquet ({n} papers)")

    counts = export_browse_by_venue_year(BROWSE_DIR)
    api.upload_folder(
        repo_id=REPO_ID,
        repo_type="dataset",
        folder_path=str(BROWSE_DIR),
        path_in_repo="browse",
        commit_message=f"Update browse views ({sum(counts.values())} rows)",
    )
    print(f"Uploaded browse views ({len(counts)} venue-years)")

    readme_content = build_readme()
    HF_README_PATH.write_text(readme_content, encoding="utf-8")
    print(f"Saved dataset card to {HF_README_PATH}")

    api.upload_file(
        path_or_fileobj=str(HF_README_PATH),
        path_in_repo="README.md",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="Update dataset card",
    )
    print(f"Published -> https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    main()
