"""
tests/unit/test_backtest_results.py

Confirms research/backtest/results.py correctly persists a completed
Portfolio's trades, equity curve, and summary metrics — and that the
numbers survive a real save/reload round trip through research/storage.py.
"""
import shutil
from datetime import datetime

import pytest

import research.storage as storage_module
from core.portfolio.portfolio import Fill, Portfolio
from research.backtest.results import save_backtest_run
from research.storage import list_versions, load_dataset


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    """Same isolation pattern as test_research_storage.py — never touch
    the real data/ folder from tests."""
    monkeypatch.setattr(storage_module, "DATA_ROOT", tmp_path / "data")


def make_completed_run() -> Portfolio:
    p = Portfolio(starting_cash=10_000.0)
    p.record_equity_snapshot(datetime(2024, 1, 1), {})
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 1.0, datetime(2024, 1, 1)))
    p.record_equity_snapshot(datetime(2024, 1, 2), {"BTCUSDT": 110.0})
    p.process_fill(Fill("BTCUSDT", "sell", 1.0, 120.0, 1.0, datetime(2024, 1, 3)))
    p.record_equity_snapshot(datetime(2024, 1, 3), {})
    return p


def test_save_backtest_run_creates_three_datasets():
    p = make_completed_run()
    versions = save_backtest_run(p, "test_run", strategy_name="stub_strategy")

    assert versions == {"trades": 1, "equity": 1, "summary": 1}


def test_trade_log_round_trips_correctly():
    p = make_completed_run()
    save_backtest_run(p, "test_run")

    trades = load_dataset("results", "test_run_trades")
    assert len(trades) == 2
    assert trades.iloc[0]["side"] == "buy"
    assert trades.iloc[1]["side"] == "sell"
    assert trades.iloc[1]["realized_pnl"] == 19.0  # (120-100)*1 - 1 fee


def test_equity_curve_round_trips_correctly():
    p = make_completed_run()
    save_backtest_run(p, "test_run")

    equity = load_dataset("results", "test_run_equity")
    assert len(equity) == 3
    assert equity.iloc[0]["equity"] == 10_000.0
    assert equity.iloc[-1]["equity"] == 10_018.0


def test_summary_round_trips_correctly():
    p = make_completed_run()
    save_backtest_run(p, "test_run")

    summary = load_dataset("results", "test_run_summary")
    assert len(summary) == 1
    assert summary.iloc[0]["realized_pnl"] == 19.0
    assert summary.iloc[0]["num_trades"] == 2
    assert summary.iloc[0]["win_rate_pct"] == 100.0


def test_metadata_is_recorded_on_saved_datasets():
    p = make_completed_run()
    save_backtest_run(
        p, "test_run", strategy_name="stub_strategy",
        extra_metadata={"symbols": ["BTCUSDT"]},
    )

    manifests = list_versions("results", "test_run_summary")
    assert len(manifests) == 1
    assert manifests[0]["metadata"]["run_name"] == "test_run"
    assert manifests[0]["metadata"]["strategy_name"] == "stub_strategy"
    assert manifests[0]["metadata"]["symbols"] == ["BTCUSDT"]


def test_run_with_zero_trades_still_saves_with_placeholder():
    """A strategy that decided to hold the entire time produces a valid,
    real result — this shouldn't fail just because trade_log is empty
    (save_dataset() itself rejects empty dataframes)."""
    p = Portfolio(starting_cash=10_000.0)  # no fills processed at all

    versions = save_backtest_run(p, "empty_run")
    assert versions == {"trades": 1, "equity": 1, "summary": 1}

    trades = load_dataset("results", "empty_run_trades")
    assert len(trades) == 1
    assert "note" in trades.columns


def test_current_prices_affects_saved_summary():
    """Confirms current_prices is actually threaded through to the
    summary that gets saved, not silently dropped."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 1)))
    # position still open — no sell

    save_backtest_run(p, "open_position_run", current_prices={"BTCUSDT": 150.0})

    summary = load_dataset("results", "open_position_run_summary")
    # unrealized = (150 - 100) * 1 = 50
    assert summary.iloc[0]["unrealized_pnl"] == 50.0