"""
Tests for kill_switch_triggers.py (Phase 6). Uses the real KillSwitch
and TriggerCategory (core.risk.kill_switch), confirmed against
Samarth's feature/risk-engine branch.
"""
from core.persistence.anomaly import ReconnectFrequencyMonitor
from core.persistence.volatility_anomaly import ExtremeVolatilityMonitor
from core.persistence import kill_switch_triggers as triggers
from core.risk.kill_switch import KillSwitch, TriggerCategory


def test_check_order_book_gap_triggers_on_gap():
    ks = KillSwitch()
    triggers.check_order_book_gap(ks, gap_detected=True, stream_key="BTCUSDT@depth")

    assert ks.is_active is True
    assert ks.status()["category"] == TriggerCategory.ORDER_BOOK_GAP.value


def test_check_order_book_gap_does_not_trigger_when_no_gap():
    ks = KillSwitch()
    triggers.check_order_book_gap(ks, gap_detected=False, stream_key="BTCUSDT@depth")

    assert ks.is_active is False


def test_check_reconnect_storm_triggers_when_exceeded():
    ks = KillSwitch()
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=1)

    monitor.record_reconnect("BTCUSDT@depth")
    result = triggers.check_reconnect_storm(ks, monitor, "BTCUSDT@depth")

    assert result is True
    assert ks.is_active is True
    assert ks.status()["category"] == TriggerCategory.RECONNECT_STORM.value


def test_check_reconnect_storm_does_not_trigger_under_threshold():
    ks = KillSwitch()
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=3)

    result = triggers.check_reconnect_storm(ks, monitor, "BTCUSDT@depth")

    assert result is False
    assert ks.is_active is False


def test_check_extreme_volatility_triggers_on_large_move():
    ks = KillSwitch()
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)

    monitor.observe("ADAUSDT", 0.20)
    result = triggers.check_extreme_volatility(ks, monitor, "ADAUSDT", 0.21)

    assert result is True
    assert ks.is_active is True
    assert ks.status()["category"] == TriggerCategory.EXTREME_VOLATILITY.value


def test_check_extreme_volatility_does_not_trigger_on_small_move():
    ks = KillSwitch()
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)

    monitor.observe("ADAUSDT", 0.20)
    result = triggers.check_extreme_volatility(ks, monitor, "ADAUSDT", 0.201)

    assert result is False
    assert ks.is_active is False


def test_first_trigger_reason_is_preserved_not_overwritten():
    """
    KillSwitch.trigger() is idempotent - a second trigger while already
    active must NOT overwrite the original reason/category, since you
    want to know what FIRST tripped it (per kill_switch.py's own
    docstring). Confirms our wiring doesn't fight that behavior.
    """
    ks = KillSwitch()
    triggers.check_order_book_gap(ks, gap_detected=True, stream_key="BTCUSDT@depth")

    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=0)
    triggers.check_reconnect_storm(ks, monitor, "ETHUSDT@depth")

    # Still shows the FIRST trigger (order book gap), not the second
    assert ks.status()["category"] == TriggerCategory.ORDER_BOOK_GAP.value
    assert "BTCUSDT@depth" in ks.status()["reason"]


def test_reset_requires_confirmed_by():
    """Sanity check that the real KillSwitch's fail-safe reset behavior works as documented."""
    import pytest

    ks = KillSwitch()
    ks.trigger(category=TriggerCategory.ORDER_BOOK_GAP, reason="test")

    with pytest.raises(ValueError):
        ks.reset(confirmed_by="")

    ks.reset(confirmed_by="hansika")
    assert ks.is_active is False