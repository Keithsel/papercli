from huggingface_hub import HfApi, create_repo

from papercli.db import DEFAULT_DB
from papercli.export import export_parquet

REPO_ID = "Keithsel/papercli-papers"
OUT = DEFAULT_DB.parent / "papers.parquet"


def main():
    n = export_parquet(OUT)
    api = HfApi()
    create_repo(REPO_ID, repo_type="dataset", exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(OUT),
        path_in_repo="papers.parquet",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message=f"Update index ({n} papers)",
    )
    print(f"Published {n} papers -> {REPO_ID}")


if __name__ == "__main__":
    main()
