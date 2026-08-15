"""
services/market_data/runner.py

Connects Hansika's live data pipeline to the persistence layer.

Batching note: an earlier version opened a new session and committed
once per event. At ~3s per DB round-trip that could not keep pace with
the stream, so lag compounded (~3s added per event, reaching 55s within
minutes). This version reuses one session and commits in batches
(Samarth's fix, fix/batch-persistence-writes).

Shutdown-flush note: the batched version's flush() silently swallowed
commit failures — on failure it rolled back and returned as if nothing
happened, so a DB error during the final shutdown flush meant that
batch was gone with only a log line, no way to recover it. Since
shutdown is the *last* chance to save that data, a failed shutdown
flush now writes the pending rows to a local JSON-lines fallback file.
Regular in-stream flushes still just log and continue (Aryan's fix,
fix/shutdown-flush-fallback).

Concurrency note (updated for the Phase 2 unified-stream merge):
market data (ticker/trade/candle) and the order book used to run as
two separate top-level tasks HERE in runner.py, each with its own
session. That's no longer how it works — BinanceAdapter.stream_market_data()
now runs both internally (as its own separate asyncio tasks, each with
independent reconnect/backoff) and merges everything onto one shared
queue, yielding it all through a single async generator. FR-12
(a book-stream failure must not interrupt ticker/trade) is now enforced
INSIDE the adapter, not by runner.py running separate consumers — see
BinanceAdapter._run_order_book_stream's own try/except/backoff loop.
runner.py's job is simpler now: consume that one merged stream and
persist whatever comes out of it, regardless of which original stream
it came from.

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

    event_source is an async iterator yielding MarketEvent models — as
    of the Phase 2 unified-stream merge, this is a SINGLE merged stream
    carrying ticker/trade/candle AND order book snapshot/delta events
    together (previously order book was a separate event_source with
    its own call to this function). No per-type branching is needed
    here: every event type sets its own event_type/event_time, and
    stage_event() already validates each one against the right Pydantic
    model based on that (see core/persistence/repository.py's
    EVENT_TYPE_MODEL_MAP — "depth_snapshot"/"depth_update" for order
    book events, alongside "ticker"/"trade"/"kline").
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
                # get saved. Every other event type (ticker/trade/depth
                # snapshot/depth delta) has no is_closed attribute at all,
                # so getattr(..., True) is a no-op for them — this only
                # actually filters candles.
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


async def run():
    """
    Single consumer against the unified stream_market_data() feed.

    Before the Phase 2 unified-stream merge, this ran TWO separate
    _consume() tasks — one for market data, one for the order book,
    each connecting and reconnecting independently. That's no longer
    needed: BinanceAdapter now does that internal separation itself
    (see the module docstring), so there is only one event_source to
    consume here.
    """
    configure_logging()
    symbols = load_symbols()
    adapter = BinanceAdapter(config={})
    log.info("runner_starting", symbols=symbols, batch_size=BATCH_SIZE)

    await _consume(adapter.stream_market_data(symbols), "market_data")

    log.info("runner_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("interrupted_by_user")