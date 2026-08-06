"""Unit tests for parsers.py — uses fake/sample data, no real network needed."""
from services.market_data.parsers import parse_ticker_event
from services.market_data.models import TickerEvent


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