"""
Tests for the paper exchange. Every expected fill price/fee is
calculated by hand first — same standard as Phase 2/3.
"""
from services.market_data.order_book import OrderBook
from core.backtest.paper_exchange import (
    match_market_order,
    match_limit_order,
    TAKER_FEE_RATE,
    MAKER_FEE_RATE,
)


def _make_book(bids: dict, asks: dict) -> OrderBook:
    book = OrderBook(symbol="BTCUSDT")
    book.bids = bids
    book.asks = asks
    return book


# ---------- Market orders ----------

def test_market_buy_fills_single_level_hand_calculated():
    book = _make_book(bids={}, asks={100.0: 5.0})
    # buying 3 @ 100 -> cost = 300, avg price = 100
    fill = match_market_order(book, side="buy", quantity=3)
    assert fill.quantity == 3
    assert fill.price == 100.0
    assert fill.fully_filled is True
    assert fill.fee == 3 * 100.0 * TAKER_FEE_RATE


def test_market_buy_fills_across_multiple_levels_hand_calculated():
    book = _make_book(bids={}, asks={100.0: 2.0, 101.0: 3.0})
    # buying 4: takes 2 @ 100, then 2 @ 101 (only 2 of the 3 available)
    # total cost = 2*100 + 2*101 = 402, avg price = 402/4 = 100.5
    fill = match_market_order(book, side="buy", quantity=4)
    assert fill.quantity == 4
    assert fill.price == 100.5
    assert fill.fully_filled is True


def test_market_buy_partial_fill_when_book_runs_out():
    book = _make_book(bids={}, asks={100.0: 2.0})
    fill = match_market_order(book, side="buy", quantity=10)
    # only 2 available — must NOT silently "fill" all 10 (touch != fill)
    assert fill.quantity == 2
    assert fill.price == 100.0
    assert fill.fully_filled is False


def test_market_sell_fills_highest_bid_first_hand_calculated():
    book = _make_book(bids={100.0: 2.0, 99.0: 5.0}, asks={})
    # selling 3: takes 2 @ 100, then 1 @ 99
    # total = 2*100 + 1*99 = 299, avg price = 299/3
    fill = match_market_order(book, side="sell", quantity=3)
    assert fill.quantity == 3
    assert fill.price == 299 / 3


def test_market_order_none_when_no_liquidity():
    book = _make_book(bids={}, asks={})
    assert match_market_order(book, side="buy", quantity=1) is None


def test_market_order_raises_on_invalid_quantity():
    import pytest
    book = _make_book(bids={}, asks={100.0: 1.0})
    with pytest.raises(ValueError):
        match_market_order(book, side="buy", quantity=0)


def test_market_order_raises_on_invalid_side():
    import pytest
    book = _make_book(bids={}, asks={100.0: 1.0})
    with pytest.raises(ValueError):
        match_market_order(book, side="hold", quantity=1)


# ---------- Limit orders ----------

def test_limit_buy_fills_at_or_below_limit_hand_calculated():
    book = _make_book(bids={}, asks={100.0: 2.0, 102.0: 5.0})
    # limit 101 -> only the 100.0 level qualifies (102 > limit, excluded)
    fill = match_limit_order(book, side="buy", quantity=2, limit_price=101.0)
    assert fill.quantity == 2
    assert fill.price == 100.0
    assert fill.fully_filled is True
    assert fill.fee == 2 * 100.0 * MAKER_FEE_RATE


def test_limit_buy_partial_fill_never_spills_into_worse_price():
    book = _make_book(bids={}, asks={100.0: 2.0, 102.0: 5.0})
    # limit 101, want 10 -> only 2 available within limit, the 102 level
    # is never touched even though it could technically cover the rest
    fill = match_limit_order(book, side="buy", quantity=10, limit_price=101.0)
    assert fill.quantity == 2
    assert fill.price == 100.0
    assert fill.fully_filled is False


def test_limit_sell_fills_at_or_above_limit_hand_calculated():
    book = _make_book(bids={99.0: 3.0, 97.0: 5.0}, asks={})
    # limit 98 -> only 99.0 qualifies (97 < limit, excluded)
    fill = match_limit_order(book, side="sell", quantity=3, limit_price=98.0)
    assert fill.quantity == 3
    assert fill.price == 99.0


def test_limit_order_none_when_limit_not_met():
    book = _make_book(bids={}, asks={105.0: 5.0})
    # limit 100, but cheapest ask is 105 -> nothing qualifies
    fill = match_limit_order(book, side="buy", quantity=1, limit_price=100.0)
    assert fill is None


def test_limit_order_uses_maker_fee_not_taker(monkeypatch):
    """
    Proves match_limit_order specifically selects MAKER_FEE_RATE, not
    TAKER_FEE_RATE - independent of whatever the two constants happen
    to be worth right now (they briefly became numerically equal after
    the Phase 8 fee correction, which is what prompted this rewrite).
    Patches TAKER_FEE_RATE to an obviously-different sentinel value so
    this test can't accidentally pass due to real-world rate coincidence.
    """
    monkeypatch.setattr("core.backtest.paper_exchange.TAKER_FEE_RATE", 0.999)

    book = _make_book(bids={}, asks={100.0: 5.0})
    fill = match_limit_order(book, side="buy", quantity=1, limit_price=100.0)

    assert fill.fee == 1 * 100.0 * MAKER_FEE_RATE
    assert fill.fee != 1 * 100.0 * 0.999  # would be wildly off if taker rate were used