"""
research/backtest/results.py

Persists a completed backtest run's results, using Phase 3's versioned
storage pattern (category="results", added in this phase) — Phase 4's
"Persist backtest run results" task.

WHY THIS LIVES IN research/, NOT core/portfolio/
----------------------------------------------------
core/portfolio/portfolio.py's Portfolio class is pure state-tracking
logic with no file I/O and no dependency on research/ — that's what
keeps it safe to import from anywhere, including core/ and services/.
Actually *saving* a completed run's results means calling
research.storage.save_dataset(), which only research/ code is allowed
to do (see tests/unit/test_research_boundary.py — core/ and services/
must never import from research/). So the boundary-crossing call lives
here, in research/, not inside core/portfolio/ itself.

The engine (wherever it ends up — likely Hansika's event loop) is
expected to: import Portfolio from core/, run the backtest, then hand
the finished Portfolio object to save_backtest_run() here, from
research/ code, to persist it.
"""
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from research.storage import save_dataset


def save_backtest_run(
    portfolio,  # core.portfolio.portfolio.Portfolio — not type-hinted directly
                # to avoid research/ needing a hard import-time dependency
                # on core/ (the boundary rule is one-directional: core/
                # and services/ can't import research/, but research/
                # importing core/ at call sites is fine and doesn't
                # create a live-pipeline dependency on research/ code)
    run_name: str,
    *,
    current_prices: dict[str, float] | None = None,
    strategy_name: str = "unknown",
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, int]:
    """
    Saves three datasets for one completed backtest run, all under the
    same run_name so they're easy to find together later:

    - "<run_name>_trades"   — the full trade log (one row per fill)
    - "<run_name>_equity"   — the equity curve (if any snapshots were recorded)
    - "<run_name>_summary"  — the final performance metrics, as a
                              single-row dataframe (so it's queryable
                              the same way as the other two, rather
                              than being a plain dict tucked into
                              metadata where it's harder to compare
                              across runs later)

    Returns the version number assigned to each of the three (a dict
    keyed by dataset name), so a caller can log/report exactly what
    got saved.
    """
    summary = portfolio.summary(current_prices)
    saved_at = datetime.now(timezone.utc).isoformat()

    shared_metadata = {
        "run_name": run_name,
        "strategy_name": strategy_name,
        "saved_at": saved_at,
        **(extra_metadata or {}),
    }

    versions = {}

    trades_df = pd.DataFrame(portfolio.trade_log)
    if trades_df.empty:
        # save_dataset() rejects empty dataframes (Phase 3 design) — a
        # run with zero fills is a real, valid outcome (e.g. a strategy
        # that decided to hold the whole time), so represent that
        # explicitly with a placeholder row rather than skipping the
        # save and leaving a silent gap in what's on disk for this run.
        trades_df = pd.DataFrame([{"note": "no trades occurred during this run"}])
    versions["trades"] = save_dataset(
        f"{run_name}_trades", trades_df, category="results",
        source="core.portfolio", metadata=shared_metadata,
    )

    equity_df = pd.DataFrame(portfolio.equity_curve)
    if equity_df.empty:
        equity_df = pd.DataFrame([{"note": "no equity snapshots were recorded during this run"}])
    versions["equity"] = save_dataset(
        f"{run_name}_equity", equity_df, category="results",
        source="core.portfolio", metadata=shared_metadata,
    )

    summary_df = pd.DataFrame([summary])
    versions["summary"] = save_dataset(
        f"{run_name}_summary", summary_df, category="results",
        source="core.portfolio", metadata=shared_metadata,
    )

    return versions