"""
Tests for the simplified candle-close fill model. Every expected value
calculated by hand first — same standard as the rest of the project.
Only used for symbols without real order-book data (e.g. ADA baseline);
see docstring in candle_fill_model.py for documented limitations.
"""
from core.backtest.candle_fill_model import (
    Candle,
    fill_market_order_candle,
    fill_limit_order_candle,
    MARKET_ORDER_SLIPPAGE,
)


def _make_candle(open_, high, low, close) -> Candle:
    return Candle(open=open_, high=high, low=low, close=close)


# ---------- Market orders ----------

def test_market_buy_fills_above_close_hand_calculated():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # slip = 0.20 * 0.0005 = 0.0001, buy fills WORSE (higher) than close
    price, qty = fill_market_order_candle(candle, side="buy", quantity=100.0)
    assert price == 0.20 + (0.20 * MARKET_ORDER_SLIPPAGE)
    assert qty == 100.0


def test_market_sell_fills_below_close_hand_calculated():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # sell fills WORSE (lower) than close
    price, qty = fill_market_order_candle(candle, side="sell", quantity=50.0)
    assert price == 0.20 - (0.20 * MARKET_ORDER_SLIPPAGE)
    assert qty == 50.0


def test_market_order_always_fully_fills_documented_limitation():
    # No depth concept in this model -> always fills the full requested
    # quantity, regardless of size. This is a known limitation, not a
    # feature -- this test locks in and documents that behavior so it
    # isn't silently "fixed" into looking more realistic than it is.
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    price, qty = fill_market_order_candle(candle, side="buy", quantity=1_000_000.0)
    assert qty == 1_000_000.0


# ---------- Limit orders ----------

def test_limit_buy_fills_when_low_touches_limit_hand_calculated():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # limit 0.195 -> candle low (0.19) went below it, so it "traded" there
    result = fill_limit_order_candle(candle, side="buy", quantity=100.0, limit_price=0.195)
    assert result == (0.195, 100.0)


def test_limit_buy_none_when_low_never_reaches_limit():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # limit 0.15 -> candle low (0.19) never went that low
    result = fill_limit_order_candle(candle, side="buy", quantity=100.0, limit_price=0.15)
    assert result is None


def test_limit_sell_fills_when_high_touches_limit_hand_calculated():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # limit 0.205 -> candle high (0.21) reached above it
    result = fill_limit_order_candle(candle, side="sell", quantity=50.0, limit_price=0.205)
    assert result == (0.205, 50.0)


def test_limit_sell_none_when_high_never_reaches_limit():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    # limit 0.25 -> candle high (0.21) never reached that high
    result = fill_limit_order_candle(candle, side="sell", quantity=50.0, limit_price=0.25)
    assert result is None


def test_limit_buy_fills_exactly_at_boundary():
    # limit price exactly equal to candle low -> should count as touched
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    result = fill_limit_order_candle(candle, side="buy", quantity=10.0, limit_price=0.19)
    assert result == (0.19, 10.0)


def test_limit_sell_fills_exactly_at_boundary():
    candle = _make_candle(0.20, 0.21, 0.19, 0.20)
    result = fill_limit_order_candle(candle, side="sell", quantity=10.0, limit_price=0.21)
    assert result == (0.21, 10.0)