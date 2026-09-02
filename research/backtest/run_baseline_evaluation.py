"""
research/backtest/run_baseline_evaluation.py

Produces THE Phase 5 baseline evaluation run — the permanent reference
point future phases (Phase 8's AI comparison) will compare against.

WHY THIS DIDN'T ALREADY EXIST
--------------------------------
Two other scripts already run the baseline strategy against real data
(research/run_sample_backtest.py, research/parameter_sensitivity.py),
but neither computes real PnL:
- run_sample_backtest.py only counts signal actions, no fills at all
- parameter_sensitivity.py explicitly assumes "every quote fills" —
  documented there as a deliberate simplification for isolating
  parameter sensitivity, not for measuring realistic performance

This is the first script to connect the pieces needed for a REAL
result: core.backtest.candle_fill_model (simulates fills against
candle data — the baseline dataset has no order-book events at all,
so paper_exchange's book-based matching can't be used here),
core.portfolio.Portfolio (real cash/PnL/drawdown tracking), and
research.backtest.results.save_backtest_run (versioned persistence).

WHY THIS DOESN'T CALL BacktestEngine.run() DIRECTLY
-------------------------------------------------------
engine.run() returns one flat list of signals for the whole run. Since
the baseline strategy returns [bid, ask] per candle, that flat list
loses the 1:1 correspondence between "this signal" and "the candle it
was quoted against" — exactly what's needed to check whether a candle's
price range actually touched the quote. Positionally zipping candles
against engine.signals afterward would be wrong (2 signals per candle,
not 1). So this script calls strategy.decide() directly, in its own
chronological one-at-a-time loop — the same no-look-ahead principle
engine.py documents (process events strictly in order, decide() only
ever sees the current event) is preserved here by construction, just
not delegated to the BacktestEngine class itself.

Worth flagging to the team: engine.py could support this more directly
with a per-event callback hook, rather than every fill-simulating
caller needing its own copy of the chronological loop. Not changed
here — that's Hansika's file, and this works correctly without it.

WHY run_name AND BASELINE_DATASET ARE FIXED CONSTANTS
----------------------------------------------------------
Per the task: "Make sure this run is clearly labeled as THE baseline —
the reference point Phase 8's AI comparison will need to find and
use." A fixed, documented name means Phase 8 can reliably do
load_dataset("results", f"{BASELINE_RUN_NAME}_summary") without
guessing which of possibly-many runs is "the" one.
"""
from datetime import datetime, timezone

import pandas as pd

from core.backtest.candle_fill_model import Candle as FillModelCandle
from core.backtest.candle_fill_model import fill_limit_order_candle
from core.portfolio.portfolio import Fill as PortfolioFill
from core.portfolio.portfolio import Portfolio
from core.strategy.baseline_market_maker import BaselineMarketMaker
from research.backtest.results import save_backtest_run
from research.storage import load_dataset
from services.market_data.models import Candle
from core.risk.risk_engine import RiskEngine
from core.risk.kill_switch import KillSwitch

BASELINE_RUN_NAME = "phase5_baseline"

# The specific historical window used for the official evaluation run.
# "Recent 24h" is the most representative, most-recently-downloaded
# complete window already saved via Phase 5's parameter-sensitivity
# work — a deliberate choice, not an arbitrary default.
BASELINE_DATASET = "adausdt_candles_1m_recent_24h"
STARTING_CASH = 10_000.0

# Verified against Binance's real published fee schedule (confirmed
# via web search, cross-checked across multiple independent sources):
# regular-tier spot maker fee is 0.1% (0.001), not 0.05%. The original
# 0.0005 was copied from paper_exchange.py's own explicitly-marked
# placeholder ("confirm real schedule with team") — never actually
# confirmed until now. This has been silently understating fees on
# every evaluation run since Phase 5 (phase5_baseline,
# phase8_baseline_plus_ai, and all 3-window comparison runs) — all of
# those persisted results need re-running with this corrected rate
# before being treated as conclusive. Flagged to Gauri: paper_exchange.py
# has the identical wrong placeholder, unaffected by this fix since it's
# a separate file, not exercised by this candle-based backtest path.
MAKER_FEE_RATE = 0.001
BACKTEST_MAX_ORDER_SIZE = 100.0
BACKTEST_MAX_POSITION = 500.0


def dataframe_to_candles(df: pd.DataFrame) -> list[Candle]:
    return [Candle(**row) for row in df.to_dict(orient="records")]


