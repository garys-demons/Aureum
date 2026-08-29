"""
Tests for the Phase 6 kill switch. Fail-safe correctness matters more
here than almost anywhere else in the codebase - test the failure
paths explicitly, not just the happy path.
"""
import pytest
from core.risk.kill_switch import KillSwitch, TriggerCategory


def test_starts_inactive():
    ks = KillSwitch()
    assert ks.is_active is False


def test_trigger_activates():
    ks = KillSwitch()
    ks.trigger(TriggerCategory.EXTREME_VOLATILITY, "2.3% move in 60s")
    assert ks.is_active is True


def test_trigger_records_first_cause_not_latest():
    """Fail-safe: once tripped, the ORIGINAL reason matters, not whatever fires next."""
    ks = KillSwitch()
    ks.trigger(TriggerCategory.ORDER_BOOK_GAP, "gap detected")
    ks.trigger(TriggerCategory.EXTREME_VOLATILITY, "also volatile")

    status = ks.status()
    assert status["category"] == "order_book_gap"
    assert status["reason"] == "gap detected"


def test_reset_requires_confirmed_by():
    ks = KillSwitch()
    ks.trigger(TriggerCategory.RECONNECT_STORM, "4 reconnects in 60s")

    with pytest.raises(ValueError):
        ks.reset(confirmed_by="")

    assert ks.is_active is True  # still active - the bad reset must not have silently succeeded


def test_reset_with_valid_confirmation_deactivates():
    ks = KillSwitch()
    ks.trigger(TriggerCategory.RECONNECT_STORM, "4 reconnects in 60s")
    ks.reset(confirmed_by="samarth")

    assert ks.is_active is False
    assert ks.status()["reason"] is None


def test_status_when_never_triggered():
    ks = KillSwitch()
    status = ks.status()
    assert status["active"] is False
    assert status["category"] is None
    assert status["triggered_at"] is None