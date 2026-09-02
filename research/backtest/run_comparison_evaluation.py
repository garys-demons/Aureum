"""
research/backtest/run_comparison_evaluation.py — Phase 8.

Runs a "Baseline + AI" strategy variant through the same evaluation
run_baseline_evaluation.py already uses, and persists it under its own
fixed name so Gauri's comparison harness
(research/evaluation/comparison_harness.py) can load and compare it
against phase5_baseline — both already work with any run saved via
save_backtest_run(), no changes needed there.

NOT RUNNABLE YET
--------------------
Samarth's Baseline+AI strategy variant (Phase 8 task: "wrap or extend
BaselineMarketMaker to consult the regime classifier before quoting")
doesn't exist as of this file. run_comparison_evaluation() below is
written and ready, but its import of the real variant is commented out
until that class exists — importing something that doesn't exist would
break every other test in this file at collection time, not just the
one that needs it. Once Samarth's class exists (likely something like
core.strategy.baseline_plus_ai.BaselinePlusAI), uncomment the import
and the strategy_factory lambda below; nothing else needs to change —
run_strategy_evaluation() already handles any strategy sharing
BaselineMarketMaker's interface (decide(), record_fill(), .inventory).
"""
from core.strategy.baseline_plus_ai import BaselinePlusAI  
from research.backtest.run_baseline_evaluation import (
    BASELINE_DATASET,
    run_strategy_evaluation,
)

COMPARISON_RUN_NAME = "phase8_baseline_plus_ai"


def run_comparison_evaluation() -> dict[str, int]:
    """
    Runs the Baseline+AI variant against the same fixed dataset the
    baseline used, and persists it under COMPARISON_RUN_NAME —
    directly comparable via Gauri's comparison_harness.py, which reads
    any run's "<run_name>_summary" the same way regardless of which
    strategy produced it.
    """
    return run_strategy_evaluation(
        lambda symbol: BaselinePlusAI(symbol=symbol, base_half_spread=0.001),
        run_name=COMPARISON_RUN_NAME,
        strategy_name="BaselinePlusAI",
        dataset=BASELINE_DATASET,
        extra_metadata={"phase": 8, "compares_against": "phase5_baseline", "dataset": BASELINE_DATASET},
    )


if __name__ == "__main__":
    run_comparison_evaluation()
WINDOWS = [
    "adausdt_candles_1m_recent_24h",
    "adausdt_candles_1m_prior_24h",
    "adausdt_candles_1m_prior_48h",
]


def run_comparison_across_windows() -> dict[str, dict[str, int]]:
    """
    Runs both BaselineMarketMaker and BaselinePlusAI across all 3
    pinned windows, not just one - a single window's trade count
    (2-4 trades) is too thin to support any real conclusion, same
    lesson Phase 5's spread-tuning investigation already taught.

    Formalizes what was previously a local-only, unmerged script -
    agreed with Gauri and Hansika as the real Phase 8 methodology
    before this was written.
    """
    from core.strategy.baseline_market_maker import BaselineMarketMaker

    results = {}
    for window in WINDOWS:
        suffix = window.replace("adausdt_candles_1m_", "")

        results[f"baseline_{suffix}"] = run_strategy_evaluation(
            lambda symbol: BaselineMarketMaker(symbol=symbol, base_half_spread=0.001),
            run_name=f"phase8_compare_baseline_{suffix}",
            strategy_name="BaselineMarketMaker",
            dataset=window,
            extra_metadata={"phase": 8, "window": suffix},
        )
        results[f"ai_{suffix}"] = run_strategy_evaluation(
            lambda symbol: BaselinePlusAI(symbol=symbol, base_half_spread=0.001),
            run_name=f"phase8_compare_ai_{suffix}",
            strategy_name="BaselinePlusAI",
            dataset=window,
            extra_metadata={"phase": 8, "window": suffix},
        )
    return results


if __name__ == "__main__":
    run_comparison_across_windows()