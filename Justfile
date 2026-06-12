default:
    @just --list

lint:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run ty check

test:
    uv run pytest

crawl venue year:
    uv run papers crawl {{ venue }} {{ year }}

search query:
    uv run papers search "{{ query }}"

export-parquet:
    uv run papers export

venue-years *args="":
    uv run papers venue-years {{ args }}

index:
    uv run papers index

reindex:
    uv run papers index --reindex

sync-hf:
    uv run papers sync-hf

download venue="" year="":
    uv run python scripts/download.py --venue "{{ venue }}" --year "{{ year }}"

publish:
    uv run python scripts/publish.py

clean:
    rm -rf .ruff_cache/ .pytest_cache/ .mypy_cache/ build/ dist/ *.egg-info/ .coverage htmlcov/
    find . -path ./.venv -prune -o -type d -name "__pycache__" -exec rm -rf {} +
    find . -path ./.venv -prune -o -type f -name "*.py[cod]" -exec rm -f {} +
