"""
core/persistence/ai_reasoning_audit.py — Phase 7.

Persists AI Research Layer outputs (reasoning results, retrieval
matches) through the SAME audit_log mechanism already used elsewhere
(repository.record_decision()) — no new persistence mechanism, per the
task list, matching the exact precedent Phase 6's risk_audit.py set:
reuse AuditCategory.DECISION with a distinguishing event_type, rather
than introducing a new category.

SYNC/ASYNC BRIDGE — SAME PATTERN AS risk_audit.py, DELIBERATELY
--------------------------------------------------------------------
core.ai_reasoning.regime_classifier.classify_regime() is a pure,
synchronous function (no I/O). Persistence is async. Rather than invent
a second bridging technique, this mirrors risk_audit.py's approach
exactly: hand the write off to a background thread with its own fresh
event loop (asyncio.run() is safe there specifically because that
thread never has a pre-existing loop of its own), so the caller never
blocks on a database round-trip.

ZERO LIVE INFLUENCE — THIS FILE IS INTENTIONALLY OUTSIDE core/ai_reasoning/
--------------------------------------------------------------------------
This lives in core/persistence/, not core/ai_reasoning/, on purpose:
Phase 7's isolation test (test_ai_reasoning_isolation.py) specifically
scans core/ai_reasoning/ for forbidden imports of core.execution or
core.risk — keeping persistence code out of that directory means it's
scanned by this file's OWN isolation test
(test_ai_reasoning_audit_isolation.py) instead, without needing to
touch or extend Samarth's existing test. Either way, this module
itself never imports core.execution or core.risk — it only writes an
audit record of what the reasoning layer produced, nothing more.

NO LIVE CALL SITE YET
--------------------------
Unlike Phase 6 (executor.py's risk_check() was an existing, single,
unbypassable choke point to wire into), nothing currently calls
classify_regime() in a live loop — it's only exercised by tests today.
This module is the ready-to-use persistence utility for whoever wires
a real reasoning loop together (Samarth's likely next step); there's
no existing call site to modify yet, so none was invented here.
"""
import asyncio
import threading
from datetime import datetime, timezone

import structlog

from core.persistence.db import AsyncSessionLocal
from core.persistence.repository import record_decision

log = structlog.get_logger("ai_reasoning_audit")


async def _record_regime_assessment_async(
    *,
    symbol: str,
    regime: str,
    confidence: float,
    volatility: float | None,
    rsi_value: float | None,
    reason: str,
) -> None:
    payload = {
        "symbol": symbol,
        "regime": regime,
        "confidence": confidence,
        "volatility": volatility,
        "rsi_value": rsi_value,
        "reason": reason,
    }
    async with AsyncSessionLocal() as session:
        await record_decision(
            session,
            event_type="regime_classified",
            source="ai_reasoning",
            payload=payload,
        )


async def _record_retrieval_match_async(
    *,
    symbol: str,
    query_description: str,
    matches: list[dict],
) -> None:
    """
    Ready for the retrieval mechanism (Phase 7 task, not yet built as
    of this file — core/ai_reasoning/ currently only has the regime
    classifier). matches: whatever shape the retrieval component ends
    up returning for "historically similar conditions" — kept as a
    plain list of dicts here rather than a specific dataclass, since
    that shape doesn't exist yet to import against.
    """
    payload = {
        "symbol": symbol,
        "query_description": query_description,
        "matches": matches,
        "match_count": len(matches),
    }
    async with AsyncSessionLocal() as session:
        await record_decision(
            session,
            event_type="retrieval_match",
            source="ai_reasoning",
            payload=payload,
        )


def _write_in_background(coro_factory) -> None:
    """
    Runs in its own thread. asyncio.run() creates a fresh event loop —
    safe here specifically because this is a brand-new thread with no
    event loop of its own already running (same reasoning as
    risk_audit.py's identical pattern).
    """
    try:
        asyncio.run(coro_factory())
    except Exception as e:
        try:
            log.error("ai_reasoning_audit_write_failed", error=str(e), exc_info=True)
        except Exception:
            pass


def record_regime_assessment(
    *,
    symbol: str,
    regime: str,
    confidence: float,
    volatility: float | None,
    rsi_value: float | None,
    reason: str,
) -> None:
    """
    Sync entry point — persists one classify_regime() output. Returns
    immediately; the actual database write happens in a background
    thread so a slow/unavailable database never delays reasoning.

    Accepts plain fields rather than a RegimeAssessment object
    directly, so this module has no import-time dependency on
    core.ai_reasoning's dataclass shape — callers unpack it themselves
    (e.g. record_regime_assessment(**vars(assessment), symbol=...)),
    keeping this file's own dependency surface minimal.
    """
    thread = threading.Thread(
        target=_write_in_background,
        args=(lambda: _record_regime_assessment_async(
            symbol=symbol, regime=regime, confidence=confidence,
            volatility=volatility, rsi_value=rsi_value, reason=reason,
        ),),
        daemon=True,
    )
    thread.start()


def record_retrieval_match(
    *,
    symbol: str,
    query_description: str,
    matches: list[dict],
) -> None:
    """Sync entry point for the retrieval mechanism, once built — same
    fire-and-forget background-thread pattern as record_regime_assessment()."""
    thread = threading.Thread(
        target=_write_in_background,
        args=(lambda: _record_retrieval_match_async(
            symbol=symbol, query_description=query_description, matches=matches,
        ),),
        daemon=True,
    )
    thread.start()