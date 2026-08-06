import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.persistence import repository
from core.persistence.anomaly import (
    ReconnectFrequencyMonitor,
    SequenceGapMonitor,
    observe_reconnect,
    observe_sequence,
)
from core.persistence.models import AuditCategory, Base


def test_sequence_gap_monitor_detects_gap():
    monitor = SequenceGapMonitor()
    assert monitor.observe("BTCUSDT", 1) is False  # first message, no baseline yet
    assert monitor.observe("BTCUSDT", 2) is False  # in order
    assert monitor.observe("BTCUSDT", 4) is True  # gap: skipped 3


def test_sequence_gap_monitor_tracks_streams_independently():
    monitor = SequenceGapMonitor()
    monitor.observe("BTCUSDT", 1)
    monitor.observe("ETHUSDT", 1)
    # BTCUSDT continues in order; ETHUSDT has a gap. They shouldn't interfere.
    assert monitor.observe("BTCUSDT", 2) is False
    assert monitor.observe("ETHUSDT", 5) is True


def test_reconnect_monitor_under_threshold_is_fine():
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=3)
    for _ in range(3):
        result = monitor.record_reconnect("BTCUSDT@depth")
    assert result is False


def test_reconnect_monitor_flags_when_exceeded():
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=2)
    monitor.record_reconnect("BTCUSDT@depth")
    monitor.record_reconnect("BTCUSDT@depth")
    result = monitor.record_reconnect("BTCUSDT@depth")  # 3rd, over threshold of 2
    assert result is True


# ---------------------------------------------------------------------
# Persistence wrapper tests — same in-memory SQLite pattern as test_persistence.py
# ---------------------------------------------------------------------
@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


async def test_observe_sequence_files_anomaly_on_gap(session):
    monitor = SequenceGapMonitor()
    await observe_sequence(monitor, session, "BTCUSDT", 1)  # baseline, no gap
    detected = await observe_sequence(monitor, session, "BTCUSDT", 3)  # gap: skipped 2

    assert detected is True
    anomalies = await repository.get_recent(session, category=AuditCategory.ANOMALY)
    assert len(anomalies) == 1
    assert anomalies[0].event_type == "sequence_gap"
    assert anomalies[0].payload["stream_key"] == "BTCUSDT"


async def test_observe_sequence_does_not_file_when_no_gap(session):
    monitor = SequenceGapMonitor()
    await observe_sequence(monitor, session, "BTCUSDT", 1)
    await observe_sequence(monitor, session, "BTCUSDT", 2)  # in order, no gap

    anomalies = await repository.get_recent(session, category=AuditCategory.ANOMALY)
    assert len(anomalies) == 0


async def test_observe_reconnect_files_anomaly_when_exceeded(session):
    monitor = ReconnectFrequencyMonitor(window_seconds=60, max_reconnects=1)
    await observe_reconnect(monitor, session, "BTCUSDT@depth")
    detected = await observe_reconnect(monitor, session, "BTCUSDT@depth")  # 2nd, over threshold of 1

    assert detected is True
    anomalies = await repository.get_recent(session, category=AuditCategory.ANOMALY)
    assert len(anomalies) == 1
    assert anomalies[0].event_type == "reconnect_frequency_exceeded"