# core/backtest/candle_fill_model.py
"""
Simplified fill model for symbols without order-book data (e.g. ADA
baseline). NOT a substitute for match_market_order/match_limit_order —
this is a documented approximation, used only when real book depth
isn't available. Do not confuse this with a "realistic fill" claim.

Limitations (must stay visible, not just in this docstring):
- No partial fills — a real order could easily be too large for actual
  liquidity at that candle; this model can't detect that
- Market order slippage is a flat assumption, not derived from real depth
- Limit fills use the candle's high/low as a proxy for "did the price
  trade there" — coarser than tick-level reality
"""
from dataclasses import dataclass

MARKET_ORDER_SLIPPAGE = 0.0005  # 0.05%, documented placeholder


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float


def fill_market_order_candle(candle: Candle, side: str, quantity: float) -> tuple[float, float]:
    """Returns (fill_price, quantity). Always fully fills — documented limitation."""
    slip = candle.close * MARKET_ORDER_SLIPPAGE
    fill_price = candle.close + slip if side == "buy" else candle.close - slip
    return fill_price, quantity


def fill_limit_order_candle(candle: Candle, side: str, quantity: float, limit_price: float) -> tuple[float, float] | None:
    """
    Fills at limit_price only if the candle's range shows the price
    actually traded there. Returns None if never touched.
    """
    if side == "buy" and candle.low <= limit_price:
        return limit_price, quantity
    if side == "sell" and candle.high >= limit_price:
        return limit_price, quantity
    return None