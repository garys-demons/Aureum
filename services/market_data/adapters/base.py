"""
ExchangeAdapter — the interface every exchange integration must implement.

Phase 1 only needs the shape defined; WebSocket and REST implementations
land on Day 3 and Day 4 of the sprint (owned by Hansika and Gauri respectively).
Keeping this interface exchange-agnostic now means swapping or adding a
second exchange later doesn't touch core/ or services/trading.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class ExchangeAdapter(ABC):
    """Base interface for any exchange integration (Binance, Kraken, etc.)."""

    @abstractmethod
    async def connect(self) -> None:
        """Open the underlying WebSocket/REST session."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanly tear down the connection."""
        raise NotImplementedError

    @abstractmethod
    async def stream_market_data(self, symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
        """
        Yield raw market data events (trades, book updates, tickers) for the
        given symbols. Raw dicts here — parsing into MarketEvent/TradeEvent/
        OrderBookDelta pydantic models happens one layer up (Day 2 schemas).
        """
        raise NotImplementedError
        yield {}  # pragma: no cover — keeps this an async generator for type checkers

    @abstractmethod
    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_time: int, end_time: int
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV candles over [start_time, end_time] (ms epoch)."""
        raise NotImplementedError
