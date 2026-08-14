"""
core/persistence/models.py — the durable audit trail table.

WHY ONE TABLE, NOT THREE
-------------------------
The working model doc describes this as owning "the durable record of
events, decisions, and executions." Right now core/events and core/models
are still empty stubs (Hansika hasn't landed MarketEvent/TradeEvent/etc
yet), so there's nothing to bind a strict per-type schema to.

Rather than block on that, this is one wide, append-only table with a
`category` discriminator (event / decision / execution) and a JSONB
`payload` column for whatever shape that category's data actually has.
This is also the right shape for TimescaleDB: a single time-series table
keyed on `occurred_at`, which we turn into a hypertable (see the note
at the bottom of this file — that step isn't automatic from SQLAlchemy
and needs to be run once, ideally via an Alembic migration).

Once Hansika's Pydantic models exist, `payload` should validate against
them before insert (repository.py is the natural place to add that) —
but the table shape itself shouldn't need to change.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditCategory(str, enum.Enum):
    EVENT = "event"  # e.g. a market data event that came in
    DECISION = "decision"  # e.g. a signal/decision from core/strategy
    EXECUTION = "execution"  # e.g. an order placed via core/execution
    ANOMALY = "anomaly"  # flagged by core/persistence/anomaly.py


class AuditLog(Base):
    """
    One row = one thing that happened, with enough context to
    reconstruct "what did the system see, decide, and do" after the fact.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    category: Mapped[AuditCategory] = mapped_column(Enum(AuditCategory), nullable=False)

    # For EVENT-category rows, this should match Hansika's actual
    # MarketEvent.event_type values from services/market_data/models.py:
    # "trade", "depth", "kline", "ticker" (short, lowercase — confirmed
    # against her real code, not guessed). For DECISION/EXECUTION/ANOMALY
    # rows, this is our own free-form label, e.g. "strategy_signal",
    # "order_placed", "sequence_gap" — indexed either way, since this
    # is the field you'll filter on most when debugging.
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Which module produced this — "market_data", "ai_reasoning",
    # "execution", "persistence" (for anomalies detected here).
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    # The actual data. JSON here (not JSONB-specific) so this also works
    # against a local sqlite DB for cheap tests; on Postgres/Timescale
    # SQLAlchemy maps this to JSONB automatically.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # When the underlying thing actually happened (e.g. exchange
    # timestamp on a trade). This is what TimescaleDB partitions on.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # When we wrote the row — usually milliseconds after occurred_at,
    # but worth keeping both: a gap between them is itself diagnostic.
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_log_category_occurred_at", "category", "occurred_at"),
        Index("ix_audit_log_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.category.value}/{self.event_type} "
            f"from={self.source} at={self.occurred_at.isoformat()}>"
        )


# ---------------------------------------------------------------------
# TimescaleDB hypertable — NOT automatic, run once after table creation
# ---------------------------------------------------------------------
# SQLAlchemy's create_all() / Alembic will create audit_log as a normal
# Postgres table. To get Timescale's time-partitioning benefits, this
# raw SQL needs to run once against the DB (best done as a follow-up
# Alembic migration, so it's tracked like any other schema change):
#
#   SELECT create_hypertable('audit_log', 'occurred_at');
#
# See: https://docs.tigerdata.com/getting-started/latest/tables-hypertables/