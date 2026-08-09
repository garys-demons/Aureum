"""
tests/unit/test_runner.py

Tests services/market_data/runner.py's run() loop itself — the piece
that was silently disconnected from persistence for days before anyone
noticed. Unlike test_runner_fallback.py (which tests the fallback-file
recovery path in isolation), this file drives the real run() loop
end-to-end with a fake adapter and a real in-memory SQLite session, to
confirm events actually get persisted, bad events don't kill the
stream, and nothing pending is lost when the stream ends.

No real Binance connection and no real shared database are touched —
BinanceAdapter and AsyncSessionLocal are both patched for the duration
of each test.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import services.market_data.runner as runner_module
from core.persistence.models import AuditCategory, Base
from core.persistence.repository import get_recent
from services.market_data.models import TradeEvent


def make_trade(trade_id: int, price: float = 65000.5) -> TradeEvent:
    """A real, valid TradeEvent — same shape Hansika's adapter actually yields."""
    return TradeEvent(
        event_type="trade", exchange="binance", symbol="BTCUSDT",
        event_time=1_700_000_000_000, received_time=1_700_000_000_050,
        trade_id=trade_id, price=price, quantity=0.01,
        buyer_maker=True, trade_time=1_700_000_000_000,
    )


class FakeAdapter:
    """Stands in for BinanceAdapter — yields a pre-set list of events/dicts
    instead of connecting to a real exchange."""

    def __init__(self, events, config=None):
        self._events = events

    async def stream_market_data(self, symbols):
        for item in self._events:
            yield item


@pytest.fixture
async def test_session_factory():
    """A real in-memory SQLite session, standing in for the shared DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _run_with_fake_data(events, test_session_factory, batch_size=100):
    """Runs the real run() loop with a fake adapter and a test DB session."""
    with patch.object(runner_module, "BinanceAdapter", lambda config: FakeAdapter(events)), \
         patch.object(runner_module, "AsyncSessionLocal", test_session_factory), \
         patch.object(runner_module, "BATCH_SIZE", batch_size), \
         patch.object(runner_module, "configure_logging", lambda: None):
        await runner_module.run()


async def test_valid_events_get_persisted(test_session_factory):
    events = [make_trade(1), make_trade(2), make_trade(3)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 3


async def test_invalid_event_does_not_kill_the_stream(test_session_factory):
    """
    A corrupted event (here: something claiming to be a "trade" but
    missing required fields when dumped) should be rejected by
    stage_event()'s validation and skipped — not crash the whole run,
    and not block the valid events around it from being saved.
    """

    class CorruptedTradeEvent:
        """Has the same interface run() expects (event_type, event_time,
        model_dump()) but produces an incomplete payload — simulating
        real-world corruption rather than a wrong type entirely."""
        event_type = "trade"
        event_time = 1_700_000_000_000

        def model_dump(self, mode="json"):
            return {"event_type": "trade", "symbol": "BTCUSDT"}  # missing required fields

    events = [make_trade(1), CorruptedTradeEvent(), make_trade(2)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    # Only the 2 valid trades should have made it through.
    assert len(rows) == 2


async def test_remaining_events_flushed_on_stream_end(test_session_factory):
    """
    With BATCH_SIZE set high, none of these events would hit the
    threshold flush mid-stream — they should still be saved via the
    shutdown flush once the (fake) stream naturally ends.
    """
    events = [make_trade(1), make_trade(2)]

    await _run_with_fake_data(events, test_session_factory, batch_size=1000)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 2