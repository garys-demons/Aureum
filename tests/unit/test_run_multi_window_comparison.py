"""
tests/unit/test_run_multi_window_comparison.py

Confirms run_multi_window_comparison.py correctly runs both strategies
across all 3 pinned windows, with recent_24h reusing the existing
canonical run names (not duplicating them under new ones) and the
other two windows getting their own distinct, correctly-named runs.
"""
import pandas as pd
import pytest

import research.storage as storage_module
from research.backtest.run_baseline_evaluation import BASELINE_RUN_NAME
from research.backtest.run_comparison_evaluation import COMPARISON_RUN_NAME
from research.backtest.run_multi_window_comparison import (
    WINDOWS,
    run_multi_window_comparison,
)
from research.storage import get_manifest, load_dataset, save_dataset


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "DATA_ROOT", tmp_path / "data")


def make_candles(n: int, start_time: int) -> pd.DataFrame:
    rows = []
    price = 0.1800
    for i in range(n):
        direction = 1 if i % 2 == 0 else -1
        move = direction * 0.001
        close_p = price + move
        high_p = max(price, close_p) + 0.001
        low_p = min(price, close_p) - 0.001
        rows.append({
            "event_type": "kline", "exchange": "binance", "symbol": "ADAUSDT",
            "event_time": start_time + i * 60_000, "received_time": start_time + i * 60_000 + 50,
            "interval": "1m", "open_time": start_time + i * 60_000,
            "close_time": start_time + (i + 1) * 60_000,
            "open": price, "high": high_p, "low": low_p, "close": close_p,
            "volume": 1000.0, "is_closed": True,
        })
        price = close_p
    return pd.DataFrame(rows)


def save_all_three_windows():
    save_dataset("adausdt_candles_1m_recent_24h", make_candles(20, 1_700_000_000_000),
                 category="raw", source="test")
    save_dataset("adausdt_candles_1m_prior_24h", make_candles(20, 1_699_900_000_000),
                 category="raw", source="test")
    save_dataset("adausdt_candles_1m_prior_48h", make_candles(20, 1_699_800_000_000),
                 category="raw", source="test")


def test_all_three_windows_get_processed():
    save_all_three_windows()
    results = run_multi_window_comparison()

    assert set(results.keys()) == {
        "recent_24h_baseline", "recent_24h_ai",
        "prior_24h_baseline", "prior_24h_ai",
        "prior_48h_baseline", "prior_48h_ai",
    }
    for versions in results.values():
        assert versions == {"trades": 1, "equity": 1, "summary": 1}


def test_recent_24h_reuses_canonical_run_names_not_duplicated():
    """
    The whole point of this design choice: recent_24h must land under
    the EXISTING phase5_baseline / phase8_baseline_plus_ai names, not
    a new "phase8_baseline_recent_24h" — those already ARE the
    canonical recent_24h results referenced elsewhere in the project.
    """
    save_all_three_windows()
    run_multi_window_comparison()

    # These specific names must exist and be loadable — proves reuse,
    # not just "some run happened".
    baseline = load_dataset("results", f"{BASELINE_RUN_NAME}_summary")
    ai = load_dataset("results", f"{COMPARISON_RUN_NAME}_summary")
    assert len(baseline) == 1
    assert len(ai) == 1


def test_prior_windows_get_distinct_new_names():
    save_all_three_windows()
    run_multi_window_comparison()

    baseline_24h = load_dataset("results", "phase8_baseline_prior_24h_summary")
    ai_24h = load_dataset("results", "phase8_ai_prior_24h_summary")
    baseline_48h = load_dataset("results", "phase8_baseline_prior_48h_summary")
    ai_48h = load_dataset("results", "phase8_ai_prior_48h_summary")

    assert len(baseline_24h) == 1
    assert len(ai_24h) == 1
    assert len(baseline_48h) == 1
    assert len(ai_48h) == 1


def test_metadata_records_which_window_and_what_it_compares_against():
    save_all_three_windows()
    run_multi_window_comparison()

    manifest = get_manifest("results", "phase8_baseline_prior_24h_summary")
    assert manifest["metadata"]["window"] == "prior_24h"
    assert manifest["metadata"]["phase"] == 8

    ai_manifest = get_manifest("results", "phase8_ai_prior_24h_summary")
    assert ai_manifest["metadata"]["compares_against"] == "phase8_baseline_prior_24h"


def test_windows_constant_has_exactly_three_entries_with_expected_labels():
    labels = [w[0] for w in WINDOWS]
    assert labels == ["recent_24h", "prior_24h", "prior_48h"]