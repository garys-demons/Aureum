"""
core/persistence/repository.py — read/write functions for the audit trail.

Other modules should import from here, not reach into models.py or db.py
directly — this is the seam where validation, redaction-before-storage,
etc. get added later without every caller needing to change.
"""

from datetime import datetime, timezone

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.persistence.models import AuditCategory, AuditLog
from services.market_data.models import (
    Candle,
    OrderBookDelta,
    OrderBookSnapshot,
    TickerEvent,
    TradeEvent,
)

log = structlog.get_logger("persistence")

# Maps Hansika's real MarketEvent.event_type values (confirmed against
# services/market_data/parsers.py, not guessed) to the Pydantic class
# that defines what a valid payload looks like for that type. Used by
# record_event() below to reject malformed market data before it's
# ever written to the audit trail, instead of silently storing it.
EVENT_TYPE_MODEL_MAP: dict[str, type] = {
    "ticker": TickerEvent,
    "trade": TradeEvent,
    "kline": Candle,
    "depth_snapshot": OrderBookSnapshot,
    "depth_update": OrderBookDelta,
}

def _validate_event_payload(event_type: str, source: str, payload: dict) -> None:
    """Shared validation used by both record_event() and stage_event()."""
    model_cls = EVENT_TYPE_MODEL_MAP.get(event_type)
    if model_cls is None:
        return
    try:
        model_cls(**payload)
    except ValidationError as e:
        log.error(
            "invalid_event_payload_rejected",
            event_type=event_type,
            source=source,
            error=str(e),
        )
        raise ValueError(
            f"payload for event_type={event_type!r} failed validation "
            f"against {model_cls.__name__}: {e}"
        ) from e


def stage_event(
    session: AsyncSession,
    *,
    event_type: str,
    source: str,
    payload: dict,
    occurred_at: datetime | None = None,
) -> AuditLog:
    """
    Validate and queue an event for writing, WITHOUT committing.

    Use this for high-throughput ingestion where the caller commits in
    batches (see services/market_data/runner.py). Committing per event
    costs a full DB round-trip each time, which cannot keep up with a
    live market data stream.

    Note: no session.refresh() here either — refresh is a second
    round-trip just to populate row.id, which batch callers don't need.
    """
    _validate_event_payload(event_type, source, payload)
    row = AuditLog(
        category=AuditCategory.EVENT,
        event_type=event_type,
        source=source,
        payload=payload,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    session.add(row)
    return row


async def record(
    session: AsyncSession,
    *,
    category: AuditCategory,
    event_type: str,
    source: str,
    payload: dict,
    occurred_at: datetime | None = None,
) -> AuditLog:
    """
    Write one audit row and commit.

    occurred_at defaults to "now" — pass it explicitly whenever you have
    a real event timestamp (e.g. the exchange's own timestamp on a
    trade), since occurred_at vs recorded_at drift is itself useful
    diagnostic signal.
    """
    row = AuditLog(
        category=category,
        event_type=event_type,
        source=source,
        payload=payload,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    log.debug(
        "audit_record_written",
        category=category.value,
        event_type=event_type,
        source=source,
        audit_id=str(row.id),
    )
    return row


async def record_event(session: AsyncSession, *, event_type: str, source: str, payload: dict,
                        occurred_at: datetime | None = None) -> AuditLog:
    """
    Records a market-data event.

    If event_type matches one of Hansika's known market-data types
    (see EVENT_TYPE_MODEL_MAP above), payload is validated against her
    real Pydantic model first — e.g. a "trade" payload with a negative
    price is rejected here (ValueError raised, nothing written) instead
    of being silently saved to the audit trail.

    Unrecognized event_types are saved as-is, unvalidated — this fails
    open rather than blocking new/future event types from being logged
    just because this map hasn't been updated for them yet.
    """
    model_cls = EVENT_TYPE_MODEL_MAP.get(event_type)
    if model_cls is not None:
        try:
            model_cls(**payload)
        except ValidationError as e:
            log.error(
                "invalid_event_payload_rejected",
                event_type=event_type,
                source=source,
                error=str(e),
            )
            raise ValueError(
                f"payload for event_type={event_type!r} failed validation "
                f"against {model_cls.__name__}: {e}"
            ) from e

    return await record(session, category=AuditCategory.EVENT, event_type=event_type,
                         source=source, payload=payload, occurred_at=occurred_at)


async def record_decision(session: AsyncSession, *, event_type: str, source: str, payload: dict,
                           occurred_at: datetime | None = None) -> AuditLog:
    return await record(session, category=AuditCategory.DECISION, event_type=event_type,
                         source=source, payload=payload, occurred_at=occurred_at)


async def record_execution(session: AsyncSession, *, event_type: str, source: str, payload: dict,
                            occurred_at: datetime | None = None) -> AuditLog:
    return await record(session, category=AuditCategory.EXECUTION, event_type=event_type,
                         source=source, payload=payload, occurred_at=occurred_at)


async def record_anomaly(session: AsyncSession, *, event_type: str, payload: dict,
                          occurred_at: datetime | None = None) -> AuditLog:
    return await record(session, category=AuditCategory.ANOMALY, event_type=event_type,
                         source="persistence", payload=payload, occurred_at=occurred_at)


async def get_recent(
    session: AsyncSession,
    *,
    category: AuditCategory | None = None,
    limit: int = 50,
) -> list[AuditLog]:
    """Most recent rows first — mainly for the future dashboard and for debugging."""
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit)
    if category is not None:
        stmt = stmt.where(AuditLog.category == category)
    result = await session.execute(stmt)
    return list(result.scalars().all())