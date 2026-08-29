"""
Tests for Phase 7's historical retrieval module.

The index-alignment logic (mapping rolling_volatility's and rsi's
different-length, different-offset outputs back onto a shared position
in `prices`) is the part most likely to hide a subtle bug, so it gets
the most direct scrutiny here — via test_price_index_alignment_is_exact,
not just end-to-end behaviour checks.
"""
import pytest

from core.ai_reasoning.historical_retrieval import (
    HistoricalMatch,
    retrieve_similar_conditions,
)


def make_prices(n: int = 100, seed_pattern: str = "gentle") -> list[float]:
    """Deterministic, varied synthetic series so distance ordering is meaningful."""
    prices, price = [], 0.20
    for i in range(n):
        if seed_pattern == "gentle":
            price *= 1.0002 if i % 3 else 0.9998
        elif seed_pattern == "volatile":
            price *= 1.02 if i % 2 == 0 else 0.98
        prices.append(price)
    return prices


def test_empty_history_returns_no_matches():
    matches = retrieve_similar_conditions([], current_volatility=0.001, current_rsi=50.0)
    assert matches == []


def test_insufficient_history_returns_no_matches_not_a_guess():
    short = make_prices(10)
    matches = retrieve_similar_conditions(short, current_volatility=0.001, current_rsi=50.0)
    assert matches == []


def test_returns_at_most_top_n_matches():
    prices = make_prices(200)
    matches = retrieve_similar_conditions(
        prices, current_volatility=0.001, current_rsi=50.0, top_n=3
    )
    assert len(matches) <= 3


def test_matches_sorted_by_ascending_distance():
    prices = make_prices(200, "volatile")
    matches = retrieve_similar_conditions(
        prices, current_volatility=0.01, current_rsi=50.0, top_n=10
    )
    distances = [m.distance for m in matches]
    assert distances == sorted(distances)


def test_exact_match_has_near_zero_distance():
    """
    Search using a REAL historical point's own (vol, rsi) as the query —
    that exact point should come back as the closest (or tied-closest)
    match, distance ~0.
    """
    prices = make_prices(200, "volatile")
    from core.features.feature_engine import rolling_volatility, rsi as rsi_fn, simple_returns

    returns = simple_returns(prices)
    vol_series = rolling_volatility(returns, window=20)
    rsi_series = rsi_fn(prices, window=14)

    # Pick a point comfortably inside both series.
    probe_vi = 50
    probe_price_idx = probe_vi + 20
    probe_ri = probe_price_idx - 14
    query_vol = vol_series[probe_vi]
    query_rsi = rsi_series[probe_ri]

    matches = retrieve_similar_conditions(
        prices, current_volatility=query_vol, current_rsi=query_rsi, top_n=1
    )
    assert len(matches) == 1
    assert matches[0].distance == pytest.approx(0.0, abs=1e-6)
    assert matches[0].index == probe_price_idx


def test_price_index_alignment_is_exact():
    """
    Direct check on the alignment logic itself: a match's reported
    volatility/rsi must equal what the feature functions ACTUALLY
    produce at that exact price index, not an off-by-one neighbour.
    """
    prices = make_prices(150, "volatile")
    from core.features.feature_engine import rolling_volatility, rsi as rsi_fn, simple_returns

    returns = simple_returns(prices)
    vol_series = rolling_volatility(returns, window=20)
    rsi_series = rsi_fn(prices, window=14)

    matches = retrieve_similar_conditions(
        prices, current_volatility=0.02, current_rsi=30.0, top_n=5
    )
    for m in matches:
        expected_vol = vol_series[m.index - 20]
        expected_rsi = rsi_series[m.index - 14]
        assert m.volatility == pytest.approx(expected_vol)
        assert m.rsi_value == pytest.approx(expected_rsi)


def test_forward_return_is_none_near_end_of_history():
    """A match too close to the end of the series can't have a forward
    return measured - must be None, never a fabricated number."""
    prices = make_prices(60)
    matches = retrieve_similar_conditions(
        prices, current_volatility=0.001, current_rsi=50.0, forward_horizon=5, top_n=50
    )
    near_end = [m for m in matches if m.index >= len(prices) - 5]
    assert all(m.forward_return is None for m in near_end)


def test_forward_return_is_computed_when_available():
    prices = make_prices(200)
    matches = retrieve_similar_conditions(
        prices, current_volatility=0.001, current_rsi=50.0, forward_horizon=5, top_n=50
    )
    with_horizon = [m for m in matches if m.index < len(prices) - 5]
    assert with_horizon  # there should be at least some
    assert any(m.forward_return is not None for m in with_horizon)


def test_forward_return_hand_calculated():
    """
    Deterministic price path so the forward return can be verified by
    hand: prices double every step starting at index 50, so the
    5-step-forward return from index 50 is exactly 2^5 - 1 = 31.0
    (3100%) — an extreme but exactly checkable case.
    """
    prices = [0.20] * 50 + [0.20 * (2 ** i) for i in range(30)]
    matches = retrieve_similar_conditions(
        prices, current_volatility=0.0, current_rsi=50.0, forward_horizon=5, top_n=200
    )
    target = next((m for m in matches if m.index == 50), None)
    assert target is not None
    assert target.forward_return == pytest.approx(31.0, rel=1e-6)


def test_result_is_immutable():
    prices = make_prices(150)
    matches = retrieve_similar_conditions(prices, current_volatility=0.001, current_rsi=50.0)
    if matches:
        with pytest.raises(Exception):
            matches[0].distance = 999.0


def test_flat_series_does_not_crash_on_zero_range_normalization():
    """Regression guard for the _normalize division-by-zero case."""
    prices = [0.20] * 100
    matches = retrieve_similar_conditions(prices, current_volatility=0.0, current_rsi=100.0)
    # Should not raise; may return matches with distance 0 since everything is identical.
    for m in matches:
        assert m.distance == pytest.approx(0.0)