"""
tests/unit/test_run_comparison_evaluation.py

Phase 8: confirms the refactor of run_baseline_evaluation.py (extracting
a generic run_strategy_evaluation() core) didn't change Phase 5's
existing behavior, and that the generic function genuinely works for a
strategy OTHER than BaselineMarketMaker — not just re-running the same
one under a different name.

Also confirms the resulting runs are directly consumable by Gauri's
comparison_harness.py, since that's the actual point of saving them
under a fixed, documented name.
"""
import shutil

import pandas as pd
import pytest

import research.storage as storage_module
from core.strategy.baseline_market_maker import BaselineMarketMaker
from research.backtest.run_baseline_evaluation import (
    BASELINE_RUN_NAME,
    run_baseline_evaluation,
    run_strategy_evaluation,
)
from research.storage import load_dataset, save_dataset


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "DATA_ROOT", tmp_path / "data")


def make_deterministic_candles(n: int = 20) -> pd.DataFrame:
    """Same fixed, non-random sequence used in Phase 5's own tests —
    kept identical here deliberately, so this file's regression check
    is comparing like-for-like against known-good Phase 5 numbers."""
    start_time = 1_700_000_000_000
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


class FakeAlwaysPausedVariant:
    """
    A minimal stand-in for a future 'reduce/pause quoting' strategy
    variant (Phase 8's actual task, not yet built) — wraps
    BaselineMarketMaker for record_fill()/inventory but NEVER quotes,
    the simplest possible distinguishable behavior. Used only to prove
    run_strategy_evaluation() genuinely respects whatever a different
    strategy does, not to simulate Samarth's real regime-aware logic.
    """

    def __init__(self, symbol: str):
        self._inner = BaselineMarketMaker(symbol=symbol, base_half_spread=0.001)

    @property
    def inventory(self):
        return self._inner.inventory

    def decide(self, market_data):
        return []  # never quotes, regardless of market conditions

    def record_fill(self, action, quantity):
        self._inner.record_fill(action, quantity)


def test_refactored_run_baseline_evaluation_matches_known_good_values():
    """
    Regression test — updated after the Phase 8 fee correction
    (MAKER_FEE_RATE 0.0005 -> 0.001, verified against Binance's real
    published spot maker fee schedule). These exact numbers were
    hand-verified against the actual trade log at the corrected rate —
    e.g. the second trade (a sell closing the first buy at 0.180,
    selling at 0.182): realized_pnl = (0.182 - 0.180) * 100 - 0.0182
    fee = 0.1818, confirmed directly against the persisted trade log,
    not just accepted from the code's own output.
    """
    save_dataset("adausdt_candles_1m_recent_24h", make_deterministic_candles(20),
                 category="raw", source="test")

    run_baseline_evaluation()

    summary = load_dataset("results", f"{BASELINE_RUN_NAME}_summary")
    row = summary.iloc[0]

    assert row["num_trades"] == 40
    assert row["num_buys"] == 20
    assert row["num_sells"] == 20
    assert row["realized_pnl"] == pytest.approx(3.637, abs=1e-3)
    assert row["ending_cash"] == pytest.approx(10003.278, abs=1e-3)
    assert row["win_rate_pct"] == 100.0
    assert row["max_drawdown_pct"] == 0.0


def test_run_strategy_evaluation_is_genuinely_generic():
    """
    Proves the extracted core respects a DIFFERENT strategy's real
    behavior (zero trades, since FakeAlwaysPausedVariant never quotes)
    — not just producing the baseline's numbers again under a new name.
    """
    save_dataset("adausdt_candles_1m_recent_24h", make_deterministic_candles(20),
                 category="raw", source="test")

    versions = run_strategy_evaluation(
        lambda symbol: FakeAlwaysPausedVariant(symbol),
        run_name="test_paused_variant",
        strategy_name="FakeAlwaysPausedVariant",
        extra_metadata={"test": True},
    )
    assert versions == {"trades": 1, "equity": 1, "summary": 1}

    summary = load_dataset("results", "test_paused_variant_summary")
    row = summary.iloc[0]
    assert row["num_trades"] == 0
    assert row["starting_cash"] == row["final_equity"]


def test_comparison_harness_can_load_a_run_saved_this_way():
    """
    Integration check with Gauri's research/evaluation/comparison_harness.py
    — confirms a run saved via run_strategy_evaluation() is directly
    loadable through her EvaluationResult path, exactly the same as
    the baseline, since that's the entire point of the fixed-name
    persistence convention.
    """
    from research.evaluation.comparison_harness import load_evaluation_result

    save_dataset("adausdt_candles_1m_recent_24h", make_deterministic_candles(20),
                 category="raw", source="test")

    run_strategy_evaluation(
        lambda symbol: FakeAlwaysPausedVariant(symbol),
        run_name="test_paused_variant",
        strategy_name="FakeAlwaysPausedVariant",
    )

    result = load_evaluation_result("test_paused_variant", strategy_name="FakeAlwaysPausedVariant")
    assert result.run_name == "test_paused_variant"
    assert result.num_trades == 0
    assert result.starting_cash == 10_000.0


def test_comparison_harness_deltas_work_between_two_runs_saved_this_way():
    """
    Full integration: baseline + a variant, both saved through this
    module, compared via Gauri's compare_results() — proving the whole
    chain Phase 8 actually needs works end-to-end, not just each piece
    in isolation.
    """
    from research.evaluation.comparison_harness import compare_results, load_evaluation_result

    save_dataset("adausdt_candles_1m_recent_24h", make_deterministic_candles(20),
                 category="raw", source="test")

    run_baseline_evaluation()
    run_strategy_evaluation(
        lambda symbol: FakeAlwaysPausedVariant(symbol),
        run_name="test_paused_variant",
        strategy_name="FakeAlwaysPausedVariant",
    )

    baseline = load_evaluation_result(BASELINE_RUN_NAME, strategy_name="BaselineMarketMaker")
    candidate = load_evaluation_result("test_paused_variant", strategy_name="FakeAlwaysPausedVariant")

    deltas = compare_results(baseline, candidate)
    # The paused variant made zero trades, so its return is exactly 0% —
    # the delta from baseline's real (nonzero) return should reflect that.
    assert deltas["num_trades_delta"] == 0 - 40
    assert deltas["total_return_pct_delta"] == pytest.approx(0.0 - baseline.total_return_pct, abs=1e-6)