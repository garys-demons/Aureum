"""
services/market_data/runner.py

The missing connector between Hansika's live data pipeline and the
persistence layer. Before this file existed, her BinanceAdapter
correctly parsed and yielded events, but nothing was listening —
every event was produced and then immediately discarded, since
nothing called core.persistence.repository.record_event() on it.

Run with:
    PYTHONPATH=. python services/market_data/runner.py
"""

import asyncio
from datetime import datetime, timezone

import structlog
import yaml

from core.logging_config import configure_logging
from core.persistence.db import AsyncSessionLocal
from core.persistence.repository import record_event
from services.market_data.adapters.binance import BinanceAdapter

log = structlog.get_logger("market_data.runner")


def load_symbols(config_path: str = "config/exchange.yaml") -> list[str]:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config["binance"]["symbols"]


async def run():
    configure_logging()
    symbols = load_symbols()
    adapter = BinanceAdapter(config={})

    log.info("runner_starting", symbols=symbols)

    async for event in adapter.stream_market_data(symbols):
        # event is one of Hansika's real Pydantic models (TradeEvent,
        # TickerEvent, etc.) — event.event_type is already the exact
        # short string ("trade", "ticker", ...) that
        # repository.EVENT_TYPE_MODEL_MAP expects, and event_time (Unix
        # ms, present on every MarketEvent subtype) becomes occurred_at.
        occurred_at = datetime.fromtimestamp(event.event_time / 1000, tz=timezone.utc)

        async with AsyncSessionLocal() as session:
            try:
                await record_event(
                    session,
                    event_type=event.event_type,
                    source="market_data",
                    payload=event.model_dump(mode="json"),
                    occurred_at=occurred_at,
                )
            except ValueError as e:
                # record_event() already logs the rejection internally
                # (invalid_event_payload_rejected) — catching here just
                # keeps one bad event from crashing the whole stream.
                log.error("event_persist_failed", error=str(e))


if __name__ == "__main__":
    asyncio.run(run())