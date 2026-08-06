"""
core/persistence/repository.py — read/write functions for the audit trail.

Other modules should import from here, not reach into models.py or db.py
directly — this is the seam where validation, redaction-before-storage,
etc. get added later without every caller needing to change.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.persistence.models import AuditCategory, AuditLog

log = structlog.get_logger("persistence")


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