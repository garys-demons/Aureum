"""
tests/unit/test_ai_reasoning_audit.py

Confirms core/persistence/ai_reasoning_audit.py correctly persists
AI Research Layer outputs, using the same background-thread pattern
Phase 6's risk_audit.py established, and never blocks or crashes the
caller if the write fails.

IMPORTANT TEST-DESIGN NOTE — a race condition worth knowing about
------------------------------------------------------------------
record_regime_assessment()/record_retrieval_match() start a background
thread and return immediately, WITHOUT waiting for that thread to
finish. If a test does:

    with patch.object(audit_module, "AsyncSessionLocal", session_factory):
        audit_module.record_regime_assessment(...)
    wait_for_write(...)   # <-- patch already undone by here!

the `with` block exits (undoing the patch) as soon as the synchronous
call returns — almost immediately, since starting a thread is fast.
The background thread itself runs a moment LATER, and may read
AsyncSessionLocal AFTER it's already been reverted to the real value,
silently writing to the wrong database (or failing) — an intermittent,
timing-dependent failure, not a deterministic one. This was caught
directly (some runs passed, some didn't, with the exact same code).

The fix used throughout this file: keep the patch active for the
ENTIRE wait, not just the synchronous part of the call.
"""
import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import patch

import core.persistence.ai_reasoning_audit as audit_module
from core.persistence.models import AuditCategory, Base
from core.persistence.repository import get_recent

# core.ai_reasoning (Samarth's Phase 7 branch) isn't merged into dev
# yet — this specific test needs it directly. Remove this skip once
# feature/ai-reasoning-layer merges; the test itself is already
# correct and ready.
try:
    from core.ai_reasoning.regime_classifier import classify_regime
    HAS_AI_REASONING = True
except ModuleNotFoundError:
    HAS_AI_REASONING = False


@pytest.fixture
async def session_factory(tmp_path):
    # A real temp FILE, not :memory: — the background thread creates
    # its own genuinely separate event loop, and async SQLite drivers
    # don't reliably share an in-memory database's state across
    # different event loops/threads even with connection-pool tricks
    # (confirmed directly: StaticPool alone did not fix this). A
    # file-based database sidesteps the problem entirely, since any
    # connection from any thread can open the same file on disk.
    db_path = tmp_path / "test_audit.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _wait_for_write(factory, category, timeout=2.0):
    """Background-thread writes aren't synchronous — poll briefly
    rather than a single fixed sleep, so this isn't flaky under load.
    MUST be called while the AsyncSessionLocal patch is still active —
    see module docstring."""
    import asyncio
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async def check():
            async with factory() as session:
                return await get_recent(session, category=category)
        rows = asyncio.run(check())
        if rows:
            return rows
        time.sleep(0.05)
    return []


def test_regime_assessment_persists_correctly(session_factory):
    with patch.object(audit_module, "AsyncSessionLocal", session_factory):
        audit_module.record_regime_assessment(
            symbol="ADAUSDT", regime="high_volatility", confidence=0.75,
            volatility=0.0025, rsi_value=48.0, reason="volatility exceeds threshold",
        )
        rows = _wait_for_write(session_factory, AuditCategory.DECISION)

    assert len(rows) == 1
    assert rows[0].event_type == "regime_classified"
    assert rows[0].payload["symbol"] == "ADAUSDT"
    assert rows[0].payload["regime"] == "high_volatility"
    assert rows[0].payload["confidence"] == 0.75


def test_regime_assessment_with_none_values_persists_correctly(session_factory):
    """classify_regime() returns None for volatility/rsi_value when
    there isn't enough history yet (Regime.UNKNOWN case) — confirms
    that round-trips correctly, not just the happy path."""
    with patch.object(audit_module, "AsyncSessionLocal", session_factory):
        audit_module.record_regime_assessment(
            symbol="ADAUSDT", regime="unknown", confidence=0.0,
            volatility=None, rsi_value=None, reason="insufficient history",
        )
        rows = _wait_for_write(session_factory, AuditCategory.DECISION)

    assert len(rows) == 1
    assert rows[0].payload["volatility"] is None
    assert rows[0].payload["rsi_value"] is None


def test_retrieval_match_persists_correctly(session_factory):
    """Ready for the retrieval mechanism, once built — no live code
    calls this yet, so this exercises it directly."""
    with patch.object(audit_module, "AsyncSessionLocal", session_factory):
        audit_module.record_retrieval_match(
            symbol="ADAUSDT",
            query_description="similar high-volatility conditions",
            matches=[
                {"timestamp": "2024-01-01T00:00:00Z", "similarity": 0.92},
                {"timestamp": "2024-02-15T00:00:00Z", "similarity": 0.87},
            ],
        )
        rows = _wait_for_write(session_factory, AuditCategory.DECISION)

    assert len(rows) == 1
    assert rows[0].event_type == "retrieval_match"
    assert rows[0].payload["match_count"] == 2
    assert len(rows[0].payload["matches"]) == 2


def test_never_raises_when_database_is_completely_broken():
    """The same fail-safe guarantee risk_audit.py established: a
    persistence failure must never propagate to the caller, and must
    never crash the background thread in a way that surfaces anywhere."""
    class BrokenSessionFactory:
        def __call__(self):
            raise ConnectionError("database is unreachable")

    with patch.object(audit_module, "AsyncSessionLocal", BrokenSessionFactory()):
        # Must return immediately without raising - the whole point of
        # the background-thread design.
        audit_module.record_regime_assessment(
            symbol="ADAUSDT", regime="ranging", confidence=0.5,
            volatility=0.001, rsi_value=50.0, reason="test",
        )
        time.sleep(0.3)  # let the background thread actually attempt and fail, patch still active


@pytest.mark.skipif(not HAS_AI_REASONING, reason="core.ai_reasoning not merged into dev yet")
def test_real_classify_regime_output_round_trips_through_persistence(session_factory):
    """
    End-to-end: a REAL classify_regime() call (not hand-built fields)
    persisted and confirmed correct — proves the two modules actually
    fit together, not just that each works in isolation.
    """
    # Enough history, deliberately flat, to reliably produce RANGING
    # rather than depending on random data for a deterministic test.
    prices = [0.180 + (0.00001 * (i % 3)) for i in range(30)]
    assessment = classify_regime(prices)

    with patch.object(audit_module, "AsyncSessionLocal", session_factory):
        audit_module.record_regime_assessment(
            symbol="ADAUSDT", regime=assessment.regime.value,
            confidence=assessment.confidence, volatility=assessment.volatility,
            rsi_value=assessment.rsi_value, reason=assessment.reason,
        )
        rows = _wait_for_write(session_factory, AuditCategory.DECISION)

    assert len(rows) == 1
    assert rows[0].payload["regime"] == assessment.regime.value
    assert rows[0].payload["reason"] == assessment.reason