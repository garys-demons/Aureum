"""Unit tests for the replay harness (Phase 2)."""
import pytest

from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel, SnapshotSource
from services.market_data.replay import replay_sequence
from services.market_data.order_book import reconcile
from services.market_data.order_book_state import OrderBook


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
def test_replay_across_reconnect_boundary_reconciles_correctly():
    """
    Simulates a real reconnect mid-stream: book runs normally, disconnects,
    a FRESH snapshot is fetched (not just resumed), and reconciliation
    picks the correct starting delta before continuing. Final state must
    be correct despite the mid-sequence restart (TRD §6.1/§6.2).
    """
    # --- Phase A: normal operation before disconnect ---
    snapshot_1 = make_snapshot(last_update_id=100)
    book = replay_sequence(
        snapshot_1,
        [
            make_delta(101, 101, bids=[PriceLevel(price=50000, quantity=2.0)]),
            make_delta(102, 105, asks=[PriceLevel(price=50001, quantity=0)]),
        ],
    )
    assert book.last_update_id == 105  # state right before the disconnect

    # --- Disconnect happens here ---
    # On reconnect, a FRESH snapshot is fetched (its last_update_id has
    # moved on, since real time passed during the disconnect+backoff).
    snapshot_2 = make_snapshot(last_update_id=112)

    # Deltas buffered live while that fresh snapshot was being fetched —
    # includes some now-stale ones (<=112) and the genuinely new ones.
    buffered_during_reconnect = [
        make_delta(106, 112, bids=[PriceLevel(price=50000, quantity=999)]),  # stale, discarded
        make_delta(113, 113, bids=[PriceLevel(price=50000, quantity=5.0)]),  # correct bridge
        make_delta(114, 115, asks=[PriceLevel(price=50004, quantity=1.2)]),
    ]

    # --- Reconciliation re-runs exactly as it does live ---
    ordered_deltas = reconcile(snapshot_2, buffered_during_reconnect)

    # Reconciliation rebuilds the book from the NEW snapshot, not the old one.
    book_after_reconnect = OrderBook(snapshot_2)
    for delta in ordered_deltas:
        book_after_reconnect.apply_delta(delta)

    state = book_after_reconnect.snapshot_state()

    # Hand-calculated expected end state: the stale delta (106-112) never
    # applied — only the post-snapshot deltas (113, 114-115) did.
    assert state["bids"][50000] == 5.0
    assert state["asks"][50004] == 1.2
    assert book_after_reconnect.last_update_id == 115