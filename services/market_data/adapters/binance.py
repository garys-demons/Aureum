"""
BinanceAdapter — concrete ExchangeAdapter for Binance Spot Testnet.

Day 3: stream_market_data (WebSocket client, reconnect/backoff) — Hansika
Day 4: fetch_historical_candles (REST downloader) — Gauri
"""
import asyncio
import json
from typing import AsyncIterator, Any

import websockets
import structlog

from services.market_data.adapters.base import ExchangeAdapter

logger = structlog.get_logger()

BINANCE_TESTNET_WS_BASE = "wss://stream.testnet.binance.vision/ws"

# Backoff parameters (TRD §6.3) — single source of truth in config/exchange.yaml
# in production; hardcoded here for Day 3 baseline, wire to config later.
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 60
BACKOFF_MULTIPLIER = 2


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

    async def stream_market_data(self, symbols: list[str]):
        """
        Connect to combined ticker + trade streams for the given symbols and
        yield parsed, deduplicated MarketEvent models (TickerEvent, TradeEvent).
        Automatically reconnects with exponential backoff on disconnect (TRD §6.3).
        """
        from services.market_data.parsers import parse_ticker_event, parse_trade_event
        from services.market_data.dedup import TradeDeduplicator

        dedup = TradeDeduplicator()

        stream_names = "/".join(
            f"{s.lower()}@ticker/{s.lower()}@trade" for s in symbols
        )
        url = f"wss://stream.testnet.binance.vision/stream?streams={stream_names}"

        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            try:
                logger.info("subscribing_to_streams", symbols=symbols, url=url)
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    logger.info("stream_connected", symbols=symbols)
                    backoff = INITIAL_BACKOFF_SECONDS

                    async for raw_message in ws:
                        try:
                            raw = json.loads(raw_message)
                        except json.JSONDecodeError:
                            logger.warning("invalid_json_received", raw=raw_message)
                            continue

                        stream_name = raw.get("stream", "")

                        try:
                            if stream_name.endswith("@ticker"):
                                yield parse_ticker_event(raw)

                            elif stream_name.endswith("@trade"):
                                trade = parse_trade_event(raw)
                                if dedup.is_duplicate(trade):
                                    logger.debug("duplicate_trade_dropped", trade_id=trade.trade_id)
                                    continue
                                dedup.mark_seen(trade)
                                yield trade

                        except Exception as e:
                            logger.error("failed_to_parse_message", error=str(e), raw=raw)
                            continue

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(
                    "stream_disconnected_retrying",
                    error=str(e),
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_time: int, end_time: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Implemented Day 4 — REST historical downloader")