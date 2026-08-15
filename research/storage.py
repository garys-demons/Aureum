"""
research/storage.py

Versioned dataset storage for Phase 3's research environment — the
actual place Hansika's historical downloads and Gauri's computed
features live.

WHY VERSIONED, NOT JUST FLAT FILES
-------------------------------------
The task explicitly calls for "not flat dumped files." The problem
with a flat file (e.g. `btcusdt_1m.parquet` that just gets overwritten
each time someone re-downloads) is that nobody can tell, later,
whether a given result was computed against the same data another
teammate used, or a different re-download with a slightly different
date range or a bug that's since been fixed. Once Samarth starts
auditing for look-ahead bias (his Phase 3 task), being able to say
"this feature was computed against dataset X, version 3, saved on
this date, covering this date range" is what makes that audit
possible at all.

WHERE DATA ACTUALLY LIVES
----------------------------
The repo's .gitignore already anticipated a top-level data/raw/ and
data/processed/ split (present before Phase 3 was assigned — an
existing convention, not something invented here). This module follows
that instead of introducing a separate location:

    data/<category>/<name>/<version>/data.parquet
    data/<category>/<name>/<version>/manifest.json

category is "raw" for Hansika's historical downloads (unmodified
source data) or "processed" for Gauri's computed features (derived
from raw data). Both are gitignored — dataset files, especially tick
data, don't belong in git history; only this module and the folder
structure itself are tracked.

Saving never overwrites an existing version — it always creates the
next one (v1, v2, v3, ...). The manifest records what's actually in
that version: row count, columns, a content checksum (so two versions
can be compared without re-reading both files), who/what produced it,
and freeform metadata (e.g. Hansika's task calls for documenting exact
start/end timestamps and any gaps found — that goes in metadata).

WHY PARQUET
-------------
Columnar, compressed, and both pandas and (later) any other tool can
read it without needing this project's own code — unlike, say, a
pickle file, which would only be safely readable by Python and only
if the reading environment has compatible library versions.

BOUNDARY RULE
---------------
This module must never be imported from core/ or services/ — it's
research infrastructure only, not part of the live trading pipeline.
Enforced by convention and code review, plus an automated check:
tests/unit/test_research_boundary.py scans core/ and services/ for any
import mentioning "research" and fails the build if it finds one.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
DATA_ROOT = REPO_ROOT / "data"

Category = Literal["raw", "processed"]


def _dataset_dir(category: Category, name: str) -> Path:
    return DATA_ROOT / category / name


def _next_version(category: Category, name: str) -> int:
    dataset_dir = _dataset_dir(category, name)
    if not dataset_dir.exists():
        return 1
    existing = [
        int(p.name[1:]) for p in dataset_dir.iterdir()
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
    ]
    return max(existing, default=0) + 1


def _checksum(df: pd.DataFrame) -> str:
    """A content hash of the dataframe, so two versions can be compared
    without re-reading both full files. Not cryptographically
    significant — just a cheap "did this actually change" signal."""
    return hashlib.sha256(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()[:16]


def save_dataset(
    name: str,
    df: pd.DataFrame,
    *,
    category: Category,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    """
    Saves a new version of a dataset. Never overwrites a previous
    version — always creates the next one.

    Args:
        name: dataset identifier, e.g. "btcusdt_candles_1m"
        df: the actual data
        category: "raw" (unmodified source data, e.g. Hansika's
                  historical downloads) or "processed" (derived data,
                  e.g. Gauri's computed features) — matches the
                  existing data/raw vs data/processed .gitignore split
        source: who/what produced this, e.g. "hansika/historical_downloader"
                or "gauri/feature_engine" — required, not optional, since
                "where did this come from" is exactly what versioning is
                for
        metadata: freeform extra info — e.g. Hansika's task calls for
                  documenting exact start/end timestamps and any gaps
                  found; that goes here, e.g.
                  {"start": "2024-01-01T00:00:00Z", "end": "...", "gaps": [...]}

    Returns the new version number.
    """
    if df.empty:
        raise ValueError(f"Refusing to save an empty dataframe for dataset {name!r}")

    version = _next_version(category, name)
    version_dir = _dataset_dir(category, name) / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    data_path = version_dir / "data.parquet"
    df.to_parquet(data_path, index=False)

    manifest = {
        "dataset": name,
        "category": category,
        "version": version,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "columns": list(df.columns),
        "checksum": _checksum(df),
        "metadata": metadata or {},
    }
    manifest_path = version_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return version


def load_dataset(category: Category, name: str, version: int | str = "latest") -> pd.DataFrame:
    """
    Loads a dataset. version="latest" (default) loads the highest
    version number; pass an explicit int to load a specific one.
    """
    dataset_dir = _dataset_dir(category, name)
    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"No dataset named {name!r} in category {category!r} exists at {dataset_dir}"
        )

    if version == "latest":
        version = _next_version(category, name) - 1
        if version < 1:
            raise FileNotFoundError(f"Dataset {name!r} exists but has no saved versions")

    data_path = dataset_dir / f"v{version}" / "data.parquet"
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset {name!r} has no version {version}")

    return pd.read_parquet(data_path)


def get_manifest(category: Category, name: str, version: int | str = "latest") -> dict[str, Any]:
    """Reads a version's manifest without loading the (potentially large) data itself."""
    dataset_dir = _dataset_dir(category, name)
    if version == "latest":
        version = _next_version(category, name) - 1
        if version < 1:
            raise FileNotFoundError(f"Dataset {name!r} exists but has no saved versions")

    manifest_path = dataset_dir / f"v{version}" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Dataset {name!r} has no version {version}")

    return json.loads(manifest_path.read_text())


def list_versions(category: Category, name: str) -> list[dict[str, Any]]:
    """Returns every version's manifest for a dataset, oldest first."""
    dataset_dir = _dataset_dir(category, name)
    if not dataset_dir.exists():
        return []

    versions = sorted(
        int(p.name[1:]) for p in dataset_dir.iterdir()
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
    )
    return [get_manifest(category, name, v) for v in versions]


def list_datasets(category: Category) -> list[str]:
    """Returns every dataset name in a category that has at least one saved version."""
    category_root = DATA_ROOT / category
    if not category_root.exists():
        return []
    return sorted(p.name for p in category_root.iterdir() if p.is_dir())