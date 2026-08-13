"""
services/market_data/runner.py

Connects Hansika's live data pipeline to the persistence layer.

Batching note: an earlier version opened a new session and committed
once per event. At ~3s per DB round-trip that could not keep pace with
the stream, so lag compounded (~3s added per event, reaching 55s within
minutes). This version reuses one session per consumer and commits in
batches (Samarth's fix, fix/batch-persistence-writes).

Shutdown-flush note: the batched version's flush() silently swallowed
commit failures — on failure it rolled back and returned as if nothing
happened, so a DB error during the final shutdown flush meant that
batch was gone with only a log line, no way to recover it. Since
shutdown is the *last* chance to save that data, a failed shutdown
flush now writes the pending rows to a local JSON-lines fallback file.
Regular in-stream flushes still just log and continue (Aryan's fix,
fix/shutdown-flush-fallback).

Concurrency note: market data (trade/ticker) and the order book run as
two independent tasks on separate WebSocket connections and separate DB
sessions. This is what TRD §6.2 / FR-12 require — a book-stream
reconnect triggers reconciliation without interrupting trade/ticker
flow. Each task catches its own exceptions so one failing stream never
takes the other down.

Run with:
    python -m services.market_data.runner
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
import yaml

from core.logging_config import configure_logging
from core.persistence.db import AsyncSessionLocal
from core.persistence.repository import stage_event
from services.market_data.adapters.binance import BinanceAdapter

log = structlog.get_logger("market_data.runner")

# Commit when EITHER threshold is hit. Tune against measured lag:
# bigger batches = lower lag, but more events lost if the process dies
# before a flush. 100 / 5s is a starting point, not a final answer.
BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 5.0

FAILED_BATCH_DIR = Path("failed_batches")


def _write_fallback_batch(rows: list) -> None:
    """
    Last-resort recovery path: called only when the SHUTDOWN flush
    itself fails. Writes the rows that were about to be committed to a
    local JSON-lines file, so the data can be manually inspected and
    re-imported later instead of being silently gone.
    """
    FAILED_BATCH_DIR.mkdir(exist_ok=True)
    filename = FAILED_BATCH_DIR / f"failed_batch_{int(time.time())}.jsonl"
    with open(filename, "w") as f:
        for row in rows:
            f.write(json.dumps({
                "event_type": row.event_type,
                "source": row.source,
                "payload": row.payload,
                "occurred_at": row.occurred_at.isoformat(),
            }) + "\n")
    log.error(
        "shutdown_flush_failed_wrote_fallback",
        rows=len(rows),
        fallback_file=str(filename),
    )


def load_symbols(config_path: str = "config/exchange.yaml") -> list[str]:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config["binance"]["symbols"]


async def _flush(session, rows, reason, stream):
    """Commit a batch. Returns the new pending list (always empty)."""
    if not rows:
        return []
    try:
        await session.commit()
        log.debug("batch_committed", rows=len(rows), reason=reason, stream=stream)
        return []
    except Exception as e:
        await session.rollback()
        log.error(
            "batch_commit_failed",
            rows=len(rows),
            reason=reason,
            stream=stream,
            error=str(e),
            exc_info=True,
        )
        if reason == "shutdown":
            _write_fallback_batch(rows)
        # In-stream failure: drop this batch (already logged) and keep
        # the stream running rather than crashing it.
        return []


async def _consume(event_source, stream_name: str):
    """
    Shared batching/persistence loop.

    event_source is an async iterator yielding MarketEvent models. Each
    consumer gets its own session — SQLAlchemy sessions are not safe to
    share across concurrent tasks.
    """
    pending_rows = []
    last_flush = time.monotonic()

    async with AsyncSessionLocal() as session:
        try:
            async for event in event_source:
                # Candles arrive as a stream of updates per bar — every
                # trade within the interval triggers one, with is_closed
                # only True on the final update (FR-6). Persisting every
                # in-progress update would flood the audit trail with
                # near-duplicate rows for no real benefit once the bar
                # closes with the final OHLCV values, so only closed bars
                # get saved. Ticker/trade/depth events have no is_closed
                # attribute at all, so getattr(..., True) is a no-op for
                # them — this only actually filters candles.
                if not getattr(event, "is_closed", True):
                    continue

                occurred_at = datetime.fromtimestamp(
                    event.event_time / 1000, tz=timezone.utc
                )
                try:
                    row = stage_event(
                        session,
                        event_type=event.event_type,
                        source="market_data",
                        payload=event.model_dump(mode="json"),
                        occurred_at=occurred_at,
                    )
                    pending_rows.append(row)
                except ValueError as e:
                    log.error("event_persist_failed", stream=stream_name, error=str(e))
                    continue

                elapsed = time.monotonic() - last_flush
                if len(pending_rows) >= BATCH_SIZE or elapsed >= FLUSH_INTERVAL_SECONDS:
                    pending_rows = await _flush(session, pending_rows, "threshold", stream_name)
                    last_flush = time.monotonic()

        except asyncio.CancelledError:
            log.info("consumer_cancelled", stream=stream_name)
            raise
        except Exception as e:
            # One stream failing must not take the other down (FR-12).
            log.error("consumer_failed", stream=stream_name, error=str(e), exc_info=True)
        finally:
            # The task may already be cancelled here, in which case a bare
            # `await session.commit()` is interrupted immediately and leaves
            # the session broken (PendingRollbackError). shield() lets the
            # final flush complete before cancellation takes effect.
            try:
                await asyncio.shield(
                    _flush(session, pending_rows, "shutdown", stream_name)
                )
            except asyncio.CancelledError:
                log.warning("shutdown_flush_interrupted", stream=stream_name)
                _write_fallback_batch(pending_rows)
            log.info("consumer_stopped", stream=stream_name)


async def _book_events(adapter, symbol: str):
    """Adapt stream_order_book's (delta, book) tuples to bare delta events."""
    async for delta, book in adapter.stream_order_book(symbol):
        yield delta


async def run():
    configure_logging()
    symbols = load_symbols()
    adapter = BinanceAdapter(config={})
    log.info("runner_starting", symbols=symbols, batch_size=BATCH_SIZE)

    tasks = [
        asyncio.create_task(
            _consume(adapter.stream_market_data(symbols), "market_data"),
            name="market_data",
        ),
        asyncio.create_task(
            _consume(_book_events(adapter, symbols[0]), "order_book"),
            name="order_book",
        ),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("runner_cancelled")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        log.info("runner_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("interrupted_by_user")