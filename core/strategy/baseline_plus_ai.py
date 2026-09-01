"""
Baseline + AI — Phase 8's comparison variant.

Per the Baseline-First Rule's stated methodology (Baseline -> Baseline
+ Feature -> Baseline + AI), this wraps BaselineMarketMaker unchanged
and adds exactly one AI-informed decision: consult the Phase 7 regime
classifier before quoting, and skip quoting entirely during
HIGH_VOLATILITY.

WHY THIS SPECIFIC RULE, FIRST
------------------------------
Phase 5 found the baseline's actual failure mode: tight spreads got
run over during high-volatility moves, producing consistent small
losses (4-7% win rate before retuning). This variant targets that
exact, known failure mode directly - it does not try to predict price
direction (hard, unproven) or improve every regime at once. A narrow,
explainable first hypothesis is worth more here than a broad,
unverifiable one.

STILL BACKTEST-ONLY
--------------------
This is not a live-trading change. Phase 7's "zero live influence"
rule was specific to that phase's isolation requirement; this class
still only implements StrategyInterface and is only ever run through
the backtester (research/backtest/), same as BaselineMarketMaker
itself. Nothing here touches core.execution or core.risk.

NO LOOK-AHEAD
--------------
The regime assessment consulted on each decide() call is computed only
from the price history available UP TO the current market_data point -
identical discipline to how BaselineMarketMaker's own fair-price logic
already works, and to how the regime classifier itself is documented
to behave. See test_no_lookahead_in_regime_consultation for the
explicit check.
"""
from core.ai_reasoning.regime_classifier import Regime, classify_regime
from core.strategy.base import Signal
from core.strategy.baseline_market_maker import BaselineMarketMaker


class BaselinePlusAI:
    """
    Same public shape as BaselineMarketMaker (symbol, base_half_spread,
    inventory, decide(), record_fill()) — required by
    run_strategy_evaluation(), confirmed against
    tests/unit/test_run_comparison_evaluation.py's FakeAlwaysPausedVariant.
    Wraps rather than subclasses, so the AI-gating logic stays visibly
    separate from the baseline's own quoting math - the diff between
    "baseline" and "baseline + AI" should be readable in this file
    alone, not scattered through BaselineMarketMaker's internals.
    """

    def __init__(self, symbol: str, base_half_spread: float = 0.001):
        self._inner = BaselineMarketMaker(symbol=symbol, base_half_spread=base_half_spread)
        self.symbol = symbol
        # Rolling price history for regime assessment. Deliberately
        # separate from anything BaselineMarketMaker tracks internally -
        # this class owns its own view of "what's happened so far",
        # built up one price at a time as decide() is called, never
        # backfilled from future data.
        self._price_history: list[float] = []
        self._regime_history: list[Regime] = []  # for later inspection/logging

    @property
    def inventory(self) -> float:
        return self._inner.inventory

    def decide(self, market_data: dict) -> list[Signal]:
        price = market_data.get("price")
        if price is not None:
            self._price_history.append(price)

        assessment = classify_regime(self._price_history)
        self._regime_history.append(assessment.regime)

        if assessment.regime is Regime.HIGH_VOLATILITY:
            # The one rule this variant adds: skip quoting entirely
            # rather than get run over, per the Phase 5 failure mode
            # this is specifically designed to address.
            return []

        return self._inner.decide(market_data)

    def record_fill(self, action: str, quantity: float) -> None:
        self._inner.record_fill(action, quantity)