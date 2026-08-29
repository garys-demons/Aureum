# tests/unit/test_comparison_harness.py
"""
Tests for the Phase 7 evaluation harness. Uses fixture data saved via
the real research.storage/save_backtest_run pattern so this tests
against the actual persisted shape, not a hand-invented one.
"""
import pandas as pd
import pytest

import research.storage as storage_module
from research.storage import save_dataset
from research.evaluation.comparison_harness import (
    EvaluationResult,
    load_evaluation_result,
    compare_results,
)


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "DATA_ROOT", tmp_path / "data")


def _save_fake_summary(run_name: str, **overrides):
    row = {
        "starting_cash": 10_000.0, "ending_cash": 10_016.0,
        "realized_pnl": 16.0, "unrealized_pnl": 0.0, "final_equity": 10_016.0,
        "total_return_pct": 0.16, "num_trades": 46, "num_buys": 23, "num_sells": 23,
        "num_closing_trades": 23, "win_rate_pct": 89.36, "max_drawdown_pct": 1.2,
    }
    row.update(overrides)
    save_dataset(f"{run_name}_summary", pd.DataFrame([row]), category="results", source="test_fixture")


def test_load_evaluation_result_matches_saved_summary():
    _save_fake_summary("test_run")
    result = load_evaluation_result("test_run", strategy_name="TestStrategy")

    assert result.total_return_pct == 0.16
    assert result.win_rate_pct == 89.36
    assert result.num_trades == 46


def test_compare_results_hand_calculated():
    _save_fake_summary("baseline_run", total_return_pct=0.16, win_rate_pct=89.36, num_trades=46, max_drawdown_pct=1.2, final_equity=10_016.0)
    _save_fake_summary("ai_run", total_return_pct=0.45, win_rate_pct=91.0, num_trades=50, max_drawdown_pct=0.9, final_equity=10_045.0)

    baseline = load_evaluation_result("baseline_run", strategy_name="Baseline")
    candidate = load_evaluation_result("ai_run", strategy_name="AI")

    delta = compare_results(baseline, candidate)

    assert delta["total_return_pct_delta"] == pytest.approx(0.45 - 0.16)
    assert delta["win_rate_pct_delta"] == pytest.approx(91.0 - 89.36)
    assert delta["num_trades_delta"] == 4
    assert delta["max_drawdown_pct_delta"] == pytest.approx(0.9 - 1.2)


def test_compare_results_handles_none_win_rate():
    """A run with zero closing trades has win_rate_pct=None - delta
    must not crash, and must itself be None rather than a wrong number."""
    _save_fake_summary("baseline_run", win_rate_pct=89.36)
    _save_fake_summary("no_trades_run", win_rate_pct=None, num_trades=0)

    baseline = load_evaluation_result("baseline_run", strategy_name="Baseline")
    candidate = load_evaluation_result("no_trades_run", strategy_name="Candidate")

    delta = compare_results(baseline, candidate)
    assert delta["win_rate_pct_delta"] is None


def test_compare_results_does_not_produce_any_verdict_field():
    """
    Explicit guard against scope creep: this harness must never output
    a 'winner'/'better'/'verdict' field - that judgment belongs to
    Phase 8, per the task doc.
    """
    _save_fake_summary("baseline_run")
    _save_fake_summary("candidate_run", total_return_pct=5.0)

    baseline = load_evaluation_result("baseline_run", strategy_name="Baseline")
    candidate = load_evaluation_result("candidate_run", strategy_name="Candidate")

    delta = compare_results(baseline, candidate)
    forbidden_keys = {"winner", "better", "verdict", "recommendation", "conclusion"}
    assert not (forbidden_keys & delta.keys())