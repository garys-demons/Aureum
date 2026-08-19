"""
tests/unit/test_research_storage.py

Confirms research/storage.py's versioning actually works: old versions
are never overwritten, "latest" resolves correctly, data round-trips
accurately, manifests capture the right metadata, and raw/processed
categories stay separate.
"""
import shutil

import pandas as pd
import pytest

from research.storage import (
    DATA_ROOT,
    get_manifest,
    list_datasets,
    list_versions,
    load_dataset,
    save_dataset,
)


@pytest.fixture(autouse=True)
def clean_data_dir():
    if DATA_ROOT.exists():
        shutil.rmtree(DATA_ROOT)
    yield
    if DATA_ROOT.exists():
        shutil.rmtree(DATA_ROOT)


def make_df(n=3, start_price=100.0):
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1min"),
        "close": [start_price + i for i in range(n)],
    })


def test_first_save_creates_version_1():
    version = save_dataset("test_ds", make_df(), category="raw", source="unit_test")
    assert version == 1


def test_second_save_creates_version_2_not_overwrite():
    save_dataset("test_ds", make_df(3), category="raw", source="unit_test")
    v2 = save_dataset("test_ds", make_df(5), category="raw", source="unit_test")
    assert v2 == 2

    v1_data = load_dataset("raw", "test_ds", version=1)
    v2_data = load_dataset("raw", "test_ds", version=2)
    assert len(v1_data) == 3
    assert len(v2_data) == 5


def test_load_latest_gets_highest_version():
    save_dataset("test_ds", make_df(3), category="raw", source="unit_test")
    save_dataset("test_ds", make_df(5), category="raw", source="unit_test")
    save_dataset("test_ds", make_df(7), category="raw", source="unit_test")

    latest = load_dataset("raw", "test_ds")  # default version="latest"
    assert len(latest) == 7


def test_data_values_round_trip_accurately():
    df = make_df(3, start_price=42.5)
    save_dataset("test_ds", df, category="raw", source="unit_test")
    loaded = load_dataset("raw", "test_ds")
    assert loaded["close"].iloc[0] == 42.5
    assert loaded["close"].iloc[-1] == 44.5


def test_manifest_records_correct_metadata():
    save_dataset(
        "test_ds", make_df(4), category="raw", source="hansika/historical_downloader",
        metadata={"start": "2024-01-01", "end": "2024-01-02", "gaps": ["2024-01-01T12:00"]},
    )
    manifest = get_manifest("raw", "test_ds")
    assert manifest["row_count"] == 4
    assert manifest["category"] == "raw"
    assert manifest["source"] == "hansika/historical_downloader"
    assert manifest["version"] == 1
    assert manifest["metadata"]["gaps"] == ["2024-01-01T12:00"]
    assert "checksum" in manifest
    assert "created_at" in manifest


def test_different_data_produces_different_checksums():
    save_dataset("test_ds", make_df(3, start_price=100.0), category="raw", source="unit_test")
    save_dataset("test_ds", make_df(3, start_price=200.0), category="raw", source="unit_test")

    m1 = get_manifest("raw", "test_ds", version=1)
    m2 = get_manifest("raw", "test_ds", version=2)
    assert m1["checksum"] != m2["checksum"]


def test_list_versions_returns_all_in_order():
    save_dataset("test_ds", make_df(3), category="raw", source="unit_test")
    save_dataset("test_ds", make_df(5), category="raw", source="unit_test")

    versions = list_versions("raw", "test_ds")
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2


def test_list_datasets_returns_all_saved_names():
    save_dataset("dataset_a", make_df(), category="raw", source="unit_test")
    save_dataset("dataset_b", make_df(), category="raw", source="unit_test")

    assert sorted(list_datasets("raw")) == ["dataset_a", "dataset_b"]


def test_raw_and_processed_categories_stay_separate():
    """Same dataset name, different category — must not collide."""
    save_dataset("btcusdt_1m", make_df(3), category="raw", source="hansika/historical_downloader")
    save_dataset("btcusdt_1m", make_df(9), category="processed", source="gauri/feature_engine")

    raw = load_dataset("raw", "btcusdt_1m")
    processed = load_dataset("processed", "btcusdt_1m")
    assert len(raw) == 3
    assert len(processed) == 9

    assert list_datasets("raw") == ["btcusdt_1m"]
    assert list_datasets("processed") == ["btcusdt_1m"]


def test_empty_dataframe_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        save_dataset("test_ds", pd.DataFrame(), category="raw", source="unit_test")


def test_loading_nonexistent_dataset_raises_clearly():
    with pytest.raises(FileNotFoundError, match="test_ds"):
        load_dataset("raw", "test_ds")


def test_loading_nonexistent_version_raises_clearly():
    save_dataset("test_ds", make_df(), category="raw", source="unit_test")
    with pytest.raises(FileNotFoundError, match="version 99"):
        load_dataset("raw", "test_ds", version=99)


def test_list_versions_on_empty_dataset_returns_empty_list():
    assert list_versions("raw", "never_saved") == []


def test_list_datasets_on_empty_store_returns_empty_list():
    assert list_datasets("raw") == []

def test_concurrent_save_raises_instead_of_silently_overwriting(monkeypatch):
    """
    Regression: _next_version() and the version-dir creation aren't atomic.
    A real race can't be reproduced in a single-threaded test by simply
    pre-creating a directory, since the next call to _next_version() would
    just see it on disk and skip past it. Instead, this monkeypatches
    _next_version to return a stale value — as if it had been computed
    before a concurrent writer's directory existed — and confirms
    mkdir(exist_ok=False) still catches the resulting collision.
    """
    import research.storage as storage_module

    save_dataset("collision_ds", make_df(), category="raw", source="unit_test")

    # A concurrent caller already created v2 on disk.
    storage_module._dataset_dir("raw", "collision_ds").joinpath("v2").mkdir(parents=True)

    # Force THIS call to compute the same stale version number (2) that
    # the concurrent caller already used — simulating the race window
    # where both callers read the directory before either had written.
    monkeypatch.setattr(storage_module, "_next_version", lambda category, name: 2)

    with pytest.raises(FileExistsError):
        save_dataset("collision_ds", make_df(3), category="raw", source="unit_test")