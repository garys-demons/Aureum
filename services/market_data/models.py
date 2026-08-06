"""
Pydantic models for standardized market data events.

MarketEvent is the base model all specific event types (TradeEvent,
OrderBookSnapshot, OrderBookDelta, Candle, TickerEvent) inherit from.
See docs/Backend_Schema.md §3 for full field definitions.
"""
from enum import Enum
from typing import List

from pydantic import BaseModel, Field, model_validator


class MarketEvent(BaseModel):
    """Base fields shared by every market data event, regardless of type."""

    event_type: str = Field(..., description="Type of market event, e.g. 'trade', 'depth', 'kline', 'ticker'")
    exchange: str = Field(..., description="Source exchange, e.g. 'binance'")
    symbol: str = Field(..., description="Trading pair, e.g. 'BTCUSDT'")
    event_time: int = Field(..., description="Exchange-side timestamp in Unix ms")
    received_time: int = Field(..., description="Local timestamp when we received the message, in Unix ms")


class PriceLevel(BaseModel):
    """A single price/quantity pair in an order book (replaces raw [price, qty] lists)."""

    price: float = Field(..., ge=0, description="Price at this level")
    quantity: float = Field(..., ge=0, description="Quantity available at this price (0 = level removed)")


class TradeEvent(MarketEvent):
    """A single executed trade on the exchange."""

    trade_id: int = Field(..., description="Exchange-assigned trade identifier")
    price: float = Field(..., gt=0, description="Executed trade price")
    quantity: float = Field(..., gt=0, description="Executed quantity")
    buyer_maker: bool = Field(..., description="True if the buyer was the market maker")
    trade_time: int = Field(..., description="Trade timestamp in Unix ms")


class SnapshotSource(str, Enum):
    """Distinguishes a fresh REST snapshot from one reconstructed after reconciliation."""

    REST_FULL = "rest_full"
    RECONCILED = "reconciled"


class OrderBookSnapshot(MarketEvent):
    """A full point-in-time picture of the order book (bids + asks)."""

    last_update_id: int = Field(..., description="Snapshot update id")
    bids: List[PriceLevel] = Field(..., description="Bid price levels")
    asks: List[PriceLevel] = Field(..., description="Ask price levels")
    snapshot_time: int = Field(..., description="Snapshot timestamp in Unix ms")
    source: SnapshotSource = Field(..., description="Whether this came fresh from REST or was reconstructed after reconciliation")


class OrderBookDelta(MarketEvent):
    """An incremental update to the order book since the last delta/snapshot."""

    first_update_id: int = Field(..., description="First update id included in this delta")
    final_update_id: int = Field(..., description="Final update id included in this delta")
    bids: List[PriceLevel] = Field(..., description="Updated bid levels")
    asks: List[PriceLevel] = Field(..., description="Updated ask levels")

    @model_validator(mode="after")
    def check_update_id_range(self):
        """Reject construction outright if first_update_id > final_update_id (Backend Schema §7)."""
        if self.first_update_id > self.final_update_id:
            raise ValueError("first_update_id must be <= final_update_id")
        return self


class Candle(MarketEvent):
    """OHLCV candle for a given interval (1m, 5m, 1h, etc.)."""

    interval: str = Field(..., description="Candle interval, e.g. '1m', '5m', '1h', '1d'")
    open_time: int = Field(..., description="Open timestamp in Unix ms")
    close_time: int = Field(..., description="Close timestamp in Unix ms")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price in the interval")
    low: float = Field(..., gt=0, description="Lowest price in the interval")
    close: float = Field(..., gt=0, description="Closing price")
    volume: float = Field(..., ge=0, description="Traded volume in the interval")
    is_closed: bool = Field(..., description="True if this bar is final, False if still in progress")


class TickerEvent(MarketEvent):
    """24-hour rolling ticker statistics for a symbol."""

    last_price: float = Field(..., gt=0, description="Latest traded price")
    price_change: float = Field(..., description="Absolute price change over 24h")
    price_change_percent: float = Field(..., description="Percentage price change over 24h")
    high_price: float = Field(..., gt=0, description="24h high")
    low_price: float = Field(..., gt=0, description="24h low")
    volume: float = Field(..., ge=0, description="24h traded volume")