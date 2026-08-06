"""
BinanceAdapter — concrete ExchangeAdapter for Binance Spot Testnet.

Day 3: stream_market_data (WebSocket client, reconnect/backoff) — Hansika
Day 4: fetch_historical_candles (REST downloader) — Gauri
"""
import json
from typing import AsyncIterator, Any

import websockets
import structlog

from services.market_data.adapters.base import ExchangeAdapter

logger = structlog.get_logger()

BINANCE_TESTNET_WS_BASE = "wss://stream.testnet.binance.vision/ws"


class BinanceAdapter(ExchangeAdapter):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._ws = None

    async def connect(self) -> None:
        """Open the WebSocket connection to Binance Testnet (base connection only)."""
        logger.info("connecting_to_binance", url=BINANCE_TESTNET_WS_BASE)
        self._ws = await websockets.connect(BINANCE_TESTNET_WS_BASE)
        logger.info("connected_to_binance")

    async def disconnect(self) -> None:
        """Cleanly close the WebSocket connection."""
        if self._ws is not None:
            await self._ws.close()
            logger.info("disconnected_from_binance")

    async def stream_market_data(self, symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
        """
        Connect to a combined ticker stream for the given symbols and yield
        raw parsed JSON dicts as they arrive. Parsing into Pydantic models
        happens one layer up (per base.py's docstring).
        """
        stream_names = "/".join(f"{s.lower()}@ticker" for s in symbols)
        url = f"wss://stream.testnet.binance.vision/stream?streams={stream_names}"

        logger.info("subscribing_to_streams", symbols=symbols, url=url)
        async with websockets.connect(url) as ws:
            self._ws = ws
            logger.info("stream_connected", symbols=symbols)
            async for raw_message in ws:
                try:
                    parsed = json.loads(raw_message)
                    yield parsed
                except json.JSONDecodeError:
                    logger.warning("invalid_json_received", raw=raw_message)
                    continue

    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_time: int, end_time: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Implemented Day 4 — REST historical downloader")