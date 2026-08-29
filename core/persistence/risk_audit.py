"""
core/persistence/risk_audit.py — Phase 6.

Persists every risk decision (allowed, rejected, kill-switch triggered)
through the SAME audit_log mechanism already used elsewhere in the
project (repository.record_decision()) — no new persistence mechanism,
per the Phase 6 task list.

The risk engine and executor are both plain synchronous functions, but
saving to the database is async AND slow (network round-trip to the
DB). record_risk_decision() is the sync entry point executor.py calls;
it hands the actual write off to a background thread so risk_check()
returns immediately rather than blocking every single order on a slow
database write.

Fail-safe note: a failure to WRITE the audit record must never block or
crash order execution. Since the write now happens after risk_check()
has already returned, this is even more true than before — errors are
caught and logged INSIDE the background thread, with nowhere else for
them to go. If audit-write reliability ever becomes a concern, that's a
signal to add a retry queue — out of scope for Phase 6.
"""
import asyncio
import threading

import structlog

from core.persistence.db import AsyncSessionLocal
from core.persistence.repository import record_decision

log = structlog.get_logger("risk_audit")


async def _record_risk_decision_async(
    *,
    action: str,
    symbol: str,
    quantity: float,
    current_inventory: float,
    allowed: bool,
    kill_switch_status: dict,
) -> None:
    if kill_switch_status.get("active"):
        event_type = "kill_switch_triggered"
    elif allowed:
        event_type = "risk_allowed"
    else:
        event_type = "risk_rejected"

    payload = {
        "action": action,
        "symbol": symbol,
        "quantity": quantity,
        "current_inventory": current_inventory,
        "allowed": allowed,
        "kill_switch": kill_switch_status,
    }

    async with AsyncSessionLocal() as session:
        await record_decision(
            session,
            event_type=event_type,
            source="risk_engine",
            payload=payload,
        )


def _write_in_background(**kwargs) -> None:
    """
    Runs in its own thread. asyncio.run() creates a fresh event loop —
    safe here specifically because this is a brand-new thread with no
    event loop of its own already running.
    """
    try:
        asyncio.run(_record_risk_decision_async(**kwargs))
    except Exception as e:
        try:
            log.error("risk_decision_audit_write_failed", error=str(e), exc_info=True)
        except Exception:
            pass


def record_risk_decision(
    *,
    action: str,
    symbol: str,
    quantity: float,
    current_inventory: float,
    allowed: bool,
    kill_switch_status: dict,
) -> None:
    """
    Sync entry point for executor.py. Returns immediately — the actual
    database write happens in a background thread so a slow/unavailable
    database never delays a real trading decision.

    daemon=True: if the whole program exits, this thread should not
    keep it alive waiting to finish a write.
    """
    thread = threading.Thread(
        target=_write_in_background,
        kwargs=dict(
            action=action,
            symbol=symbol,
            quantity=quantity,
            current_inventory=current_inventory,
            allowed=allowed,
            kill_switch_status=kill_switch_status,
        ),
        daemon=True,
    )
    thread.start()