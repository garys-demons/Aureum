"""Unit tests for ExtremeVolatilityMonitor (Phase 6)."""
from datetime import datetime, timedelta, timezone

from core.persistence.volatility_anomaly import ExtremeVolatilityMonitor


def test_no_flag_with_single_observation():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    assert monitor.observe("ADAUSDT", 0.20) is False


def test_no_flag_when_move_under_threshold():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    now = datetime.now(timezone.utc)
    monitor.observe("ADAUSDT", 0.20, timestamp=now)
    result = monitor.observe("ADAUSDT", 0.202, timestamp=now + timedelta(seconds=10))
    assert result is False


def test_flags_when_move_exceeds_threshold():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    now = datetime.now(timezone.utc)
    monitor.observe("ADAUSDT", 0.20, timestamp=now)
    result = monitor.observe("ADAUSDT", 0.206, timestamp=now + timedelta(seconds=10))
    assert result is True


def test_old_observations_fall_out_of_window():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    now = datetime.now(timezone.utc)
    monitor.observe("ADAUSDT", 0.20, timestamp=now)
    result = monitor.observe("ADAUSDT", 0.206, timestamp=now + timedelta(seconds=90))
    assert result is False


def test_tracks_symbols_independently():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    now = datetime.now(timezone.utc)
    monitor.observe("ADAUSDT", 0.20, timestamp=now)
    monitor.observe("BTCUSDT", 65000, timestamp=now)

    ada_result = monitor.observe("ADAUSDT", 0.21, timestamp=now + timedelta(seconds=5))
    btc_result = monitor.observe("BTCUSDT", 65010, timestamp=now + timedelta(seconds=5))

    assert ada_result is True
    assert btc_result is False


def test_downward_move_also_flagged():
    monitor = ExtremeVolatilityMonitor(window_seconds=60, max_pct_move=0.02)
    now = datetime.now(timezone.utc)
    monitor.observe("ADAUSDT", 0.20, timestamp=now)
    result = monitor.observe("ADAUSDT", 0.194, timestamp=now + timedelta(seconds=10))
    assert result is True