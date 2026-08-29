"""
Historical retrieval — Phase 7's second structured reasoning component.

ZERO LIVE INFLUENCE: same rule as regime_classifier.py, enforced by the
same structural test (test_ai_reasoning_isolation.py). This module
finds and describes historical precedent; it never places an order.

WHAT THIS ACTUALLY DOES
------------------------
Given the current market conditions (volatility, RSI — same features
the regime classifier already uses), find past moments in history that
looked similar, and report what happened afterward. "Similar
conditions, but we don't know the outcome" is not useful on its own —
the forward outcome is the entire point of retrieval.

HONEST LIMITATION — STATE THIS EVERY TIME THIS MODULE IS USED
---------------------------------------------------------------
The available history is a few days of ADA testnet data (~5,700
20-period windows across the three Phase 5 datasets). That is a very
thin sample for "historical precedent." This module is mechanically
correct and a legitimate first version, but its output should be read
as "here is what a small sample of somewhat-similar past moments did
next," not as a statistically robust prediction. Phase 8 must account
for this when comparing against the baseline — do not let a small
sample size dress up as confidence it hasn't earned.

DISTANCE METRIC
----------------
Simple normalised Euclidean distance over (volatility, rsi). Both
features are min-max normalised against the SAME historical dataset
being searched, so neither dominates just because it happens to have
larger raw units. This is deliberately simple, matching the same
principle used for the regime classifier's thresholds — a defensible
first version, not a claim of sophistication.
"""
from dataclasses import dataclass

from core.features.feature_engine import rolling_volatility, rsi, simple_returns


@dataclass(frozen=True)
class HistoricalMatch:
    """
    One retrieved precedent. `index` is the position in the searched
    price series (not a timestamp — callers with real timestamps must
    map this back themselves; this module only knows about the price
    list it was given).
    """
    index: int
    distance: float
    volatility: float
    rsi_value: float
    forward_return: float | None  # None if too close to the end of history to measure


def _normalize(values: list[float]) -> list[float]:
    """Min-max to [0, 1]. Returns all-zero if the series has no range,
    rather than dividing by zero."""
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [0.0] * len(values)
    return [(v - lo) / span for v in values]


def retrieve_similar_conditions(
    prices: list[float],
    *,
    current_volatility: float,
    current_rsi: float,
    volatility_window: int = 20,
    rsi_window: int = 14,
    forward_horizon: int = 5,
    top_n: int = 5,
) -> list[HistoricalMatch]:
    """
    Search `prices` for historical points whose (volatility, rsi) most
    closely resemble (current_volatility, current_rsi), and report
    each match's forward return over `forward_horizon` steps.

    No look-ahead in the SEARCH itself: every candidate point's own
    volatility/rsi is computed only from prices up to and including
    that point. The FORWARD RETURN is deliberately the one place this
    module looks ahead — that's the entire purpose of retrieval (what
    happened next), not a bias violation. It is never fed back into
    the features used for matching.

    Returns fewer than `top_n` matches if there is not enough history,
    rather than padding with anything invented.
    """
    returns = simple_returns(prices)
    vol_series = rolling_volatility(returns, window=volatility_window) if returns else []
    rsi_series = rsi(prices, window=rsi_window)

    # vol_series and rsi_series can differ in length from `prices` and
    # from each other, since each indicator has its own warm-up period.
    # Align to the shorter of the two so every candidate index has both
    # a valid volatility and a valid RSI value.
    usable_length = min(len(vol_series), len(rsi_series))
    if usable_length == 0:
        return []

    # rolling_volatility(returns, window) has length len(returns) -
    # window + 1 == len(prices) - window (since returns has len(prices)-1).
    # rsi(prices, window) has length len(prices) - window.
    # Both series' index 0 corresponds to a different offset into
    # `prices` depending on window size - map each series index back
    # to its true position in `prices` explicitly rather than assuming
    # they line up.
    vol_offset = volatility_window
    rsi_offset = rsi_window
    price_indices = []
    aligned_vol = []
    aligned_rsi = []
    for vi in range(len(vol_series)):
        price_idx = vi + vol_offset
        ri = price_idx - rsi_offset
        if 0 <= ri < len(rsi_series):
            price_indices.append(price_idx)
            aligned_vol.append(vol_series[vi])
            aligned_rsi.append(rsi_series[ri])

    if not price_indices:
        return []

    norm_vol = _normalize(aligned_vol + [current_volatility])
    norm_rsi = _normalize(aligned_rsi + [current_rsi])
    current_norm_vol, current_norm_rsi = norm_vol[-1], norm_rsi[-1]
    norm_vol, norm_rsi = norm_vol[:-1], norm_rsi[:-1]

    candidates = []
    for i, price_idx in enumerate(price_indices):
        dist = ((norm_vol[i] - current_norm_vol) ** 2 + (norm_rsi[i] - current_norm_rsi) ** 2) ** 0.5

        forward_idx = price_idx + forward_horizon
        forward_return = None
        if forward_idx < len(prices) and prices[price_idx] != 0:
            forward_return = (prices[forward_idx] - prices[price_idx]) / prices[price_idx]

        candidates.append(HistoricalMatch(
            index=price_idx,
            distance=dist,
            volatility=aligned_vol[i],
            rsi_value=aligned_rsi[i],
            forward_return=forward_return,
        ))

    candidates.sort(key=lambda m: m.distance)
    return candidates[:top_n]