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

# If the buffer grows past this while still unable to bridge the snapshot,
# the snapshot is genuinely stale and we re-fetch. Should effectively never
# happen in normal operation.
MAX_BUFFER_BEFORE_RESNAPSHOT = 200


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
        from services.market_data.parsers import parse_candle_event, parse_ticker_event, parse_trade_event
        from services.market_data.dedup import TradeDeduplicator

        dedup = TradeDeduplicator()

        stream_names = "/".join(
            f"{s.lower()}@ticker/{s.lower()}@trade/{s.lower()}@kline_1m" for s in symbols
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

                            elif stream_name.endswith("@kline_1m"):
                                # Binance sends an update on every trade within
                                # the current candle (is_closed=False), then one
                                # final update when the bar completes
                                # (is_closed=True). We yield every update here —
                                # the adapter's job is to report what's actually
                                # happening, not decide what's worth keeping.
                                # Whether to persist in-progress bars is a
                                # downstream (runner.py) decision (FR-6).
                                yield parse_candle_event(raw)

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

    async def stream_order_book(self, symbol: str):
        """
        Stream order book deltas for one symbol on a dedicated connection.

        Implements the TRD §6.1 reconciliation procedure: subscribe first,
        buffer deltas while fetching the REST snapshot, reconcile, then apply
        in contiguous order. Any gap triggers a full re-sync rather than
        silently continuing with a corrupt book.

        Runs on its own WebSocket so a book-stream reconnect doesn't disturb
        trade/ticker flow (TRD §6.2).

        Yields (delta, book) so callers can persist the delta and read current
        book state without re-deriving it.
        """
        from services.market_data.parsers import parse_order_book_delta
        from services.market_data.order_book import fetch_snapshot, reconcile, OrderBook

        url = f"wss://stream.testnet.binance.vision/stream?streams={symbol.lower()}@depth"
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            try:
                logger.info("book_stream_subscribing", symbol=symbol, url=url)
                async with websockets.connect(url) as ws:
                    logger.info("book_stream_connected", symbol=symbol, state="reconciling")
                    backoff = INITIAL_BACKOFF_SECONDS

                    book: OrderBook | None = None
                    snapshot = None
                    buffer: list = []

                    async for raw_message in ws:
                        try:
                            raw = json.loads(raw_message)
                        except json.JSONDecodeError:
                            logger.warning("book_invalid_json", raw=raw_message)
                            continue

                        try:
                            delta = parse_order_book_delta(raw)
                        except Exception as e:
                            logger.error("book_parse_failed", error=str(e))
                            continue

                        # --- Reconciling ---
                        if book is None:
                            buffer.append(delta)

                            # Fetch the snapshot exactly once. Re-fetching on
                            # every failed reconcile is a trap: each new snapshot
                            # is newer than the buffered deltas, so they all get
                            # filtered out and reconciliation never succeeds.
                            if snapshot is None:
                                snapshot = await fetch_snapshot(symbol)

                            try:
                                ordered = reconcile(snapshot, buffer)
                            except ValueError:
                                # Not bridgeable yet — keep buffering. Only
                                # re-snapshot if the buffer runs away, meaning
                                # the snapshot is genuinely stale.
                                if len(buffer) > MAX_BUFFER_BEFORE_RESNAPSHOT:
                                    logger.warning(
                                        "book_snapshot_stale_refetching", symbol=symbol
                                    )
                                    snapshot = None
                                    buffer = []
                                continue

                            book = OrderBook.from_snapshot(snapshot)
                            for d in ordered:
                                book.apply(d)
                            book.mark_live()
                            buffer = []
                            logger.info(
                                "book_reconciled",
                                symbol=symbol,
                                last_update_id=book.last_update_id,
                                depth=book.depth(),
                            )
                            yield ordered[-1], book
                            continue

                        # --- Live: apply with contiguity enforcement ---
                        try:
                            book.apply(delta)
                            yield delta, book
                        except ValueError as e:
                            logger.error(
                                "book_sequence_gap_resyncing", symbol=symbol, error=str(e)
                            )
                            book = None
                            snapshot = None
                            buffer = [delta]

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(
                    "book_stream_disconnected_retrying",
                    symbol=symbol,
                    error=str(e),
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_time: int, end_time: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Implemented Day 4 — REST historical downloader")