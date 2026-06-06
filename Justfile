default:
    @just --list

lint:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run ty check

crawl venue year:
    uv run papers crawl {{venue}} {{year}}

search query:
    uv run papers search "{{query}}"

export-parquet:
    uv run papers export

venue-years:
    uv run papers venue-years

index:
    uv run papers index

download venue="" year="":
    uv run python -c "import subprocess; cmd = ['uv', 'run', 'papers', 'download']; cmd += ['--venue', '{{venue}}'] if '{{venue}}' else []; cmd += ['--year', '{{year}}'] if '{{year}}' else []; subprocess.run(cmd)"

publish:
    uv run python scripts/publish.py

clean:
    rm -rf .ruff_cache/ .pytest_cache/ .mypy_cache/ build/ dist/ *.egg-info/ .coverage htmlcov/
    find . -path ./.venv -prune -o -type d -name "__pycache__" -exec rm -rf {} +
    find . -path ./.venv -prune -o -type f -name "*.py[cod]" -exec rm -f {} +

