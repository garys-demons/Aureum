"""
tests/unit/test_fixtures.py

Confirms the replay fixture format (services/market_data/fixtures.py)
actually round-trips correctly: what gets recorded is exactly what
gets loaded back, in order, as real validated Pydantic models — and
that a corrupted fixture fails loudly rather than replaying silently
bad data.
"""
import pytest

from services.market_data.fixtures import FixtureRecorder, load_fixture
from services.market_data.models import (
    OrderBookDelta,
    OrderBookSnapshot,
    PriceLevel,
    SnapshotSource,
)

COMMON_SNAPSHOT = dict(
    event_type="depth_snapshot", exchange="binance", symbol="BTCUSDT",
    event_time=1_700_000_000_000, received_time=1_700_000_000_010,
)
COMMON_DELTA = dict(event_type="depth_update", exchange="binance", symbol="BTCUSDT")


def make_snapshot(last_update_id: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        **COMMON_SNAPSHOT, last_update_id=last_update_id,
        snapshot_time=1_700_000_000_000, source=SnapshotSource.REST_FULL,
        bids=[PriceLevel(price=100.0, quantity=1.0)],
        asks=[PriceLevel(price=101.0, quantity=1.0)],
    )


def make_delta(first_id: int, final_id: int) -> OrderBookDelta:
    return OrderBookDelta(
        **COMMON_DELTA, event_time=1_700_000_001_000, received_time=1_700_000_001_010,
        first_update_id=first_id, final_update_id=final_id,
        bids=[PriceLevel(price=100.0, quantity=2.0)], asks=[],
    )


def test_round_trip_preserves_order_and_content(tmp_path):
    path = tmp_path / "test.jsonl"
    snapshot = make_snapshot(1000)
    delta = make_delta(1001, 1001)

    with FixtureRecorder(path) as recorder:
        recorder.record(snapshot)
        recorder.record(delta)

    events = list(load_fixture(path))

    assert len(events) == 2
    assert isinstance(events[0], OrderBookSnapshot)
    assert events[0].last_update_id == 1000
    assert isinstance(events[1], OrderBookDelta)
    assert events[1].first_update_id == 1001


def test_recorder_reports_correct_count(tmp_path):
    path = tmp_path / "test.jsonl"
    with FixtureRecorder(path) as recorder:
        recorder.record(make_snapshot(1000))
        recorder.record(make_delta(1001, 1001))
        recorder.record(make_delta(1002, 1002))
    assert recorder.count == 3


def test_multiple_snapshots_mid_file_are_preserved_in_order(tmp_path):
    """A second snapshot appearing mid-fixture represents a real
    reconnect triggering fresh reconciliation — the loader must not
    collapse or reorder these, since replay depends on exact sequence."""
    path = tmp_path / "test.jsonl"
    with FixtureRecorder(path) as recorder:
        recorder.record(make_snapshot(1000))
        recorder.record(make_delta(1001, 1001))
        recorder.record(make_snapshot(2000))  # reconnect
        recorder.record(make_delta(2001, 2001))

    events = list(load_fixture(path))
    types = [type(e).__name__ for e in events]
    assert types == ["OrderBookSnapshot", "OrderBookDelta", "OrderBookSnapshot", "OrderBookDelta"]
    assert events[0].last_update_id == 1000
    assert events[2].last_update_id == 2000


def test_recorder_rejects_wrong_event_type(tmp_path):
    path = tmp_path / "test.jsonl"
    with FixtureRecorder(path) as recorder:
        with pytest.raises(TypeError):
            recorder.record("not a real event")


def test_loader_raises_on_malformed_json(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"type": "snapshot", "data": {broken json\n')

    with pytest.raises(ValueError, match="invalid JSON"):
        list(load_fixture(path))


def test_loader_raises_on_unrecognized_type(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"type": "something_else", "data": {}}\n')

    with pytest.raises(ValueError, match="unrecognized fixture type"):
        list(load_fixture(path))


def test_loader_raises_if_data_fails_model_validation(tmp_path):
    """A fixture claiming to be a snapshot but missing required fields
    should fail validation at load time, not silently replay garbage."""
    path = tmp_path / "bad.jsonl"
    path.write_text('{"type": "snapshot", "data": {"symbol": "BTCUSDT"}}\n')

    with pytest.raises(Exception):  # pydantic.ValidationError
        list(load_fixture(path))


def test_loader_skips_blank_lines(tmp_path):
    path = tmp_path / "test.jsonl"
    with FixtureRecorder(path) as recorder:
        recorder.record(make_snapshot(1000))
    with open(path, "a") as f:
        f.write("\n\n")  # trailing blank lines shouldn't break loading

    events = list(load_fixture(path))
    assert len(events) == 1