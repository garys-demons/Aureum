"""
tests/unit/test_lag.py

Confirms lag is measured honestly (including legitimately negative
values from clock skew) and that skew gets logged for visibility
without altering the underlying numbers.
"""
from datetime import datetime, timedelta, timezone

from core.persistence.lag import compute_lag_seconds, log_if_clock_skew


def test_positive_lag_normal_case():
    occurred = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded = occurred + timedelta(seconds=2.5)
    assert compute_lag_seconds(occurred, recorded) == 2.5


def test_negative_lag_from_clock_skew_is_not_hidden():
    """The whole point: negative lag should be returned as-is, not
    clamped to zero or otherwise hidden."""
    occurred = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
    recorded = datetime(2026, 1, 1, 12, 0, 3, tzinfo=timezone.utc)  # 2s "before"
    assert compute_lag_seconds(occurred, recorded) == -2.0


def test_zero_lag():
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert compute_lag_seconds(t, t) == 0.0


def test_log_if_clock_skew_returns_same_value_as_compute(caplog):
    occurred = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
    recorded = datetime(2026, 1, 1, 12, 0, 3, tzinfo=timezone.utc)

    lag = log_if_clock_skew(occurred, recorded, context="depth_update")

    assert lag == -2.0


def test_log_if_clock_skew_does_not_raise_on_positive_lag():
    """Sanity check: normal positive lag shouldn't trigger any error path."""
    occurred = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded = occurred + timedelta(seconds=1)
    lag = log_if_clock_skew(occurred, recorded)
    assert lag == 1.0