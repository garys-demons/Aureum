"""
core/persistence/lag.py

Addresses docs/risk_register.md (2026-08-11): "Occasional negative lag
on depth_update rows — residual clock offset."

WHAT'S ACTUALLY HAPPENING
---------------------------
"Lag" = recorded_at - occurred_at (how long after the real-world event
did we finish saving it). occurred_at comes from the exchange's own
timestamp; recorded_at comes from our server's clock. If the two
clocks aren't perfectly synced, lag can occasionally come out negative
— i.e. we appear to have recorded something before it happened. This
isn't a bug in the pipeline logic; it's a measurement artifact of two
independent clocks never being in perfect agreement.

WHAT THIS FILE DOES
---------------------
Deliberately does NOT hide or clamp negative values — occurred_at and
recorded_at are the real, honest timestamps, and silently flooring the
computed lag would hide genuine clock-skew information from anyone
debugging a real delay issue later. Instead, this makes the skew
visible: compute_lag_seconds() returns the true (possibly negative)
value, and log_if_clock_skew() logs a low-severity note when it sees
one, so the pattern is visible in logs without polluting the stored
data itself.
"""
from datetime import datetime

import structlog

log = structlog.get_logger("persistence.lag")


def compute_lag_seconds(occurred_at: datetime, recorded_at: datetime) -> float:
    """
    Returns recorded_at - occurred_at, in seconds. Can legitimately be
    negative due to clock skew between the exchange's timestamp and our
    server's clock — this is expected and NOT corrected here (see module
    docstring for why).
    """
    return (recorded_at - occurred_at).total_seconds()


def log_if_clock_skew(occurred_at: datetime, recorded_at: datetime, *, context: str = "") -> float:
    """
    Computes lag and logs a low-severity note if it's negative (a clock
    skew signal), so this pattern is visible over time in logs without
    needing to hunt through raw rows to notice it. Returns the computed
    lag either way.
    """
    lag = compute_lag_seconds(occurred_at, recorded_at)
    if lag < 0:
        log.info(
            "negative_lag_clock_skew",
            lag_seconds=lag,
            context=context,
            note="recorded_at earlier than occurred_at - likely clock "
                 "skew between exchange and server clocks, not a real bug",
        )
    return lag