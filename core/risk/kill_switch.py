"""
Kill switch — Phase 6. A hard stop that halts all new order signals
when triggered. Fail-safe by design: once triggered, stays triggered
until someone explicitly resets it. No silent auto-resume.
"""
from datetime import datetime, timezone
from enum import Enum


class TriggerCategory(str, Enum):
    ORDER_BOOK_GAP = "order_book_gap"
    RECONNECT_STORM = "reconnect_storm"
    EXTREME_VOLATILITY = "extreme_volatility"


class KillSwitch:
    def __init__(self):
        self._active = False
        self._reason: str | None = None
        self._category: TriggerCategory | None = None
        self._triggered_at: datetime | None = None

    def trigger(self, category: TriggerCategory, reason: str) -> None:
        """
        Activate the kill switch. Idempotent - triggering an already-active
        switch just logs, doesn't overwrite the original trigger reason
        (you want to know what FIRST tripped it, not the latest).
        """
        if self._active:
            return  # already tripped; first cause is what matters
        self._active = True
        self._category = category
        self._reason = reason
        self._triggered_at = datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return self._active

    def status(self) -> dict:
        return {
            "active": self._active,
            "category": self._category.value if self._category else None,
            "reason": self._reason,
            "triggered_at": self._triggered_at.isoformat() if self._triggered_at else None,
        }

    def reset(self, confirmed_by: str) -> None:
        """
        Explicit, deliberate re-enable. Requires a human name/identifier -
        no anonymous or automatic resets. This is the one place the
        fail-safe gets deliberately overridden, so it should never be
        silent or accidental.
        """
        if not confirmed_by:
            raise ValueError("reset() requires confirmed_by - no anonymous resets")
        self._active = False
        self._reason = None
        self._category = None
        self._triggered_at = None