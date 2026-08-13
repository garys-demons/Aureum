"""Unit tests for the replay harness (Phase 2)."""
import pytest

from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel, SnapshotSource
from services.market_data.replay import replay_sequence


def make_snapshot(last_update_id: int = 100) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1,
        received_time=1,
        last_update_id=last_update_id,
        bids=[PriceLevel(price=50000, quantity=1.0)],
        asks=[PriceLevel(price=50001, quantity=1.0)],
        snapshot_time=1,
        source=SnapshotSource.REST_FULL,
    )


def make_delta(first_id: int, final_id: int, bids=None, asks=None) -> OrderBookDelta:
    return OrderBookDelta(
        event_type="depth_update",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1,
        received_time=1,
        first_update_id=first_id,
        final_update_id=final_id,
        bids=bids or [],
        asks=asks or [],
    )


def test_replay_long_contiguous_run_stays_synchronized():
    """A long, clean, gap-free sequence should apply fully and match the
    hand-calculated expected end state (Phase 2 exit criterion: 'book
    stays synchronized under replay testing')."""
    snapshot = make_snapshot(last_update_id=100)

    deltas = [
        make_delta(101, 101, bids=[PriceLevel(price=50000, quantity=2.0)]),
        make_delta(102, 102, asks=[PriceLevel(price=50001, quantity=0)]),  # remove
        make_delta(103, 103, asks=[PriceLevel(price=50003, quantity=0.8)]),  # add
        make_delta(104, 106, bids=[PriceLevel(price=49998, quantity=0.3)]),  # multi-id delta
        make_delta(107, 107, bids=[PriceLevel(price=50000, quantity=1.75)]),  # update again
    ]

    book = replay_sequence(snapshot, deltas)
    state = book.snapshot_state()

    # Hand-calculated expected end state:
    assert state["bids"] == {50000: 1.75, 49998: 0.3}
    assert state["asks"] == {50003: 0.8}
    assert book.last_update_id == 107


def test_replay_raises_on_gap():
    """A sequence with a missing update_id must raise, not silently continue."""
    snapshot = make_snapshot(last_update_id=100)

    deltas = [
        make_delta(101, 101, bids=[PriceLevel(price=50000, quantity=2.0)]),
        make_delta(105, 105, bids=[PriceLevel(price=50000, quantity=3.0)]),  # gap: skipped 102-104
    ]

    with pytest.raises(ValueError, match="Gap detected"):
        replay_sequence(snapshot, deltas)


def test_replay_empty_delta_list_returns_snapshot_state_unchanged():
    """No deltas at all should just return the snapshot's initial state."""
    snapshot = make_snapshot(last_update_id=100)

    book = replay_sequence(snapshot, [])

    assert book.last_update_id == 100
    assert book.best_bid == 50000