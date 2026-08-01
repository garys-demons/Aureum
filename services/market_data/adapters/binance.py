"""
BinanceAdapter — concrete ExchangeAdapter for Binance Spot Testnet.

Stub only for Day 1. Implementation lands:
  - Day 3: stream_market_data (WebSocket client, reconnect/backoff) — Hansika
  - Day 4: fetch_historical_candles (REST downloader) — Gauri
"""

from typing import AsyncIterator, Any

from services.market_data.adapters.base import ExchangeAdapter


class BinanceAdapter(ExchangeAdapter):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._ws = None

    async def connect(self) -> None:
        raise NotImplementedError("Implemented Day 3 — WebSocket client with reconnect/backoff")

    async def disconnect(self) -> None:
        raise NotImplementedError("Implemented Day 3")

    async def stream_market_data(self, symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError("Implemented Day 3")
        yield {}  # pragma: no cover

    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_time: int, end_time: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Implemented Day 4 — REST historical downloader")
