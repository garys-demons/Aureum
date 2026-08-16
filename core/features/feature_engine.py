"""
Feature engine — pure functions computing quant features from historical
price series. No side effects, no lookahead: every function only uses
data up to and including the current point, never future data.
"""
import math
from services.market_data.order_book import OrderBook
from core.metrics.microstructure import order_book_imbalance


def simple_returns(prices: list[float]) -> list[float]:
    """
    Percent change from each price to the next.

    Given N prices, returns N-1 values (you can't compute a return for
    the very first price — there's nothing before it to compare against).

    Example: prices = [100, 105, 103]
             -> [(105-100)/100, (103-105)/105] = [0.05, -0.019047...]
    """
    if len(prices) < 2:
        return []

    return [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
    ]


def log_returns(prices: list[float]) -> list[float]:
    """
    Natural-log return from each price to the next: ln(price_t / price_t-1).

    Same shape as simple_returns (N prices -> N-1 returns), just a
    different formula preferred in quant finance because log returns
    are additive across time periods.
    """
    if len(prices) < 2:
        return []

    return [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
    ]

def rolling_volatility(returns: list[float], window: int) -> list[float]:
    """
    Rolling realized volatility: standard deviation of returns over a
    sliding window of size `window`.

    Given N returns, produces N - window + 1 volatility values — one per
    window position, starting from the first full window (never a
    partial one, since a partial window would silently compute
    volatility over incomplete data).

    Uses SAMPLE standard deviation (divides by window - 1, not window) —
    the standard convention for a rolling volatility estimate.

    Example: returns = [0.01, -0.02, 0.03, 0.01], window = 2
             -> vol of [0.01, -0.02], vol of [-0.02, 0.03], vol of [0.03, 0.01]
    """
    if window < 2:
        raise ValueError("window must be at least 2 — can't compute std dev of a single value")
    if len(returns) < window:
        return []

    result = []
    for i in range(len(returns) - window + 1):
        chunk = returns[i:i + window]
        mean = sum(chunk) / len(chunk)
        squared_diffs = [(r - mean) ** 2 for r in chunk]
        variance = sum(squared_diffs) / (len(chunk) - 1)  # sample variance
        result.append(variance ** 0.5)

    return result

def rsi(prices: list[float], window: int = 14) -> list[float]:
    """
    Relative Strength Index — standard momentum oscillator, 0-100.

    Given N prices, first computes N-1 price changes, then produces
    (N-1) - window + 1 RSI values, one per full window of changes.

    Uses simple (non-exponential) moving averages of gains/losses —
    the classic/original RSI formulation. Wilder's smoothed version
    exists too, but simple averaging is the more common starting point
    and easier to hand-verify.
    """
    if window < 1:
        raise ValueError("window must be at least 1")

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    if len(changes) < window:
        return []

    result = []
    for i in range(len(changes) - window + 1):
        chunk = changes[i:i + window]
        gains = [c for c in chunk if c > 0]
        losses = [-c for c in chunk if c < 0]  # store losses as positive numbers

        avg_gain = sum(gains) / window
        avg_loss = sum(losses) / window

        if avg_loss == 0:
            result.append(100.0)  # no losses at all -> maxed out RSI
            continue

        rs = avg_gain / avg_loss
        result.append(100 - (100 / (1 + rs)))

    return result

def historical_spread(books: list[OrderBook]) -> list[float | None]:
    """
    Spread (ask - bid) computed across a list of historical OrderBook
    snapshots, in order. Reuses OrderBook.spread() directly — same
    formula as the live version, just applied one snapshot at a time.

    Returns None for any snapshot where spread can't be computed
    (e.g. one side of the book was empty at that point in time) —
    matches spread()'s own behavior rather than silently skipping it,
    so the output list stays the same length as the input.
    """
    return [book.spread() for book in books]


def historical_order_book_imbalance(
    books: list[OrderBook], levels: int | None = None
) -> list[float | None]:
    """
    Order-book imbalance computed across a list of historical OrderBook
    snapshots, in order. Reuses order_book_imbalance() from Phase 2
    directly — no new formula, just applied across historical data.
    """
    return [order_book_imbalance(book, levels=levels) for book in books]