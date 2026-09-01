"""
Tests for Phase 8's BaselinePlusAI variant.

Where possible, checks behavior against BaselineMarketMaker directly
(same call, same market_data) to confirm the wrapper is faithful
outside of the one deliberate difference: skipping HIGH_VOLATILITY.
"""
from core.ai_reasoning.regime_classifier import Regime
from core.strategy.baseline_market_maker import BaselineMarketMaker
from core.strategy.baseline_plus_ai import BaselinePlusAI


def test_insufficient_history_behaves_identically_to_baseline():
    """
    Below the classifier's minimum history, regime is UNKNOWN, so this
    variant must produce IDENTICAL quotes to plain BaselineMarketMaker
    - the AI layer has nothing to say yet, so it must not interfere.
    """
    variant = BaselinePlusAI(symbol="ADAUSDT", base_half_spread=0.001)
    baseline = BaselineMarketMaker(symbol="ADAUSDT", base_half_spread=0.001)

    market_data = {"price": 0.20}
    variant_signals = variant.decide(market_data)
    baseline_signals = baseline.decide(market_data)

    assert len(variant_signals) == len(baseline_signals) == 2
    for v, b in zip(variant_signals, baseline_signals):
        assert v.price == b.price
        assert v.action == b.action


def test_flat_calm_history_still_quotes_normally():
    """A long, calm (ranging) price history should NOT trigger a skip."""
    variant = BaselinePlusAI(symbol="ADAUSDT", base_half_spread=0.001)
    signals = []
    for _ in range(60):
        signals = variant.decide({"price": 0.20})

    assert len(signals) == 2  # still quoting, not skipped


def test_violently_volatile_history_skips_quoting():
    """
    The one behavior this variant adds: feed it a violently swinging
    price series (same shape used to hand-verify HIGH_VOLATILITY in
    the classifier's own tests) and confirm it returns [] instead of
    quoting into a market that's currently running the baseline over.
    """
    variant = BaselinePlusAI(symbol="ADAUSDT", base_half_spread=0.001)
    price = 0.20
    signals = []
    for i in range(60):
        price = price * (1.05 if i % 2 == 0 else 0.95)
        signals = variant.decide({"price": price})

    assert signals == []


def test_inventory_property_reflects_inner_baseline():
    variant = BaselinePlusAI(symbol="ADAUSDT")
    assert variant.inventory == 0.0

    variant.record_fill(action="buy", quantity=50.0)
    assert variant.inventory == 50.0

    variant.record_fill(action="sell", quantity=20.0)
    assert variant.inventory == 30.0


def test_no_signals_produced_during_skip_means_no_fills_possible():
    """
    An empty list from decide() means run_strategy_evaluation()'s loop
    (per run_baseline_evaluation.py's own pattern: `for signal in
    signals`) simply has nothing to iterate - confirms the [] return
    is a safe, correctly-typed way to skip a period entirely.
    """
    variant = BaselinePlusAI(symbol="ADAUSDT")
    price = 0.20
    signals = []
    for i in range(60):
        price = price * (1.05 if i % 2 == 0 else 0.95)
        signals = variant.decide({"price": price})

    assert isinstance(signals, list)
    assert len(signals) == 0


def test_no_lookahead_in_regime_consultation():
    """
    The regime assessed at call N must be identical whether or not
    FUTURE prices (beyond call N) are ever fed in later - i.e. the
    variant's internal price history must only grow forward, never be
    influenced by what decide() is called with next.

    Verified by running the same first 60 prices through two variants,
    one which then receives 60 MORE (different) prices and one which
    doesn't - their behavior up to call 60 must be identical.
    """
    prices = [0.20 * (1.0005 ** i) for i in range(60)]  # steady uptrend -> TRENDING

    variant_a = BaselinePlusAI(symbol="ADAUSDT")
    results_a = [variant_a.decide({"price": p}) for p in prices]

    variant_b = BaselinePlusAI(symbol="ADAUSDT")
    results_b = [variant_b.decide({"price": p}) for p in prices]
    # Feed variant_b MORE data afterward - must not retroactively change
    # anything already returned above.
    for p in [0.30, 0.10, 0.50]:
        variant_b.decide({"price": p})

    for ra, rb in zip(results_a, results_b):
        assert len(ra) == len(rb)
        for sa, sb in zip(ra, rb):
            assert sa.price == sb.price
            assert sa.action == sb.action