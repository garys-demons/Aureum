"""
tests/unit/test_event_validation.py

Confirms record_event() actually enforces Hansika's real market-data
schema (services/market_data/models.py) — a valid TradeEvent-shaped
payload should save; an invalid one (e.g. negative price) should be
rejected outright, with nothing written to the database.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.persistence import repository
from core.persistence.models import AuditCategory, Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


VALID_TRADE_PAYLOAD = {
    "event_type": "trade",
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "event_time": 1_700_000_000_000,
    "received_time": 1_700_000_000_050,
    "trade_id": 12345,
    "price": 65000.5,
    "quantity": 0.01,
    "buyer_maker": True,
    "trade_time": 1_700_000_000_000,
}


async def test_valid_trade_payload_saves_successfully(session):
    row = await repository.record_event(
        session,
        event_type="trade",
        source="market_data",
        payload=VALID_TRADE_PAYLOAD,
    )
    assert row.category == AuditCategory.EVENT
    assert row.payload["price"] == 65000.5


async def test_invalid_trade_payload_is_rejected_and_not_saved(session):
    bad_payload = dict(VALID_TRADE_PAYLOAD, price=-50)  # TradeEvent requires price > 0

    with pytest.raises(ValueError, match="failed validation"):
        await repository.record_event(
            session,
            event_type="trade",
            source="market_data",
            payload=bad_payload,
        )

    # The whole point: nothing should have been written.
    rows = await repository.get_recent(session, category=AuditCategory.EVENT)
    assert len(rows) == 0


async def test_trade_payload_missing_required_field_is_rejected(session):
    incomplete_payload = {k: v for k, v in VALID_TRADE_PAYLOAD.items() if k != "trade_id"}

    with pytest.raises(ValueError, match="failed validation"):
        await repository.record_event(
            session,
            event_type="trade",
            source="market_data",
            payload=incomplete_payload,
        )


async def test_unrecognized_event_type_saves_without_validation(session):
    """
    Event types not in EVENT_TYPE_MODEL_MAP fail open (save as-is) —
    this is deliberate, so logging a brand-new event type isn't blocked
    just because this map hasn't been updated for it yet.
    """
    row = await repository.record_event(
        session,
        event_type="some_future_event_type",
        source="market_data",
        payload={"anything": "goes"},
    )
    assert row.payload == {"anything": "goes"}