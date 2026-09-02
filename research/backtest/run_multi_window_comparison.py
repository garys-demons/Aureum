"""
research/backtest/run_multi_window_comparison.py — Phase 8.

Runs Baseline and Baseline+AI across all 3 pinned windows (Hansika's
reproducible windows — recent_24h, prior_24h, prior_48h; see
research/download_sensitivity_windows.py), persisting each comparably
so the dashboard and Gauri's comparison harness can show results
across multiple windows, not a single one.

WHY THIS EXISTS
------------------
A single-window comparison isn't statistically meaningful on its own —
the same lesson Phase 5's spread tuning already learned. Confirmed
with Gauri and Hansika before building this (a methodology decision,
not purely a coding one) — turns Samarth's local, gitignored one-off
script (run_full_comparison.py, only ever meant to get numbers to hand
Hansika, never meant to ship) into real, permanent, reproducible code.

WHY recent_24h REUSES THE EXISTING SINGLE-WINDOW RUN NAMES
----------------------------------------------------------------
phase5_baseline and phase8_baseline_plus_ai (from
run_baseline_evaluation.py / run_comparison_evaluation.py) are already
THE canonical recent_24h results — referenced elsewhere as "the"
baseline and "the" single-window Phase 8 comparison. Re-running and
saving recent_24h under a DIFFERENT name here would create two
competing "truths" for the exact same window; this function reuses the
existing names for that one window instead of duplicating it.
"""
from core.strategy.baseline_market_maker import BaselineMarketMaker
from core.strategy.baseline_plus_ai import BaselinePlusAI
from research.backtest.run_baseline_evaluation import (
    BASELINE_RUN_NAME,
    run_strategy_evaluation,
)
from research.backtest.run_comparison_evaluation import COMPARISON_RUN_NAME

SYMBOL_PREFIX = "adausdt_candles_1m"

# (window_label, dataset_name, baseline_run_name, ai_run_name)
# recent_24h deliberately reuses the existing canonical single-window
# names — see module docstring for why.
WINDOWS = [
    ("recent_24h", f"{SYMBOL_PREFIX}_recent_24h", BASELINE_RUN_NAME, COMPARISON_RUN_NAME),
    ("prior_24h", f"{SYMBOL_PREFIX}_prior_24h", "phase8_baseline_prior_24h", "phase8_ai_prior_24h"),
    ("prior_48h", f"{SYMBOL_PREFIX}_prior_48h", "phase8_baseline_prior_48h", "phase8_ai_prior_48h"),
]


def run_multi_window_comparison() -> dict[str, dict[str, int]]:
    """
    Runs both Baseline and Baseline+AI against all 3 pinned windows.

    Returns a dict keyed by "{window_label}_baseline" / "{window_label}_ai"
    -> the version numbers save_backtest_run() assigned for that run,
    so a caller can confirm exactly what was (re)saved.
    """
    results = {}
    for window_label, dataset, baseline_run_name, ai_run_name in WINDOWS:
        print(f"\n=== Window: {window_label} (dataset={dataset!r}) ===")

        results[f"{window_label}_baseline"] = run_strategy_evaluation(
            lambda symbol: BaselineMarketMaker(symbol=symbol, base_half_spread=0.001),
            run_name=baseline_run_name,
            strategy_name="BaselineMarketMaker",
            dataset=dataset,
            extra_metadata={"phase": 8, "window": window_label, "dataset": dataset},
        )
        results[f"{window_label}_ai"] = run_strategy_evaluation(
            lambda symbol: BaselinePlusAI(symbol=symbol, base_half_spread=0.001),
            run_name=ai_run_name,
            strategy_name="BaselinePlusAI",
            dataset=dataset,
            extra_metadata={
                "phase": 8, "window": window_label, "dataset": dataset,
                "compares_against": baseline_run_name,
            },
        )

    return results


if __name__ == "__main__":
    run_multi_window_comparison()