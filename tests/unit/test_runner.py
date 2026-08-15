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
from services.market_data.models import Candle, OrderBookDelta, OrderBookSnapshot, PriceLevel, SnapshotSource, TradeEvent


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


def make_candle(is_closed: bool, close: float = 65100.0) -> Candle:
    """A real, valid Candle — same shape parse_candle_event() actually produces."""
    return Candle(
        event_type="kline", exchange="binance", symbol="BTCUSDT",
        event_time=1_700_000_000_000, received_time=1_700_000_000_050,
        interval="1m", open_time=1_700_000_000_000, close_time=1_700_000_060_000,
        open=65000.0, high=65150.0, low=64950.0, close=close, volume=12.5,
        is_closed=is_closed,
    )


async def test_closed_candle_gets_persisted(test_session_factory):
    """FR-6: a completed bar (is_closed=True) should be saved."""
    events = [make_candle(is_closed=True)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 1
    assert rows[0].payload["is_closed"] is True


async def test_in_progress_candle_is_not_persisted(test_session_factory):
    """
    FR-6's is_closed handling: an in-progress bar update (is_closed=False)
    should be skipped, not saved — Binance sends one of these on every
    trade within the interval, and persisting all of them would flood
    the audit trail with near-duplicate rows.
    """
    events = [make_candle(is_closed=False), make_candle(is_closed=False)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 0


async def test_mixed_open_and_closed_candles_only_persists_closed(test_session_factory):
    """A realistic sequence: several in-progress updates, then one final
    closed update — only the closed one should land in the audit trail."""
    events = [
        make_candle(is_closed=False, close=65050.0),
        make_candle(is_closed=False, close=65080.0),
        make_candle(is_closed=True, close=65100.0),
    ]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 1
    assert rows[0].payload["close"] == 65100.0


async def test_trade_events_unaffected_by_is_closed_filter(test_session_factory):
    """Sanity check: TradeEvent has no is_closed attribute at all, so the
    filter must not accidentally drop non-candle events."""
    events = [make_trade(1), make_trade(2)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 2


def make_order_book_snapshot(last_update_id: int = 500) -> OrderBookSnapshot:
    """A real, valid OrderBookSnapshot — same shape the unified
    stream_market_data() now yields for order book events (Phase 2
    unified-stream merge)."""
    return OrderBookSnapshot(
        event_type="depth_snapshot", exchange="binance", symbol="BTCUSDT",
        event_time=1_700_000_000_000, received_time=1_700_000_000_010,
        last_update_id=last_update_id, snapshot_time=1_700_000_000_000,
        source=SnapshotSource.RECONCILED,
        bids=[PriceLevel(price=99.0, quantity=1.0)],
        asks=[PriceLevel(price=101.0, quantity=1.0)],
    )


def make_order_book_delta(first_id: int, final_id: int) -> OrderBookDelta:
    return OrderBookDelta(
        event_type="depth_update", exchange="binance", symbol="BTCUSDT",
        event_time=1_700_000_001_000, received_time=1_700_000_001_010,
        first_update_id=first_id, final_update_id=final_id,
        bids=[PriceLevel(price=99.0, quantity=1.5)], asks=[],
    )


async def test_order_book_events_persist_through_unified_stream(test_session_factory):
    """
    Phase 2 unified-stream merge: order book events used to arrive
    through a SEPARATE event_source (adapter.stream_order_book(), run
    as its own _consume() task in runner.py). Now they're mixed into
    the same stream_market_data() feed as ticker/trade/candle. This
    confirms the single consumer correctly persists them without any
    special-case handling needed.
    """
    events = [
        make_trade(1),
        make_order_book_snapshot(500),
        make_order_book_delta(501, 501),
        make_trade(2),
    ]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 4
    event_types = sorted(r.event_type for r in rows)
    assert event_types == ["depth_snapshot", "depth_update", "trade", "trade"]


async def test_order_book_events_unaffected_by_is_closed_filter(test_session_factory):
    """Sanity check: neither OrderBookSnapshot nor OrderBookDelta have an
    is_closed attribute, so the candle-specific filter must not
    accidentally drop them (same style as the existing trade check)."""
    events = [make_order_book_snapshot(500), make_order_book_delta(501, 501)]

    await _run_with_fake_data(events, test_session_factory)

    async with test_session_factory() as session:
        rows = await get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 2