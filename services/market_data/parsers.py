"""
Parsers that convert raw Binance JSON messages into standardized
internal Pydantic models (MarketEvent subclasses).
"""
from services.market_data.models import TickerEvent
from services.market_data.models import TradeEvent
from services.market_data.models import Candle
from services.market_data.models import OrderBookSnapshot, PriceLevel, SnapshotSource
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



def parse_trade_event(raw: dict) -> TradeEvent:
    """
    Convert a raw Binance combined-stream trade message into a TradeEvent.

    Expected raw shape:
        {"stream": "btcusdt@trade", "data": {...actual trade fields...}}
    """
    data = raw["data"]

    return TradeEvent(
        event_type="trade",
        exchange="binance",
        symbol=data["s"],
        event_time=data["E"],
        received_time=int(time.time() * 1000),
        trade_id=data["t"],
        price=float(data["p"]),
        quantity=float(data["q"]),
        buyer_maker=data["m"],
        trade_time=data["T"],
    )




def parse_candle_event(raw: dict) -> Candle:
    """
    Convert a raw Binance combined-stream kline message into a Candle.

    Expected raw shape:
        {"stream": "btcusdt@kline_1m", "data": {..., "k": {...candle fields...}}}
    """
    data = raw["data"]
    k = data["k"]

    return Candle(
        event_type="kline",
        exchange="binance",
        symbol=data["s"],
        event_time=data["E"],
        received_time=int(time.time() * 1000),
        interval=k["i"],
        open_time=k["t"],
        close_time=k["T"],
        open=float(k["o"]),
        high=float(k["h"]),
        low=float(k["l"]),
        close=float(k["c"]),
        volume=float(k["v"]),
        is_closed=k["x"],
    )
    



def parse_order_book_snapshot(raw: dict, symbol: str) -> OrderBookSnapshot:
    """
    Convert a raw Binance REST /api/v3/depth response into an OrderBookSnapshot.

    Expected raw shape:
        {"lastUpdateId": 376446, "bids": [["64750.08", "15.05"], ...], "asks": [...]}

    Note: Binance's REST depth response doesn't include the symbol — it's
    implied by what you requested — so we pass it in explicitly.
    """
    bids = [PriceLevel(price=float(p), quantity=float(q)) for p, q in raw["bids"]]
    asks = [PriceLevel(price=float(p), quantity=float(q)) for p, q in raw["asks"]]
    now_ms = int(time.time() * 1000)

    return OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol=symbol,
        event_time=now_ms,
        received_time=now_ms,
        last_update_id=raw["lastUpdateId"],
        bids=bids,
        asks=asks,
        snapshot_time=now_ms,
        source=SnapshotSource.REST_FULL,
    )