# papercli

A command-line tool to crawl, index, download, and search AI conference and journal papers.

## Features

- Fetch metadata from top-tier AI venues (ACL, EMNLP, NAACL, CVPR, ICCV, WACV, NeurIPS, ICML, ICLR), curated from the [Cannot-Miss-AI-Conferences-Journals](https://github.com/christian-hoang-04/Cannot-Miss-AI-Conferences-Journals) registry.
- Local SQLite database storage with FTS5 virtual tables for rapid text search.
- Retrieve and store PDFs locally.
- Export indexed papers to Parquet format.

### Setup

Requires Python 3.12+.

1. Clone the repository.
2. Set up the virtual environment and install dependencies:

   With uv:

   ```bash
   uv sync
   ```

   With pip:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

## Usage

If you installed using standard Python, activate the virtual environment (`source .venv/bin/activate`) and run commands using `papers <command>`.
If you installed using `uv sync`, run commands using `uv run papers <command>`.
If you have `just` installed, you can use the helper shortcuts in the `Justfile`.

### Supported Venues

The CLI crawls and indexes key publications from the [Cannot-Miss-AI-Conferences-Journals](https://github.com/christian-hoang-04/Cannot-Miss-AI-Conferences-Journals) registry:

- ACL Anthology: `ACL`, `EMNLP`, `NAACL`
- CVF: `CVPR`, `ICCV`, `WACV`
- OpenReview: `NeurIPS`, `ICML`, `ICLR`
- ECVA: `ECCV`
- ISCA: `Interspeech`

List registered venues:

```bash
papers venues
# or:
uv run papers venues
```

View venue status and download progress:

```bash
papers venue-years
# or:
uv run papers venue-years
# or:
just venue-years
```

### Crawling & Indexing

Crawl a specific venue and year:

```bash
papers crawl <venue> <year>
# Example:
papers crawl ACL 2025
# or:
uv run papers crawl ACL 2025
# or:
just crawl ACL 2025
```

Crawl and index all supported venue-years:

```bash
papers index
# or:
uv run papers index
# or:
just index
```

Metadata is stored in SQLite at `.papercli/papers.db`.

### Searching Papers

Search title, abstract, and authors:

```bash
papers search "<query>"
# Example:
papers search "attention mechanism"
# or:
uv run papers search "attention mechanism"
# or:
just search "attention mechanism"
```

Options:

- `--venue <venue>`: Filter search by venue.
- `--limit <int>`: Maximum results (default: 20).

### Downloading PDFs

Retrieve PDF files to `.papercli/pdfs/`:

```bash
papers download [--venue <venue>] [--year <year>] [--delay <seconds>]
# Example:
papers download --venue ACL --year 2025
# or:
uv run papers download --venue ACL --year 2025
# or:
just download venue="ACL" year="2025"
```

### Exporting Metadata

Export papers to a Parquet file (defaults to `.papercli/papers.parquet`):

```bash
papers export
# or:
uv run papers export
# or:
just export-parquet
```

### Dataset Structure

- `ClosedUni/papercli-papers` (main entrypoint): Contains the full index metadata parquet (`papers.parquet`) and the per-venue browse parquet views (`browse/`).
- `ClosedUni/papercli-papers-[venue]`: Contains the sharded PDF files of that specific venue (no metadata parquet).

### Resolving PDFs

Each row has `pdf_url` (the original source link, always present) and `hf_pdf_path` (a path within this dataset, present only for mirrored papers).

To fetch a mirrored PDF:

```python
from huggingface_hub import hf_hub_download

repo_id = f"ClosedUni/papercli-papers-{row['venue'].lower()}"
path = hf_hub_download(
    repo_id=repo_id,
    filename=row["hf_pdf_path"],   # e.g. "pdfs/acl/2025/12/12d4c706b05abfff.pdf"
    repo_type="dataset",
)
```

If `hf_pdf_path` is null, use `pdf_url` instead.

### Publishing & Collaboration

To publish indexed papers and downloaded PDFs to the `ClosedUni/papercli-papers` Hugging Face dataset (configured via the `HF_DATASET_SLUG` environment variable):

1. Authenticate with Hugging Face:

   ```bash
   huggingface-cli login
   ```

   Or set the `HF_TOKEN` environment variable.

2. Crawl and index all paper metadata locally:

   ```bash
   papers index
   ```

3. (Optional) Download PDFs for the venues/years you want to contribute (e.g. CVPR):

   ```bash
   papers download --venue CVPR --year 2025   # Specific year
   papers download --venue CVPR               # All years for CVPR
   ```

   _Note: The export script checks the remote Hugging Face repository first, so your uploads will merge cleanly with PDFs uploaded by other contributors without overwriting their metadata links._

4. Export and upload to Hugging Face:
   ```bash
   papers publish
   ```

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
- [x] **AAAI**
  - [x] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [x] **IJCAI**
  - [ ] 2026 (Not yet, August 2026)
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
- [x] **ECCV**
  - [x] 2024
  - [x] 2022
  - [x] 2020
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
  - [ ] 2026 (Not yet, July 2026)
  - [x] 2025
  - [x] 2024
  - [ ] 2023 (combined with ACL)
- [x] **Interspeech**
  - [x] 2025
  - [x] 2024
  - [x] 2023
- [ ] **ICASSP** (Deferred, IEEE)
  - [ ] 2026
  - [ ] 2024

### Journals

- [x] **JMLR**
  - [ ] 2026
  - [x] 2025
  - [x] 2024
  - [x] 2023
  - [x] 2022
- [ ] **TPAMI** (Deferred, IEEE)
- [ ] **ACM MM** (Deferred, paywalled, blocks crawlers without official API registration)
  - [ ] 2025
  - [ ] 2024
