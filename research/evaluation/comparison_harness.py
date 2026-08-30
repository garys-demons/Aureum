"""
Evaluation harness for comparing strategy variants against phase5_baseline
(Phase 7). Loads real persisted results via research.storage. Produces
structured deltas only - does NOT determine a winner or make any
"AI beats baseline" claim, per the Phase 7 task doc; that judgment
belongs to Phase 8's statistical comparison.
"""
from dataclasses import dataclass
from research.storage import load_dataset

BASELINE_RUN_NAME = "phase5_baseline"


@dataclass
class EvaluationResult:
    """
    Mirrors the real fields Portfolio.summary() produces - not an
    invented parallel shape. Built directly from a saved run's
    "<run_name>_summary" dataset (research/backtest/results.py).
    """
    run_name: str
    strategy_name: str
    starting_cash: float
    ending_cash: float
    realized_pnl: float
    unrealized_pnl: float
    final_equity: float
    total_return_pct: float
    num_trades: int
    num_buys: int
    num_sells: int
    num_closing_trades: int
    win_rate_pct: float | None
    max_drawdown_pct: float


def load_evaluation_result(run_name: str, strategy_name: str) -> EvaluationResult:
    """
    Loads a completed run's summary via the same research.storage path
    the baseline evaluation script and its tests already use - works
    identically for the baseline or any future AI-assisted run, since
    both are saved through research.backtest.results.save_backtest_run().
    """
    df = load_dataset("results", f"{run_name}_summary")
    row = df.iloc[0].to_dict()

    return EvaluationResult(
        run_name=run_name,
        strategy_name=strategy_name,
        starting_cash=row["starting_cash"],
        ending_cash=row["ending_cash"],
        realized_pnl=row["realized_pnl"],
        unrealized_pnl=row["unrealized_pnl"],
        final_equity=row["final_equity"],
        total_return_pct=row["total_return_pct"],
        num_trades=row["num_trades"],
        num_buys=row["num_buys"],
        num_sells=row["num_sells"],
        num_closing_trades=row["num_closing_trades"],
        win_rate_pct=row["win_rate_pct"],
        max_drawdown_pct=row["max_drawdown_pct"],
    )


def load_baseline_result() -> EvaluationResult:
    """Convenience wrapper - always loads the fixed, documented baseline."""
    return load_evaluation_result(BASELINE_RUN_NAME, strategy_name="BaselineMarketMaker")


def compare_results(baseline: EvaluationResult, candidate: EvaluationResult) -> dict:
    """
    Returns structured deltas only (candidate minus baseline) - no
    verdict, no "better/worse" label. Phase 8 decides what these
    numbers mean statistically (sample size, significance).
    """
    return {
        "baseline_run": baseline.run_name,
        "candidate_run": candidate.run_name,
        "total_return_pct_delta": candidate.total_return_pct - baseline.total_return_pct,
        "win_rate_pct_delta": (
            candidate.win_rate_pct - baseline.win_rate_pct
            if candidate.win_rate_pct is not None and baseline.win_rate_pct is not None
            else None
        ),
        "num_trades_delta": candidate.num_trades - baseline.num_trades,
        "max_drawdown_pct_delta": candidate.max_drawdown_pct - baseline.max_drawdown_pct,
        "final_equity_delta": candidate.final_equity - baseline.final_equity,
    }