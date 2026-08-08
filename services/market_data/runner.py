"""
services/market_data/runner.py

Connects Hansika's live data pipeline to the persistence layer.

Batching note: an earlier version opened a new session and committed
once per event. At ~3s per DB round-trip that could not keep pace with
the stream, so lag compounded (~3s added per event, reaching 55s within
minutes). This version reuses one session and commits in batches.

Run with:
    python -m services.market_data.runner
"""
import asyncio
import time
from datetime import datetime, timezone

import structlog
import yaml

from core.logging_config import configure_logging
from core.persistence.db import AsyncSessionLocal
from core.persistence.repository import stage_event
from services.market_data.adapters.binance import BinanceAdapter

log = structlog.get_logger("market_data.runner")

# Commit when EITHER threshold is hit. Tune against measured lag:
# bigger batches = lower lag, but more events lost if the process dies
# before a flush.
BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 5.0


def load_symbols(config_path: str = "config/exchange.yaml") -> list[str]:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config["binance"]["symbols"]


async def run():
    configure_logging()
    symbols = load_symbols()
    adapter = BinanceAdapter(config={})
    log.info("runner_starting", symbols=symbols, batch_size=BATCH_SIZE)

    pending = 0
    last_flush = time.monotonic()

    async def flush(session, count, reason):
        if count == 0:
            return 0
        try:
            await session.commit()
            log.debug("batch_committed", rows=count, reason=reason)
        except Exception as e:
            await session.rollback()
            log.error("batch_commit_failed", rows=count, error=str(e), exc_info=True)
        return 0

    async with AsyncSessionLocal() as session:
        try:
            async for event in adapter.stream_market_data(symbols):
                occurred_at = datetime.fromtimestamp(
                    event.event_time / 1000, tz=timezone.utc
                )
                try:
                    stage_event(
                        session,
                        event_type=event.event_type,
                        source="market_data",
                        payload=event.model_dump(mode="json"),
                        occurred_at=occurred_at,
                    )
                    pending += 1
                except ValueError as e:
                    # record/stage already logged the rejection; one bad
                    # event must not kill the stream.
                    log.error("event_persist_failed", error=str(e))
                    continue

                elapsed = time.monotonic() - last_flush
                if pending >= BATCH_SIZE or elapsed >= FLUSH_INTERVAL_SECONDS:
                    pending = await flush(session, pending, "threshold")
                    last_flush = time.monotonic()

        except asyncio.CancelledError:
            log.info("runner_cancelled")
            raise
        finally:
            # App Flow v2.0 §4: flush in-flight events before exiting.
            pending = await flush(session, pending, "shutdown")
            log.info("runner_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("interrupted_by_user")