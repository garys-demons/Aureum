# notebooks/

Exploratory analysis — Jupyter notebooks or similar. Meant to be
revisited and built on, unlike experiments/ which is fine to abandon.

Load data via `research.storage.load_dataset()`, don't read parquet
files directly — that way every notebook automatically benefits from
the versioning (e.g. re-running against `version=1` to reproduce an
old result).