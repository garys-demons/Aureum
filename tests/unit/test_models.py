"""Unit tests for MarketEvent and related models."""
import pytest
from pydantic import ValidationError

from services.market_data.models import (
    MarketEvent,
    TradeEvent,
    OrderBookSnapshot,
    OrderBookDelta,
    PriceLevel,
    SnapshotSource,
    Candle,
    TickerEvent,
)


def test_market_event_valid():
    """A correctly-shaped MarketEvent should construct without errors."""
    event = MarketEvent(
        event_type="trade",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1234567890,
        received_time=1234567891,
    )
    assert event.symbol == "BTCUSDT"
    assert event.exchange == "binance"


def test_market_event_missing_field_raises():
    """Missing a required field should raise a ValidationError, not silently pass."""
    with pytest.raises(ValidationError):
        MarketEvent(
            event_type="trade",
            exchange="binance",
            symbol="BTCUSDT",
            event_time=1234567890,
        )


def test_market_event_wrong_type_raises():
    """Passing a string where an int is expected should raise a ValidationError."""
    with pytest.raises(ValidationError):
        MarketEvent(
            event_type="trade",
            exchange="binance",
            symbol="BTCUSDT",
            event_time="not-a-number",
            received_time=1234567891,
        )


def test_trade_event_valid():
    """A correctly-shaped TradeEvent should construct and inherit base fields."""
    trade = TradeEvent(
        event_type="trade",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1700000000000,
        received_time=1700000000010,
        trade_id=12345,
        price=50000.5,
        quantity=0.01,
        buyer_maker=True,
        trade_time=1700000000000,
    )
    assert trade.symbol == "BTCUSDT"
    assert trade.trade_id == 12345
    assert trade.exchange == "binance"  # inherited from MarketEvent


def test_trade_event_zero_price_rejected():
    """Price must be > 0 — a trade at price 0 is invalid, should raise."""
    with pytest.raises(ValidationError):
        TradeEvent(
            event_type="trade",
            exchange="binance",
            symbol="BTCUSDT",
            event_time=1700000000000,
            received_time=1700000000010,
            trade_id=12345,
            price=0,
            quantity=0.01,
            buyer_maker=True,
            trade_time=1700000000000,
        )


def test_trade_event_negative_quantity_rejected():
    """Quantity must be > 0 — negative quantity is invalid, should raise."""
    with pytest.raises(ValidationError):
        TradeEvent(
            event_type="trade",
            exchange="binance",
            symbol="BTCUSDT",
            event_time=1700000000000,
            received_time=1700000000010,
            trade_id=12345,
            price=50000.5,
            quantity=-1,
            buyer_maker=True,
            trade_time=1700000000000,
        )


def test_order_book_snapshot_valid():
    """A correctly-shaped OrderBookSnapshot should construct successfully."""
    snapshot = OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1700000000000,
        received_time=1700000000010,
        last_update_id=1000,
        bids=[PriceLevel(price=50000, quantity=1.5)],
        asks=[PriceLevel(price=50010, quantity=2.0)],
        snapshot_time=1700000000000,
        source=SnapshotSource.REST_FULL,
    )
    assert snapshot.source == "rest_full"
    assert len(snapshot.bids) == 1


def test_order_book_delta_valid():
    """A correctly-shaped OrderBookDelta should construct successfully."""
    delta = OrderBookDelta(
        event_type="depth_update",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1700000000000,
        received_time=1700000000010,
        first_update_id=100,
        final_update_id=105,
        bids=[PriceLevel(price=50000, quantity=1.5)],
        asks=[PriceLevel(price=50010, quantity=2.0)],
    )
    assert delta.first_update_id == 100
    assert delta.final_update_id == 105


def test_order_book_delta_invalid_range_rejected():
    """first_update_id > final_update_id must raise ValidationError at construction (Backend Schema §7)."""
    with pytest.raises(ValidationError):
        OrderBookDelta(
            event_type="depth_update",
            exchange="binance",
            symbol="BTCUSDT",
            event_time=1700000000000,
            received_time=1700000000010,
            first_update_id=105,
            final_update_id=100,
            bids=[],
            asks=[],
        )


def test_price_level_negative_quantity_rejected():
    """PriceLevel quantity must be >= 0."""
    with pytest.raises(ValidationError):
        PriceLevel(price=50000, quantity=-1)


def test_candle_valid():
    """A correctly-shaped Candle should construct successfully."""
    candle = Candle(
        event_type="kline",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1700000000000,
        received_time=1700000000010,
        interval="1m",
        open_time=1700000000000,
        close_time=1700000060000,
        open=50000,
        high=50100,
        low=49900,
        close=50050,
        volume=12.5,
        is_closed=True,
    )
    assert candle.interval == "1m"
    assert candle.is_closed is True


def test_candle_zero_open_price_rejected():
    """open must be > 0."""
    with pytest.raises(ValidationError):
        Candle(
            event_type="kline",
            exchange="binance",
            symbol="BTCUSDT",
            event_time=1700000000000,
            received_time=1700000000010,
            interval="1m",
            open_time=1700000000000,
            close_time=1700000060000,
            open=0,
            high=50100,
            low=49900,
            close=50050,
            volume=12.5,
            is_closed=True,
        )


def test_ticker_event_valid():
    """A correctly-shaped TickerEvent should construct successfully."""
    ticker = TickerEvent(
        event_type="ticker",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1700000000000,
        received_time=1700000000010,
        last_price=50000,
        price_change=100,
        price_change_percent=0.2,
        high_price=50500,
        low_price=49500,
        volume=1000,
    )
    assert ticker.last_price == 50000
    assert ticker.symbol == "BTCUSDT"