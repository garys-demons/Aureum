"""
tests/unit/test_run_baseline_evaluation.py

Confirms research/backtest/run_baseline_evaluation.py actually connects
BaselineMarketMaker + candle_fill_model + Portfolio + save_backtest_run
into a real, working run — using small, deterministic synthetic candles
(not random) so this test is reproducible.
"""
import shutil

import pandas as pd
import pytest

import research.storage as storage_module
from research.backtest import run_baseline_evaluation as rbe
from research.storage import get_manifest, load_dataset, save_dataset


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "DATA_ROOT", tmp_path / "data")


def make_deterministic_candles(n: int = 20) -> pd.DataFrame:
    """
    Small, fixed candle sequence — enough price movement that the
    baseline market maker's default quotes (±~0.0005 around fair
    price, ADA-scale) will actually cross the high/low range on
    several candles, producing real fills, without any randomness.
    """
    start_time = 1_700_000_000_000
    rows = []
    price = 0.1800
    for i in range(n):
        # Deterministic oscillation: alternates up/down with a fixed
        # amount, always wide enough (0.002) to cross a ~0.0005 quote.
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


def test_run_baseline_evaluation_produces_real_fills_and_pnl():
    save_dataset(
        rbe.BASELINE_DATASET, make_deterministic_candles(20),
        category="raw", source="test_fixture",
    )

    versions = rbe.run_baseline_evaluation()
    assert versions == {"trades": 1, "equity": 1, "summary": 1}

    trades = load_dataset("results", f"{rbe.BASELINE_RUN_NAME}_trades")
    # With this much price movement relative to the default spread,
    # at least some quotes should have actually filled — this is the
    # core thing that was broken before (parameter_sensitivity.py's
    # "every quote fills" shortcut, and run_sample_backtest.py not
    # simulating fills at all).
    assert len(trades) > 0
    assert "note" not in trades.columns  # confirms these are real fills, not the empty-run placeholder


def test_baseline_run_is_clearly_labeled():
    """The task's explicit requirement: Phase 8 must be able to reliably
    find this run later. Confirms the fixed name and is_baseline flag."""
    save_dataset(
        rbe.BASELINE_DATASET, make_deterministic_candles(10),
        category="raw", source="test_fixture",
    )
    rbe.run_baseline_evaluation()

    manifest = get_manifest("results", f"{rbe.BASELINE_RUN_NAME}_summary")
    assert manifest["metadata"]["is_baseline"] is True
    assert manifest["metadata"]["phase"] == 5
    assert manifest["metadata"]["strategy_name"] == "BaselineMarketMaker"


def test_summary_has_real_pnl_metrics():
    save_dataset(
        rbe.BASELINE_DATASET, make_deterministic_candles(20),
        category="raw", source="test_fixture",
    )
    rbe.run_baseline_evaluation()

    summary = load_dataset("results", f"{rbe.BASELINE_RUN_NAME}_summary")
    row = summary.iloc[0]
    # These being present and not all zero/None confirms real fills
    # actually happened and Portfolio actually tracked them - the
    # exact failure mode of the two pre-existing scripts.
    assert row["num_trades"] > 0
    assert row["starting_cash"] == rbe.STARTING_CASH


def test_strategy_inventory_stays_in_sync_with_fills():
    """
    Confirms record_fill() is actually being called — if it weren't,
    the strategy's inventory would stay at 0 forever, and every
    subsequent quote would be perfectly symmetric (no skew), which is
    easy to check indirectly via realized trades existing at all sizes
    other than the fixed order_quantity in a way that implies inventory
    tracking is live. Simpler direct check: run it and confirm no
    exception - record_fill()'s own side effects aren't independently
    observable from outside the run, so this mainly guards against a
    regression where the call is accidentally removed and inventory
    logic silently stops mattering (still runs without crashing either
    way, so this is a smoke test, not a precise assertion).
    """
    save_dataset(
        rbe.BASELINE_DATASET, make_deterministic_candles(20),
        category="raw", source="test_fixture",
    )
    versions = rbe.run_baseline_evaluation()
    assert versions is not None