"""
Unit tests for core/persistence, run against in-memory SQLite —
no live Postgres/Timescale connection needed.

Note: this intentionally does NOT test against db.py's engine (that one
requires DATABASE_URL and a real Postgres/Timescale instance — see
README.md 'Database'). A separate integration test, run manually or in
CI with real credentials, should cover that. This file only tests that
the models and repository functions behave correctly in isolation.
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


async def test_record_event_round_trips(session):
    # Uses event_type="custom" (not a real Hansika market-data type) so
    # this test stays about generic persistence behavior, not coupled to
    # her schema — payload validation for real event types is covered
    # separately in test_event_validation.py.
    row = await repository.record_event(
        session,
        event_type="custom",
        source="market_data",
        payload={"symbol": "BTCUSDT", "price": "65000.5"},
    )
    assert row.category == AuditCategory.EVENT
    assert row.payload["symbol"] == "BTCUSDT"


async def test_get_recent_filters_by_category(session):
    await repository.record_event(
        session, event_type="custom", source="market_data", payload={}
    )
    await repository.record_decision(
        session, event_type="strategy_signal", source="ai_reasoning", payload={}
    )

    events_only = await repository.get_recent(session, category=AuditCategory.EVENT)
    assert len(events_only) == 1
    assert events_only[0].category == AuditCategory.EVENT


async def test_get_recent_orders_newest_first(session):
    import asyncio

    first = await repository.record_event(
        session, event_type="a", source="market_data", payload={}
    )
    await asyncio.sleep(0.01)
    second = await repository.record_event(
        session, event_type="b", source="market_data", payload={}
    )

    rows = await repository.get_recent(session)
    assert rows[0].id == second.id
    assert rows[1].id == first.id