default:
    @just --list

lint:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run ty check

test:
    uv run pytest

crawl *args="":
    uv run papers crawl {{ args }}

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

download *args="":
    uv run papers download {{ args }}

publish *args="":
    uv run papers publish {{ args }}

clean:
    rm -rf .ruff_cache/ .pytest_cache/ .mypy_cache/ build/ dist/ *.egg-info/ .coverage htmlcov/
    find . -path ./.venv -prune -o -type d -name "__pycache__" -exec rm -rf {} +
    find . -path ./.venv -prune -o -type f -name "*.py[cod]" -exec rm -f {} +
