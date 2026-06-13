---
license: cc-by-4.0
pretty_name: AI Conference & Journal Papers
configs:
  - config_name: aaai
    data_files:
      - split: "2026"
        path: browse/aaai/2026.parquet
      - split: "2025"
        path: browse/aaai/2025.parquet
      - split: "2024"
        path: browse/aaai/2024.parquet
      - split: "2023"
        path: browse/aaai/2023.parquet
  - config_name: acl
    data_files:
      - split: "2025"
        path: browse/acl/2025.parquet
      - split: "2024"
        path: browse/acl/2024.parquet
      - split: "2023"
        path: browse/acl/2023.parquet
  - config_name: cvpr
    data_files:
      - split: "2026"
        path: browse/cvpr/2026.parquet
      - split: "2025"
        path: browse/cvpr/2025.parquet
      - split: "2024"
        path: browse/cvpr/2024.parquet
      - split: "2023"
        path: browse/cvpr/2023.parquet
  - config_name: eccv
    data_files:
      - split: "2024"
        path: browse/eccv/2024.parquet
      - split: "2022"
        path: browse/eccv/2022.parquet
      - split: "2020"
        path: browse/eccv/2020.parquet
  - config_name: emnlp
    data_files:
      - split: "2025"
        path: browse/emnlp/2025.parquet
      - split: "2024"
        path: browse/emnlp/2024.parquet
      - split: "2023"
        path: browse/emnlp/2023.parquet
  - config_name: iccv
    data_files:
      - split: "2025"
        path: browse/iccv/2025.parquet
      - split: "2023"
        path: browse/iccv/2023.parquet
  - config_name: iclr
    data_files:
      - split: "2026"
        path: browse/iclr/2026.parquet
      - split: "2025"
        path: browse/iclr/2025.parquet
      - split: "2024"
        path: browse/iclr/2024.parquet
      - split: "2023"
        path: browse/iclr/2023.parquet
  - config_name: icml
    data_files:
      - split: "2025"
        path: browse/icml/2025.parquet
      - split: "2024"
        path: browse/icml/2024.parquet
      - split: "2023"
        path: browse/icml/2023.parquet
  - config_name: ijcai
    data_files:
      - split: "2025"
        path: browse/ijcai/2025.parquet
      - split: "2024"
        path: browse/ijcai/2024.parquet
      - split: "2023"
        path: browse/ijcai/2023.parquet
  - config_name: interspeech
    data_files:
      - split: "2025"
        path: browse/interspeech/2025.parquet
      - split: "2024"
        path: browse/interspeech/2024.parquet
      - split: "2023"
        path: browse/interspeech/2023.parquet
  - config_name: jmlr
    data_files:
      - split: "2025"
        path: browse/jmlr/2025.parquet
      - split: "2024"
        path: browse/jmlr/2024.parquet
      - split: "2023"
        path: browse/jmlr/2023.parquet
      - split: "2022"
        path: browse/jmlr/2022.parquet
  - config_name: naacl
    data_files:
      - split: "2025"
        path: browse/naacl/2025.parquet
      - split: "2024"
        path: browse/naacl/2024.parquet
  - config_name: neurips
    data_files:
      - split: "2025"
        path: browse/neurips/2025.parquet
      - split: "2024"
        path: browse/neurips/2024.parquet
      - split: "2023"
        path: browse/neurips/2023.parquet
  - config_name: wacv
    data_files:
      - split: "2026"
        path: browse/wacv/2026.parquet
      - split: "2025"
        path: browse/wacv/2025.parquet
      - split: "2024"
        path: browse/wacv/2024.parquet
      - split: "2023"
        path: browse/wacv/2023.parquet
---

# AI Conference & Journal Papers

Searchable metadata for papers from top AI venues (NeurIPS, ICML, ICLR, CVPR, ICCV, WACV, ACL, EMNLP, NAACL).

- `papers.parquet`: the full dataset (all fields, all venues).
- Per-venue browse views: pick a venue in **Subset**, a year in **Split**.

### Dataset Structure

- `ClosedUni/papercli-papers` (main entrypoint): Contains the full index metadata parquet (`papers.parquet`) and the per-venue browse parquet views (`browse/`).
- `ClosedUni/papercli-papers-[venue]`: Contains the sharded PDF files of that specific venue (no metadata parquet).

### PDF Storage

PDF files are sharded across separate datasets by venue to keep repository sizes optimal:
- `ClosedUni/papercli-papers-[venue]` (e.g. `ClosedUni/papercli-papers-cvpr` for CVPR PDFs)

To download a mirrored PDF:
```python
from huggingface_hub import hf_hub_download

repo_id = f"ClosedUni/papercli-papers-{row['venue'].lower()}"
path = hf_hub_download(
    repo_id=repo_id,
    filename=row["hf_pdf_path"],
    repo_type="dataset",
)
```

Built with [papercli](https://github.com/Keithsel/papercli).