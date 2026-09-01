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
# from core.strategy.baseline_plus_ai import BaselinePlusAI  # uncomment once this exists

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
    raise NotImplementedError(
        "Samarth's Baseline+AI strategy variant (core.strategy.baseline_plus_ai, "
        "or wherever it ends up) doesn't exist yet. Once it does: uncomment the "
        "import above, and replace this function body with:\n\n"
        "    return run_strategy_evaluation(\n"
        "        lambda symbol: BaselinePlusAI(symbol=symbol, base_half_spread=0.001),\n"
        "        run_name=COMPARISON_RUN_NAME,\n"
        "        strategy_name='BaselinePlusAI',\n"
        "        dataset=BASELINE_DATASET,\n"
        "        extra_metadata={'phase': 8, 'compares_against': 'phase5_baseline', "
        "'dataset': BASELINE_DATASET},\n"
        "    )\n\n"
        "See tests/unit/test_run_comparison_evaluation.py for a working, verified "
        "demonstration of this exact pattern against a stand-in strategy."
    )


if __name__ == "__main__":
    run_comparison_evaluation()