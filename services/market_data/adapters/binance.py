"""
BinanceAdapter — concrete ExchangeAdapter for Binance Spot Testnet.

Runs independently-tracked stream lifecycles concurrently (TRD §6.2):
  - ticker + trade (stateless, append-only — resubscribe-and-resume on reconnect)
  - order book, per symbol (stateful — full reconciliation on reconnect, TRD §6.1)
All parsed, validated, deduplicated events are merged onto a single queue
and yielded to the caller via stream_market_data().
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
        Run the ticker+trade stream and one order-book stream per symbol
        concurrently, and yield all parsed events through a single merged
        stream as they arrive. Each stream reconnects independently
        (TRD §6.2) — a book-stream disconnect never interrupts ticker/trade.
        """
        queue: asyncio.Queue = asyncio.Queue()

        tasks = [asyncio.create_task(self._run_ticker_trade_stream(symbols, queue))]
        for symbol in symbols:
            tasks.append(asyncio.create_task(self._run_order_book_stream(symbol, queue)))

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_ticker_trade_stream(self, symbols: list[str], queue: asyncio.Queue) -> None:
        """
        Connect to combined ticker + trade streams and push parsed,
        deduplicated events onto the shared queue. Reconnects with
        exponential backoff on disconnect (TRD §6.3). Stateless/append-only
        streams — resubscribe and resume directly on reconnect (TRD §6.2).
        """
        from services.market_data.parsers import parse_ticker_event, parse_trade_event
        from services.market_data.dedup import TradeDeduplicator

        dedup = TradeDeduplicator()
        stream_names = "/".join(f"{s.lower()}@ticker/{s.lower()}@trade" for s in symbols)
        url = f"wss://stream.testnet.binance.vision/stream?streams={stream_names}"

        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            try:
                logger.info("subscribing_to_ticker_trade_streams", symbols=symbols, url=url)
                async with websockets.connect(url) as ws:
                    logger.info("ticker_trade_stream_connected", symbols=symbols)
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
                                await queue.put(parse_ticker_event(raw))

                            elif stream_name.endswith("@trade"):
                                trade = parse_trade_event(raw)
                                if dedup.is_duplicate(trade):
                                    logger.debug("duplicate_trade_dropped", trade_id=trade.trade_id)
                                    continue
                                dedup.mark_seen(trade)
                                await queue.put(trade)

                        except Exception as e:
                            logger.error("failed_to_parse_message", error=str(e), raw=raw)
                            continue

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(
                    "ticker_trade_stream_disconnected_retrying",
                    error=str(e),
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    async def _run_order_book_stream(self, symbol: str, queue: asyncio.Queue) -> None:
        """
        Maintain a reconciled local order book for `symbol` (TRD §6.1).

        On initial connect and on ANY disconnect, this does NOT simply
        resubscribe — it re-runs the full reconciliation procedure:
        buffer live deltas, fetch a fresh REST snapshot, find the correct
        starting delta, and verify contiguity. Any gap triggers a full
        re-reconciliation, not a skip (TRD §6.1 step 6, §6.2).
        """
        from services.market_data.order_book import fetch_snapshot, reconcile
        from services.market_data.parsers import parse_order_book_delta

        stream_url = f"wss://stream.testnet.binance.vision/ws/{symbol.lower()}@depth"
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            try:
                logger.info("order_book_connecting", symbol=symbol)
                async with websockets.connect(stream_url) as ws:
                    logger.info("order_book_reconciling", symbol=symbol)
                    backoff = INITIAL_BACKOFF_SECONDS

                    # Buffer live deltas while the REST snapshot is fetched
                    # (TRD §6.1 steps 2-3) — do not discard anything.
                    buffered_deltas = []
                    snapshot_task = asyncio.create_task(fetch_snapshot(symbol))

                    while not snapshot_task.done():
                        try:
                            raw_message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        raw = json.loads(raw_message)
                        wrapped = {"stream": f"{symbol.lower()}@depth", "data": raw}
                        buffered_deltas.append(parse_order_book_delta(wrapped))

                    snapshot = await snapshot_task

                    # Find the correct starting point and verify contiguity
                    # (TRD §6.1 steps 4-6). Any failure -> re-fetch and retry.
                    try:
                        ordered_deltas = reconcile(snapshot, buffered_deltas)
                    except ValueError as e:
                        logger.warning(
                            "order_book_reconciliation_failed_retrying",
                            symbol=symbol,
                            error=str(e),
                        )
                        continue  # re-enter outer loop: fresh connect + fresh snapshot

                    await queue.put(snapshot)
                    last_update_id = snapshot.last_update_id
                    for delta in ordered_deltas:
                        await queue.put(delta)
                        last_update_id = delta.final_update_id

                    logger.info("order_book_live", symbol=symbol, last_update_id=last_update_id)

                    # Now "live" — forward each new delta, verifying it
                    # connects exactly to the previous one.
                    async for raw_message in ws:
                        raw = json.loads(raw_message)
                        wrapped = {"stream": f"{symbol.lower()}@depth", "data": raw}
                        delta = parse_order_book_delta(wrapped)

                        if delta.first_update_id != last_update_id + 1:
                            logger.warning(
                                "order_book_gap_detected_reconciling",
                                symbol=symbol,
                                expected=last_update_id + 1,
                                got=delta.first_update_id,
                            )
                            break  # exit inner loop -> full reconciliation restarts

                        await queue.put(delta)
                        last_update_id = delta.final_update_id

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(
                    "order_book_disconnected_retrying",
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