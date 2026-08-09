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
shutdown is the *last* chance to save that data (no more events are
coming to make up for it), a failed shutdown flush now writes the
pending rows to a local JSON-lines fallback file instead of just
losing them. Regular in-stream flushes still just log and continue —
losing at most one batch mid-stream while the stream itself keeps
running is a smaller problem than a full stop, and is a reasonable
Phase 1 tradeoff; the shutdown case is the one where "log and move on"
isn't good enough, since there's nothing left to move on to.

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
# before a flush. 100 / 5s is a starting point, not a final answer —
# worth revisiting once we know real throughput (100 events could be a
# few seconds of BTCUSDT trade+ticker data, or much less on a quieter
# symbol — that ratio is what actually determines the real risk).
BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 5.0

FAILED_BATCH_DIR = Path("failed_batches")


def _write_fallback_batch(rows: list) -> None:
    """
    Last-resort recovery path: called only when the SHUTDOWN flush
    itself fails. Writes the rows that were about to be committed to a
    local JSON-lines file, so the data can be manually inspected and
    re-imported later instead of being silently gone. Not used for
    regular in-stream flush failures — those log and continue, since
    more events are still coming.
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


async def run():
    configure_logging()
    symbols = load_symbols()
    adapter = BinanceAdapter(config={})
    log.info("runner_starting", symbols=symbols, batch_size=BATCH_SIZE)

    pending_rows = []
    last_flush = time.monotonic()

    async def flush(session, rows, reason):
        if not rows:
            return []
        try:
            await session.commit()
            log.debug("batch_committed", rows=len(rows), reason=reason)
            return []
        except Exception as e:
            await session.rollback()
            log.error(
                "batch_commit_failed",
                rows=len(rows),
                reason=reason,
                error=str(e),
                exc_info=True,
            )
            if reason == "shutdown":
                _write_fallback_batch(rows)
                return []  # fallback file written, nothing left pending
            # In-stream failure: drop this batch (already logged above)
            # and keep the stream running rather than crashing it.
            return []

    async with AsyncSessionLocal() as session:
        try:
            async for event in adapter.stream_market_data(symbols):
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
                    # record/stage already logged the rejection; one bad
                    # event must not kill the stream.
                    log.error("event_persist_failed", error=str(e))
                    continue

                elapsed = time.monotonic() - last_flush
                if len(pending_rows) >= BATCH_SIZE or elapsed >= FLUSH_INTERVAL_SECONDS:
                    pending_rows = await flush(session, pending_rows, "threshold")
                    last_flush = time.monotonic()

        except asyncio.CancelledError:
            log.info("runner_cancelled")
            raise
        finally:
            # App Flow v2.0 §4: flush in-flight events before exiting.
            # This is the one flush() call where failure now has a
            # fallback (see _write_fallback_batch above) instead of
            # just a log line, since nothing else will save this data.
            pending_rows = await flush(session, pending_rows, "shutdown")
            log.info("runner_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("interrupted_by_user")