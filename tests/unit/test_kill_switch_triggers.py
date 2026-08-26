"""
Tests for kill_switch_triggers.py (Phase 6). Uses a fake KillSwitch
double instead of Samarth's real one, so this wiring can be built and
tested before his module lands. Once real, these tests should be
re-run against the actual KillSwitch/TriggerCategory as a sanity check
that the fake's behavior genuinely matches.
"""
import pytest

from core.persistence.anomaly import ReconnectFrequencyMonitor
from core.persistence.volatility_anomaly import ExtremeVolatilityMonitor
from core.persistence import kill_switch_triggers as triggers


class FakeTriggerCategory:
    ORDER_BOOK_GAP = "ORDER_BOOK_GAP"
    RECONNECT_STORM = "RECONNECT_STORM"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"


class FakeKillSwitch:
    """Records every .trigger() call instead of actually doing anything."""

    def __init__(self):
        self.calls = []
        self.is_active = False

    def trigger(self, category, reason):
        self.calls.append((category, reason))
        self.is_active = True


@pytest.fixture(autouse=True)
def patch_trigger_category(monkeypatch):
    monkeypatch.setattr(triggers, "TriggerCategory", FakeTriggerCategory)


def test_check_order_book_gap_triggers_on_gap():
    ks = FakeKillSwitch()
    triggers.check_order_book_gap(ks, gap_detected=True, stream_key="BTCUSDT@depth")

    assert ks.is_active is True
    assert len(ks.calls) == 1
    assert ks.calls[0][0] == FakeTriggerCategory.ORDER_BOOK_GAP


def test_check_order_book_gap_does_not_trigger_when_no_gap():
    ks = FakeKillSwitch()
    triggers.check_order_book_gap(ks, gap_detected=False, stream_key="BTCUSDT@depth")

    assert ks.is_active is False
    assert len(ks.calls) == 0


def test_check_reconnect_storm_triggers_when_exceeded():
    ks = FakeKillSwitch()
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=1)

    monitor.record_reconnect("BTCUSDT@depth")  # 1st, under threshold
    result = triggers.check_reconnect_storm(ks, monitor, "BTCUSDT@depth")  # 2nd, over threshold

    assert result is True
    assert ks.is_active is True
    assert ks.calls[0][0] == FakeTriggerCategory.RECONNECT_STORM


def test_check_reconnect_storm_does_not_trigger_under_threshold():
    ks = FakeKillSwitch()
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=3)

    result = triggers.check_reconnect_storm(ks, monitor, "BTCUSDT@depth")

    assert result is False
    assert ks.is_active is False


def test_check_extreme_volatility_triggers_on_large_move():
    ks = FakeKillSwitch()
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)

    monitor.observe("ADAUSDT", 0.20)
    result = triggers.check_extreme_volatility(ks, monitor, "ADAUSDT", 0.21)  # 5% move

    assert result is True
    assert ks.is_active is True
    assert ks.calls[0][0] == FakeTriggerCategory.EXTREME_VOLATILITY


def test_check_extreme_volatility_does_not_trigger_on_small_move():
    ks = FakeKillSwitch()
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)

    monitor.observe("ADAUSDT", 0.20)
    result = triggers.check_extreme_volatility(ks, monitor, "ADAUSDT", 0.201)  # 0.5% move

    assert result is False
    assert ks.is_active is False