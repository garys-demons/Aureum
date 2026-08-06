"""Unit tests for parsers.py — uses fake/sample data, no real network needed."""
from services.market_data.parsers import parse_ticker_event
from services.market_data.models import TickerEvent
from services.market_data.parsers import parse_trade_event
from services.market_data.models import TradeEvent
from services.market_data.parsers import parse_candle_event
from services.market_data.models import Candle
    
from services.market_data.parsers import parse_order_book_snapshot
from services.market_data.models import OrderBookSnapshot
from services.market_data.parsers import parse_order_book_delta
from services.market_data.models import OrderBookDelta




def sample_raw_ticker_message():
    """A realistic fake Binance combined-stream ticker message."""
    return {
        "stream": "btcusdt@ticker",
        "data": {
            "e": "24hrTicker",
            "E": 1786035795004,
            "s": "BTCUSDT",
            "p": "44.71000000",
            "P": "0.069",
            "c": "64823.99000000",
            "h": "65004.62000000",
            "l": "53382.00000000",
            "v": "835.72199000",
        },
    }


def test_parse_ticker_event_returns_ticker_event():
    """parse_ticker_event should return a valid TickerEvent instance."""
    raw = sample_raw_ticker_message()
    ticker = parse_ticker_event(raw)

    assert isinstance(ticker, TickerEvent)
    assert ticker.symbol == "BTCUSDT"
    assert ticker.exchange == "binance"


def test_parse_ticker_event_converts_string_numbers_to_float():
    """Binance sends numbers as strings — confirm they're correctly converted."""
    raw = sample_raw_ticker_message()
    ticker = parse_ticker_event(raw)

    assert ticker.last_price == 64823.99
    assert isinstance(ticker.last_price, float)


def test_parse_ticker_event_preserves_event_time():
    """event_time should come from Binance's 'E' field, unchanged."""
    raw = sample_raw_ticker_message()
    ticker = parse_ticker_event(raw)

    assert ticker.event_time == 1786035795004
    



def sample_raw_trade_message():
    """A realistic fake Binance combined-stream trade message."""
    return {
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "E": 1786035795004,
            "s": "BTCUSDT",
            "t": 12345,
            "p": "64823.99000000",
            "q": "0.01000000",
            "b": 88,
            "a": 50,
            "T": 1786035794999,
            "m": True,
        },
    }


def test_parse_trade_event_returns_trade_event():
    raw = sample_raw_trade_message()
    trade = parse_trade_event(raw)

    assert isinstance(trade, TradeEvent)
    assert trade.symbol == "BTCUSDT"
    assert trade.trade_id == 12345


def test_parse_trade_event_converts_types_correctly():
    raw = sample_raw_trade_message()
    trade = parse_trade_event(raw)

    assert trade.price == 64823.99
    assert trade.buyer_maker is True
    


def sample_raw_candle_message():
    """A realistic fake Binance combined-stream kline message."""
    return {
        "stream": "btcusdt@kline_1m",
        "data": {
            "e": "kline",
            "E": 1786035795004,
            "s": "BTCUSDT",
            "k": {
                "t": 1786035780000,
                "T": 1786035839999,
                "s": "BTCUSDT",
                "i": "1m",
                "o": "64800.00000000",
                "c": "64823.99000000",
                "h": "64850.00000000",
                "l": "64790.00000000",
                "v": "12.50000000",
                "x": False,
            },
        },
    }


def test_parse_candle_event_returns_candle():
    raw = sample_raw_candle_message()
    candle = parse_candle_event(raw)

    assert isinstance(candle, Candle)
    assert candle.interval == "1m"
    assert candle.is_closed is False


def test_parse_candle_event_converts_types_correctly():
    raw = sample_raw_candle_message()
    candle = parse_candle_event(raw)

    assert candle.open == 64800.0
    assert candle.close == 64823.99


def sample_raw_snapshot():
    return {
        "lastUpdateId": 376909,
        "bids": [["64733.13", "14.77361"], ["64733.12", "0.00326"]],
        "asks": [["64733.14", "30.5753"], ["64733.15", "0.00192"]],
    }


def test_parse_order_book_snapshot_returns_snapshot():
    raw = sample_raw_snapshot()
    snapshot = parse_order_book_snapshot(raw, symbol="BTCUSDT")

    assert isinstance(snapshot, OrderBookSnapshot)
    assert snapshot.last_update_id == 376909
    assert len(snapshot.bids) == 2
    assert snapshot.bids[0].price == 64733.13
    


def sample_raw_delta():
    return {
        "stream": "btcusdt@depth",
        "data": {
            "e": "depthUpdate",
            "E": 1786035795004,
            "s": "BTCUSDT",
            "U": 157,
            "u": 160,
            "b": [["64750.08", "1.5"]],
            "a": [["64750.09", "2.0"]],
        },
    }


def test_parse_order_book_delta_returns_delta():
    raw = sample_raw_delta()
    delta = parse_order_book_delta(raw)

    assert isinstance(delta, OrderBookDelta)
    assert delta.first_update_id == 157
    assert delta.final_update_id == 160