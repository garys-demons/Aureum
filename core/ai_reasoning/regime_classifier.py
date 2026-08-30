"""
Market regime classifier — Phase 7's structured reasoning component.

ZERO LIVE INFLUENCE (Phase 7's load-bearing rule): this module reasons
about market state and returns a structured classification. It never
places an order, never adjusts a strategy, and never imports from
core.execution or core.risk. That boundary is enforced structurally by
tests/unit/test_ai_reasoning_isolation.py, not by convention.

WHY THESE REGIMES, SPECIFICALLY
-------------------------------
Not chosen generically. Phase 5's baseline evaluation found the market
maker lost money because a tight spread got run over by intra-candle
price movement — fills happened on the wrong side of a move, and fees
compounded across many small round trips. So the useful question for
this project is not "which way will price go" (hard, heavily competed)
but "are the baseline's assumptions currently holding?"

  HIGH_VOLATILITY -> they are not; the market maker is exposed
  TRENDING        -> they are not; quotes fill one-sided
  RANGING         -> they are; this is what market making is built for

Volatility is checked BEFORE direction on purpose: a violently trending
market is dangerous for the same reason a violently ranging one is, so
the volatility condition dominates.

RULE-BASED, NOT LEARNED — DELIBERATELY
--------------------------------------
Per the Phase 7 scope doc: "simple and honest beats complex and
unexplainable for a first pass." A learned model here would be harder
to evaluate against the baseline and harder to justify, with no
evidence yet that it would do better. This is a defensible first
version, not a placeholder — thresholds are documented and testable,
and Phase 8 can measure whether it adds value before anyone reaches
for something heavier.
"""
from dataclasses import dataclass
from enum import Enum

from core.features.feature_engine import rolling_volatility, rsi, simple_returns


class Regime(str, Enum):
    RANGING = "ranging"
    TRENDING = "trending"
    HIGH_VOLATILITY = "high_volatility"
    UNKNOWN = "unknown"  # not enough data to classify honestly

# Thresholds, set from MEASUREMENT not intuition.
#
# HIGH_VOLATILITY_THRESHOLD: the 95th percentile of ADA's real
# 20-period rolling volatility, measured across all three Phase 5
# windows (n=5700): median 0.001113, 90th 0.001763, 95th 0.001995,
# 99th 0.002784, max 0.003191. So "high volatility" means roughly the
# top 1-in-20 periods — unusual, but not vanishingly rare.
#
# An earlier value of 0.003 sat between the 99th percentile and the
# observed maximum, meaning this branch never fired on real data at
# all. Every unit test still passed, because they used synthetic price
# series — the dead branch was only caught by running the classifier
# against real history. Worth remembering before trusting any threshold
# that hasn't been measured.
#
# Still NOT validated against forward performance — whether this
# threshold actually predicts anything useful is explicitly Phase 8's
# question, not a claim made here.
HIGH_VOLATILITY_THRESHOLD = 0.002
RSI_TRENDING_DISTANCE = 20.0  # |rsi - 50| above this counts as trending

DEFAULT_VOLATILITY_WINDOW = 20
DEFAULT_RSI_WINDOW = 14


@dataclass(frozen=True)
class RegimeAssessment:
    """
    Structured output — machine-readable by design, so Phase 8 can
    compare it numerically rather than parsing prose.

    confidence: 0.0-1.0, how far the deciding metric sat beyond its
    threshold, normalised. Crude by construction — it measures
    "how clearly did this rule fire", NOT "how likely is this correct".
    Those are different things and conflating them would be dishonest.
    """
    regime: Regime
    confidence: float
    volatility: float | None
    rsi_value: float | None
    reason: str


def classify_regime(
    prices: list[float],
    *,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    rsi_window: int = DEFAULT_RSI_WINDOW,
    high_volatility_threshold: float = HIGH_VOLATILITY_THRESHOLD,
    rsi_trending_distance: float = RSI_TRENDING_DISTANCE,
) -> RegimeAssessment:
    """
    Classify the regime as of the LAST price in `prices`.

    No look-ahead by construction: only `prices` is consumed, and the
    assessment describes the final element. Callers must not pass
    prices that postdate the moment being assessed — the same rule
    Phase 3's feature audit established.

    Returns UNKNOWN rather than guessing when there is not enough
    history for either indicator.
    """
    returns = simple_returns(prices)

    vol_series = rolling_volatility(returns, window=volatility_window) if returns else []
    rsi_series = rsi(prices, window=rsi_window)

    latest_vol = vol_series[-1] if vol_series else None
    latest_rsi = rsi_series[-1] if rsi_series else None

    if latest_vol is None or latest_rsi is None:
        return RegimeAssessment(
            regime=Regime.UNKNOWN,
            confidence=0.0,
            volatility=latest_vol,
            rsi_value=latest_rsi,
            reason=(
                f"insufficient history: need >{volatility_window} returns and "
                f">{rsi_window} prices, got {len(returns)} returns / {len(prices)} prices"
            ),
        )

    # Volatility dominates — see module docstring.
    if latest_vol > high_volatility_threshold:
        excess = (latest_vol - high_volatility_threshold) / high_volatility_threshold
        return RegimeAssessment(
            regime=Regime.HIGH_VOLATILITY,
            confidence=max(0.05, min(1.0, excess)),
            volatility=latest_vol,
            rsi_value=latest_rsi,
            reason=f"volatility {latest_vol:.5f} exceeds threshold {high_volatility_threshold}",
        )

    rsi_distance = abs(latest_rsi - 50.0)
    if rsi_distance > rsi_trending_distance:
        # Max possible distance from 50 is 50, so normalise the excess
        # against the remaining room above the threshold.
        excess = (rsi_distance - rsi_trending_distance) / (50.0 - rsi_trending_distance)
        # Floor at 0.05: a rule that FIRED should never report zero
        # confidence — that reads as "no signal" when it actually means
        # "fired exactly at the threshold". Observed on real data: an
        # RSI of exactly 30.00 is exactly 20.0 from neutral, giving a
        # raw excess of 0.0.
        return RegimeAssessment(
            regime=Regime.TRENDING,
            confidence=max(0.05, min(1.0, excess)),
            volatility=latest_vol,
            rsi_value=latest_rsi,
            reason=f"RSI {latest_rsi:.2f} is {rsi_distance:.2f} from neutral (>{rsi_trending_distance})",
        )

    # Neither condition fired: calm and directionless.
    vol_headroom = 1.0 - (latest_vol / high_volatility_threshold)
    rsi_headroom = 1.0 - (rsi_distance / rsi_trending_distance)
    return RegimeAssessment(
        regime=Regime.RANGING,
        confidence=min(vol_headroom, rsi_headroom),
        volatility=latest_vol,
        rsi_value=latest_rsi,
        reason=(
            f"volatility {latest_vol:.5f} below {high_volatility_threshold} and "
            f"RSI {latest_rsi:.2f} within {rsi_trending_distance} of neutral"
        ),
    )