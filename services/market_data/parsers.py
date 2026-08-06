"""
Parsers that convert raw Binance JSON messages into standardized
internal Pydantic models (MarketEvent subclasses).
"""
from services.market_data.models import TickerEvent
import time


def parse_ticker_event(raw: dict) -> TickerEvent:
    """
    Convert a raw Binance combined-stream ticker message into a TickerEvent.

    Expected raw shape (combined stream wrapper):
        {"stream": "btcusdt@ticker", "data": {...actual ticker fields...}}
    """
    data = raw["data"]

    return TickerEvent(
        event_type="ticker",
        exchange="binance",
        symbol=data["s"],
        event_time=data["E"],
        received_time=int(time.time() * 1000),
        last_price=float(data["c"]),
        price_change=float(data["p"]),
        price_change_percent=float(data["P"]),
        high_price=float(data["h"]),
        low_price=float(data["l"]),
        volume=float(data["v"]),
    )