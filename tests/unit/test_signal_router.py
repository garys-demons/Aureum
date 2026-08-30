"""
Tests for signal routing. Proves both correct fill translation and the
critical timing constraint: record_fill() must be called synchronously,
per-fill, before returning — per Samarth's documented requirement.
"""
from unittest.mock import Mock
from core.strategy.base import Signal
from core.backtest.signal_router import (
    route_signal,
    route_signal_and_record,
    route_signals_and_record,
)
from services.market_data.order_book import OrderBook


def _make_book(bids: dict, asks: dict) -> OrderBook:
    book = OrderBook(symbol="ADAUSDT")
    book.bids = bids
    book.asks = asks
    return book


def test_hold_signal_produces_no_fill():
    book = _make_book(bids={}, asks={})
    signal = Signal(action="hold", symbol="ADAUSDT", reason="stub")
    assert route_signal(signal, book) is None


def test_signal_with_price_routes_to_limit_order_hand_calculated():
    book = _make_book(bids={}, asks={0.20: 100.0})
    signal = Signal(action="buy", symbol="ADAUSDT", price=0.20, quantity=50.0, reason="bid")
    fill = route_signal(signal, book)
    assert fill.quantity == 50.0
    assert fill.price == 0.20


def test_signal_without_price_routes_to_market_order():
    book = _make_book(bids={}, asks={0.20: 100.0})
    signal = Signal(action="buy", symbol="ADAUSDT", price=None, quantity=50.0, reason="market buy")
    fill = route_signal(signal, book)
    assert fill.quantity == 50.0


def test_record_fill_happens_before_returning_so_inventory_updates_immediately():
    book = _make_book(bids={}, asks={0.20: 100.0})
    strategy = Mock()
    signal = Signal(action="buy", symbol="ADAUSDT", price=0.20, quantity=10.0, reason="bid")

    route_signal_and_record(signal, book, strategy)

    strategy.record_fill.assert_called_once_with(action="buy", quantity=10.0)


def test_bid_and_ask_pair_each_record_fill_immediately_not_batched():
    # Book has: an ask at 0.18 (cheap enough for our buy limit 0.19 to
    # match against) and a bid at 0.22 (high enough for our sell limit
    # 0.21 to match against) — i.e. book liquidity sits inside our
    # strategy's quotes, so both signals actually cross and fill
    book = _make_book(bids={0.22: 100.0}, asks={0.18: 100.0})
    strategy = Mock()
    bid = Signal(action="buy", symbol="ADAUSDT", price=0.19, quantity=10.0, reason="bid")
    ask = Signal(action="sell", symbol="ADAUSDT", price=0.21, quantity=10.0, reason="ask")

    route_signals_and_record([bid, ask], book, strategy)

    assert strategy.record_fill.call_count == 2
    strategy.record_fill.assert_any_call(action="buy", quantity=10.0)
    strategy.record_fill.assert_any_call(action="sell", quantity=10.0)


def test_route_signals_filters_out_holds_and_non_fills():
    book = _make_book(bids={}, asks={})
    strategy = Mock()
    signals = [
        Signal(action="hold", symbol="ADAUSDT", reason="stub"),
        Signal(action="buy", symbol="ADAUSDT", price=0.20, quantity=10.0, reason="bid"),
    ]
    fills = route_signals_and_record(signals, book, strategy)
    assert fills == []
    strategy.record_fill.assert_not_called()


def test_route_signals_accepts_single_signal_not_just_list():
    book = _make_book(bids={}, asks={0.20: 100.0})
    strategy = Mock()
    signal = Signal(action="buy", symbol="ADAUSDT", price=0.20, quantity=10.0, reason="bid")
    fills = route_signals_and_record(signal, book, strategy)
    assert len(fills) == 1
