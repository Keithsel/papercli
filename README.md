# papercli

A command-line tool to crawl, index, download, and search AI conference and journal papers.

## Features

- Fetch metadata from top-tier AI venues (ACL, EMNLP, NAACL, CVPR, ICCV, WACV, NeurIPS, ICML, ICLR), curated from the [Cannot-Miss-AI-Conferences-Journals](https://github.com/christian-hoang-04/Cannot-Miss-AI-Conferences-Journals) registry.
- Local SQLite database storage with FTS5 virtual tables for rapid text search.
- Retrieve and store PDFs locally.
- Export indexed papers to Parquet format.

## Setup

Requires Python 3.12+.

1. Clone the repository.
2. Install dependencies and set up the virtual environment:

   **Using `uv` (Recommended):**
   ```bash
   uv sync
   ```

   **Using standard Python and `pip`:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

## Usage

Commands can be run via `uv run papers <command>` or using the helper shortcuts defined in the `Justfile`.

### Supported Venues

The CLI crawls and indexes key publications from the [Cannot-Miss-AI-Conferences-Journals](https://github.com/christian-hoang-04/Cannot-Miss-AI-Conferences-Journals) list:

- ACL Anthology: `ACL`, `EMNLP`, `NAACL`
- CVF: `CVPR`, `ICCV`, `WACV`
- OpenReview: `NeurIPS`, `ICML`, `ICLR`

List registered venues programmatically:
```bash
uv run papers venues
```

View supported venue-years vs. indexed counts:
```bash
uv run papers venue-years
# or
just venue-years
```

### Crawling & Indexing

Crawl a specific venue and year:
```bash
uv run papers crawl <venue> <year>
# Example:
uv run papers crawl ACL 2025
# or
just crawl ACL 2025
```

Crawl and index all supported venue-years:
```bash
uv run papers index
# or
just index
```

*Metadata is stored in SQLite at `.paper-cli/papers.db` in the project root.*

### Searching Papers

Search the database (queries title, abstract, and authors):
```bash
uv run papers search "<query>"
# Example:
uv run papers search "attention mechanism"
# or
just search "attention mechanism"
```

Options:
- `--venue <venue>`: Filter search by venue.
- `--limit <int>`: Maximum results to display (default: 20).

### Downloading PDFs

Retrieve PDF files for crawled papers to `.paper-cli/pdfs/` in the project root:
```bash
uv run papers download [--venue <venue>] [--year <year>] [--delay <seconds>]
# Example:
just download venue="ACL" year="2025"
```

### Exporting Metadata

Export crawled papers to a Parquet file (default: `.paper-cli/papers.parquet` in the project root):
```bash
uv run papers export [out-path]
# or
just export-parquet
```

### Resolving PDFs

Each row has `pdf_url` (the original source link, always present) and
`hf_pdf_path` (a path within this dataset, present only for mirrored papers).

To fetch a mirrored PDF:

```python
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="Keithsel/papercli-papers",
    filename=row["hf_pdf_path"],   # e.g. "pdfs/acl/2025/42cbbfdf08e170c9.pdf"
    repo_type="dataset",
)
```

If `hf_pdf_path` is null, the PDF isn't mirrored — use `pdf_url` instead.

### Publishing

Publish the local index and downloaded PDFs to the [`Keithsel/papercli-papers`](https://huggingface.co/datasets/Keithsel/papercli-papers) dataset repository:

1. **Authenticate once** (saves token locally):
   ```bash
   # If using uv:
   uv run huggingface-cli login
   
   # If using standard Python:
   huggingface-cli login
   ```
   *Alternatively, set the `HF_TOKEN` environment variable.*

2. **Ensure the desired venue-years are indexed**:
   ```bash
   # If using uv/just:
   just index            # or: just crawl NeurIPS 2025
   
   # If using standard Python:
   papers index
   ```

3. **Export and Upload**:
   ```bash
   # If using uv/just:
   just publish
   
   # If using standard Python:
   python scripts/publish.py
   ```
   This will export the local index to Parquet format, generate per-venue-year browse Parquet files, and upload them alongside any locally downloaded PDFs directly to the Hugging Face dataset repository.

## Development

- Lint and format code:
  ```bash
  just lint
  ```
- Run type checks:
  ```bash
  just typecheck
  ```
- Clean build and cache artifacts:
  ```bash
  just clean
  ```

## TODO

Tracked status of crawler implementations against the [Cannot-Miss-AI-Conferences-Journals](https://github.com/christian-hoang-04/Cannot-Miss-AI-Conferences-Journals) registry:

### Conferences

- [x] **NeurIPS**
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **ICML**
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **ICLR**
  - [x] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [ ] **AAAI**
  - [ ] 2026
  - [ ] 2025
  - [ ] 2024
  - [ ] 2023
- [x] **IJCAI**
  - [ ] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **CVPR**
  - [x] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **ICCV**
  - [x] 2025
  - [x] 2023
- [ ] **ECCV**
  - [ ] 2024
- [x] **WACV**
  - [x] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **ACL**
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **EMNLP**
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **NAACL**
  - [ ] 2026 (combined with ACL)
  - [x] 2025
  - [x] 2024
  - [ ] 2023 (combined with ACL)
- [ ] **Interspeech**
  - [ ] 2025
  - [ ] 2024
  - [ ] 2023
- [ ] **ICASSP**
  - [ ] 2026
  - [ ] 2024

### Journals

- [x] **JMLR**
  - [ ] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
  - [x] 2022
- [ ] **TPAMI** (not fully open)
- [ ] **ACM MM**
  - [ ] 2025
  - [ ] 2024

