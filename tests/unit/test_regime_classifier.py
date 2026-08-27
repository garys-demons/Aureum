"""
Tests for the Phase 7 regime classifier.

Where a value is hand-calculable it is checked exactly. Where it
depends on the feature engine's internals (rolling volatility over
real-ish price paths), the test asserts the CLASSIFICATION and the
ORDERING of confidence rather than inventing a precise number — a
test that hardcodes a value nobody verified by hand is worse than
no test, because it looks rigorous while proving nothing.
"""
import pytest

from core.ai_reasoning.regime_classifier import (
    HIGH_VOLATILITY_THRESHOLD,
    RSI_TRENDING_DISTANCE,
    Regime,
    classify_regime,
)


def test_insufficient_history_returns_unknown_not_a_guess():
    """
    The honest failure mode: too little data must produce UNKNOWN,
    never a confident-looking classification built on nothing.
    """
    assessment = classify_regime([0.20, 0.21, 0.20])

    assert assessment.regime is Regime.UNKNOWN
    assert assessment.confidence == 0.0
    assert "insufficient history" in assessment.reason


def test_empty_price_list_returns_unknown():
    assessment = classify_regime([])
    assert assessment.regime is Regime.UNKNOWN


def test_flat_prices_classify_as_ranging():
    """
    A perfectly flat price series has zero volatility and, by the
    feature engine's own RSI convention, no losses and no gains.
    Whatever RSI it produces, volatility is 0.0, so this must never
    be HIGH_VOLATILITY.
    """
    prices = [0.20] * 60
    assessment = classify_regime(prices)

    assert assessment.regime is not Regime.HIGH_VOLATILITY
    assert assessment.volatility == pytest.approx(0.0)


def test_violent_price_swings_classify_as_high_volatility():
    """
    Alternating +5%/-5% moves produce rolling volatility far above the
    0.003 threshold — this is the Phase 5 failure condition (market
    maker gets run over), so it must be caught.
    """
    prices = []
    price = 0.20
    for i in range(60):
        price = price * (1.05 if i % 2 == 0 else 0.95)
        prices.append(price)

    assessment = classify_regime(prices)

    assert assessment.regime is Regime.HIGH_VOLATILITY
    assert assessment.volatility > HIGH_VOLATILITY_THRESHOLD
    assert "exceeds threshold" in assessment.reason


def test_steady_uptrend_classifies_as_trending():
    """
    Monotonic small increases: RSI saturates near 100 (all gains, no
    losses), while per-step volatility stays low. Must be TRENDING,
    not HIGH_VOLATILITY — the ordering of the checks matters here.
    """
    prices = [0.20 * (1.0005 ** i) for i in range(60)]
    assessment = classify_regime(prices)

    assert assessment.regime is Regime.TRENDING
    assert assessment.rsi_value is not None
    assert abs(assessment.rsi_value - 50.0) > RSI_TRENDING_DISTANCE


def test_steady_downtrend_also_classifies_as_trending():
    """Direction-agnostic: a sustained decline is equally 'trending'."""
    prices = [0.20 * (0.9995 ** i) for i in range(60)]
    assessment = classify_regime(prices)

    assert assessment.regime is Regime.TRENDING


def test_volatility_is_checked_before_trend():
    """
    A series that is BOTH trending and violently volatile must be
    reported as HIGH_VOLATILITY, per the documented precedence — a
    violent trend is dangerous for the volatility reason first.
    """
    prices = []
    price = 0.20
    for i in range(60):
        # Strong upward drift with large oscillation on top.
        price = price * (1.08 if i % 2 == 0 else 0.97)
        prices.append(price)

    assessment = classify_regime(prices)
    assert assessment.regime is Regime.HIGH_VOLATILITY


def test_confidence_is_between_zero_and_one():
    """Confidence is normalised; a value outside [0, 1] is a bug."""
    price = 0.20
    prices = []
    for i in range(60):
        price = price * (1.05 if i % 2 == 0 else 0.95)
        prices.append(price)

    assessment = classify_regime(prices)
    assert 0.0 <= assessment.confidence <= 1.0


def test_higher_volatility_gives_higher_confidence():
    """
    Ordering check rather than an invented absolute value: a more
    violent series should fire the HIGH_VOLATILITY rule more clearly
    than a marginally-over-threshold one.
    """
    def build(swing: float) -> list[float]:
        out, price = [], 0.20
        for i in range(60):
            price = price * ((1 + swing) if i % 2 == 0 else (1 - swing))
            out.append(price)
        return out

    mild = classify_regime(build(0.005))
    extreme = classify_regime(build(0.10))

    assert mild.regime is Regime.HIGH_VOLATILITY
    assert extreme.regime is Regime.HIGH_VOLATILITY
    assert extreme.confidence >= mild.confidence


def test_thresholds_are_overridable_for_sensitivity_analysis():
    """
    Phase 8 will need to sweep these — confirm they're parameters,
    not hardcoded constants baked into the logic.
    """
    prices = [0.20] * 60

    strict = classify_regime(prices, high_volatility_threshold=-1.0)
    assert strict.regime is Regime.HIGH_VOLATILITY  # everything exceeds -1.0


def test_assessment_is_immutable():
    """
    Frozen dataclass: a downstream consumer must not be able to mutate
    a recorded assessment after the fact, which would corrupt any
    Phase 8 comparison built on persisted results.
    """
    assessment = classify_regime([0.20] * 60)
    with pytest.raises(Exception):
        assessment.regime = Regime.TRENDING