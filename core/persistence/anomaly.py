"""
core/persistence/anomaly.py — general anomaly detection.

Scope, per the team working model doc: "general anomaly detection
(sequence-gap monitoring, connection drop frequency) — the
correctness-critical order-book gap logic itself stays with Hansika's
module." So these classes are deliberately generic/system-level, not a
reimplementation of order-book reconciliation.

Both monitors just log a warning via structlog when they see something
off. Wiring them up to also write an ANOMALY row via
core.persistence.repository.record_anomaly() is the natural next step,
once there's a live DB session to hand them (see the __main__ demo below
for the log-only version).
"""

from collections import deque
from datetime import datetime, timezone

import structlog

log = structlog.get_logger("anomaly")


class SequenceGapMonitor:
    """
    Tracks the last-seen sequence number per stream key (e.g. per symbol)
    and flags when a new sequence number doesn't follow the previous one.

    This is intentionally generic — it doesn't know anything about order
    books specifically. It's meant for any stream that carries a
    monotonic sequence number.
    """

    def __init__(self):
        self._last_seq: dict[str, int] = {}

    def observe(self, stream_key: str, sequence: int) -> bool:
        """
        Returns True if a gap was detected (and logs it). Call this once
        per incoming message with its sequence number.
        """
        last = self._last_seq.get(stream_key)
        self._last_seq[stream_key] = sequence

        if last is None:
            return False  # first message on this stream, nothing to compare

        expected = last + 1
        if sequence != expected:
            log.warning(
                "sequence_gap_detected",
                stream_key=stream_key,
                expected=expected,
                received=sequence,
                gap_size=sequence - expected,
            )
            return True
        return False


class ReconnectFrequencyMonitor:
    """
    Tracks reconnect timestamps in a sliding window and flags when
    reconnects happen more often than `max_reconnects` within
    `window_seconds` — frequent reconnects on a supposedly-stable
    exchange connection is itself a signal something's wrong, even if
    each individual reconnect "succeeds."
    """

    def __init__(self, window_seconds: int = 300, max_reconnects: int = 3):
        self.window_seconds = window_seconds
        self.max_reconnects = max_reconnects
        self._events: dict[str, deque] = {}

    def record_reconnect(self, stream_key: str) -> bool:
        """Returns True if reconnect frequency exceeded the threshold (and logs it)."""
        now = datetime.now(timezone.utc)
        window = self._events.setdefault(stream_key, deque())
        window.append(now)

        cutoff = now.timestamp() - self.window_seconds
        while window and window[0].timestamp() < cutoff:
            window.popleft()

        if len(window) > self.max_reconnects:
            log.warning(
                "reconnect_frequency_exceeded",
                stream_key=stream_key,
                reconnects_in_window=len(window),
                window_seconds=self.window_seconds,
                threshold=self.max_reconnects,
            )
            return True
        return False


# ---------------------------------------------------------------------
# Persistence wrappers — detect AND permanently record, in one call
# ---------------------------------------------------------------------
# The two classes above only log a warning. These functions wrap them:
# run the check, and if something was detected, also file it into the
# audit trail via repository.record_anomaly(), so it's not just a line
# that scrolled past in the terminal — it's something you can look up
# weeks later with repository.get_recent(category=AuditCategory.ANOMALY).
#
# Deliberately kept separate from the classes above rather than baked
# into observe()/record_reconnect() directly, so those stay simple,
# synchronous, and don't need a database session to be tested (see
# tests/unit/test_anomaly.py — those tests still don't touch a DB).

from sqlalchemy.ext.asyncio import AsyncSession

from core.persistence import repository


async def observe_sequence(
    monitor: SequenceGapMonitor,
    session: AsyncSession,
    stream_key: str,
    sequence: int,
) -> bool:
    """Check for a sequence gap; if found, log it AND file an ANOMALY record."""
    gap_detected = monitor.observe(stream_key, sequence)
    if gap_detected:
        await repository.record_anomaly(
            session,
            event_type="sequence_gap",
            payload={"stream_key": stream_key, "sequence": sequence},
        )
    return gap_detected


async def observe_reconnect(
    monitor: ReconnectFrequencyMonitor,
    session: AsyncSession,
    stream_key: str,
) -> bool:
    """Check reconnect frequency; if exceeded, log it AND file an ANOMALY record."""
    exceeded = monitor.record_reconnect(stream_key)
    if exceeded:
        await repository.record_anomaly(
            session,
            event_type="reconnect_frequency_exceeded",
            payload={"stream_key": stream_key},
        )
    return exceeded


if __name__ == "__main__":
    from core.logging_config import configure_logging

    configure_logging(json_logs=False)

    seq_monitor = SequenceGapMonitor()
    for s in [1, 2, 3, 5, 6]:  # gap at 4
        seq_monitor.observe("BTCUSDT@depth", s)

    reconnect_monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=2)
    for _ in range(4):
        reconnect_monitor.record_reconnect("BTCUSDT@depth")