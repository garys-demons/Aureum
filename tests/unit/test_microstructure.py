"""
Tests for microstructure metrics. Every expected value below is worked
out by hand first (see comments) — not just "does it run without error."
"""
from services.market_data.order_book import OrderBook
from core.metrics.microstructure import (
    microprice,
    depth_weighted_price,
    order_book_imbalance,
)


def _make_book() -> OrderBook:
    """
    A small, fixed order book used across all tests, so every expected
    value can be traced back to the same numbers.

    Bids: 100 x 10, 99 x 5, 98 x 2
    Asks: 101 x 8, 102 x 4, 103 x 1
    """
    book = OrderBook(symbol="BTCUSDT")
    book.bids = {100.0: 10.0, 99.0: 5.0, 98.0: 2.0}
    book.asks = {101.0: 8.0, 102.0: 4.0, 103.0: 1.0}
    return book


def test_microprice_hand_calculated():
    book = _make_book()
    # best_bid = (100, 10), best_ask = (101, 8)
    # microprice = (100*8 + 101*10) / (8+10) = (800 + 1010) / 18 = 1810/18
    expected = 1810 / 18
    assert microprice(book) == expected


def test_microprice_none_when_one_side_empty():
    book = OrderBook(symbol="BTCUSDT")
    book.bids = {100.0: 10.0}
    book.asks = {}
    assert microprice(book) is None


def test_depth_weighted_price_top_2_levels_hand_calculated():
    book = _make_book()
    # top 2 bids: 100 x 10, 99 x 5  -> value = 1000 + 495 = 1495, qty = 15
    # top 2 asks: 101 x 8, 102 x 4  -> value = 808 + 408 = 1216, qty = 12
    # total value = 2711, total qty = 27
    expected = 2711 / 27
    assert depth_weighted_price(book, levels=2) == expected


def test_depth_weighted_price_uses_all_levels_if_fewer_than_requested():
    book = _make_book()
    # only 3 levels exist per side, so levels=10 should behave like levels=3
    result_10 = depth_weighted_price(book, levels=10)
    result_3 = depth_weighted_price(book, levels=3)
    assert result_10 == result_3


def test_order_book_imbalance_all_levels_hand_calculated():
    book = _make_book()
    # total bid qty = 10+5+2 = 17, total ask qty = 8+4+1 = 13
    # imbalance = 17 / (17+13) = 17/30
    expected = 17 / 30
    assert order_book_imbalance(book) == expected


def test_order_book_imbalance_top_1_level_hand_calculated():
    book = _make_book()
    # top 1 bid = 10, top 1 ask = 8 -> imbalance = 10 / 18
    expected = 10 / 18
    assert order_book_imbalance(book, levels=1) == expected


def test_order_book_imbalance_none_when_empty():
    book = OrderBook(symbol="BTCUSDT")
    assert order_book_imbalance(book) is None