def run_strategy_evaluation(
    strategy_factory,
    *,
    run_name: str,
    strategy_name: str,
    dataset: str = BASELINE_DATASET,
    extra_metadata: dict | None = None,
) -> dict[str, int]:
    """
    Phase 8: the generic core extracted from run_baseline_evaluation()
    below, so any strategy sharing BaselineMarketMaker's interface
    (decide(), record_fill(), an .inventory attribute) can be run and
    persisted the same way, comparably, via the same
    save_backtest_run() -> research.storage path Gauri's evaluation
    harness (research/evaluation/comparison_harness.py) already reads
    from generically.

    strategy_factory is a callable(symbol) -> strategy instance, not an
    already-built strategy — the real symbol is only known AFTER the
    dataset loads (see below), and BaselineMarketMaker (and presumably
    any variant of it) needs symbol at construction time. This mirrors
    exactly how run_baseline_evaluation() already worked before this
    refactor: load data first, determine symbol from it, construct the
    strategy after.

    run_baseline_evaluation() below is unchanged in its own public
    behavior — it's now a thin wrapper calling this function, kept
    working exactly as it did before this refactor (verified: same
    synthetic-data test produces byte-identical results pre/post).
    """
    df = load_dataset("raw", dataset)
    candles = dataframe_to_candles(df)
    print(f"Loaded {len(candles)} candles from {dataset!r}")

    sorted_candles = sorted(candles, key=lambda c: c.close_time)
    symbol = sorted_candles[0].symbol

    strategy = strategy_factory(symbol)
    portfolio = Portfolio(starting_cash=STARTING_CASH)
    risk_engine = RiskEngine(
        kill_switch=KillSwitch(),
        max_order_size=BACKTEST_MAX_ORDER_SIZE,
        max_position=BACKTEST_MAX_POSITION,
    )

    last_price = None
    for candle in sorted_candles:
        # Only fields derivable from THIS candle — no look-ahead,
        # matching engine.py's own _build_market_data() shape.
        market_data = {
            "symbol": candle.symbol,
            "timestamp": candle.close_time,
            "event_type": candle.event_type,
            "price": candle.close,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "volume": candle.volume,
        }
        last_price = candle.close

        result = strategy.decide(market_data)
        signals = result if isinstance(result, list) else [result]

        fill_candle = FillModelCandle(
            open=candle.open, high=candle.high, low=candle.low, close=candle.close,
        )
        occurred_at = datetime.fromtimestamp(candle.close_time / 1000, tz=timezone.utc)

        for signal in signals:
            if signal.action == "hold" or signal.price is None or signal.quantity is None:
                continue

            # Phase 6: same Strategy -> Risk -> Execution gate the live
            # path uses. Deliberately NOT persisted to the audit trail
            # here (that's a live-trading concern) - a backtest run can
            # produce thousands of checks per run; persisting all of
            # them would pollute audit_log, which is meant to record
            # real trading activity, not backtest iterations.
            allowed = risk_engine.check(
                action=signal.action,
                quantity=signal.quantity,
                current_inventory=strategy.inventory,
            )
            if not allowed:
                continue  # risk-rejected, never reaches the fill model

            fill_result = fill_limit_order_candle(
                fill_candle, side=signal.action,
                quantity=signal.quantity, limit_price=signal.price,
            )
            if fill_result is None:
                continue  # quote never touched during this candle — no fill

            fill_price, fill_quantity = fill_result
            fee = fill_price * fill_quantity * MAKER_FEE_RATE
            portfolio.process_fill(PortfolioFill(
                symbol=signal.symbol, side=signal.action, quantity=fill_quantity,
                price=fill_price, fee=fee, timestamp=occurred_at,
            ))
            # Keep the strategy's own inventory tracking in sync before
            # its next decide() call — required by BaselineMarketMaker's
            # own docstring ("updated externally via record_fill()").
            strategy.record_fill(action=signal.action, quantity=fill_quantity)

        portfolio.record_equity_snapshot(occurred_at, {symbol: candle.close})

    print(f"Processed {len(sorted_candles)} candles, {len(portfolio.trade_log)} fills")

    current_prices = {symbol: last_price} if last_price is not None else None
    summary = portfolio.summary(current_prices)
    print(f"Summary: {summary}")

    versions = save_backtest_run(
        portfolio,
        run_name,
        current_prices=current_prices,
        strategy_name=strategy_name,
        extra_metadata=extra_metadata or {},
    )
    print(f"Saved run as {run_name!r}, versions: {versions}")
    return versions


def run_baseline_evaluation() -> dict[str, int]:
    """
    Runs BaselineMarketMaker against the real ADA baseline dataset,
    simulating fills via the candle-close fill model, tracking real
    PnL through Portfolio, and persisting the result under the fixed
    BASELINE_RUN_NAME so Phase 8 can find it reliably later.

    Returns the version numbers assigned to each persisted dataset
    (trades/equity/summary) — same shape save_backtest_run() returns.
    """
    return run_strategy_evaluation(
        lambda symbol: BaselineMarketMaker(symbol=symbol, base_half_spread=0.001),
        run_name=BASELINE_RUN_NAME,
        strategy_name="BaselineMarketMaker",
        extra_metadata={
            "is_baseline": True,
            "phase": 5,
            "dataset": BASELINE_DATASET,
            "fill_model": "candle_close (no order-book data available for this symbol)",
        },
    )


if __name__ == "__main__":
    run_baseline_evaluation()