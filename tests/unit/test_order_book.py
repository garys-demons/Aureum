"""Unit tests for order book reconciliation logic (TRD §6.1)."""
import pytest

from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel, SnapshotSource
from services.market_data.order_book import reconcile


def make_snapshot(last_update_id: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1,
        received_time=1,
        last_update_id=last_update_id,
        bids=[PriceLevel(price=100, quantity=1)],
        asks=[PriceLevel(price=101, quantity=1)],
        snapshot_time=1,
        source=SnapshotSource.REST_FULL,
    )


def make_delta(first_id: int, final_id: int) -> OrderBookDelta:
    return OrderBookDelta(
        event_type="depth_update",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1,
        received_time=1,
        first_update_id=first_id,
        final_update_id=final_id,
        bids=[PriceLevel(price=100, quantity=1)],
        asks=[PriceLevel(price=101, quantity=1)],
    )


def test_reconcile_happy_path():
    """A clean, contiguous set of deltas should reconcile successfully."""
    snapshot = make_snapshot(last_update_id=100)
    deltas = [
        make_delta(95, 100),    # too old — should be discarded
        make_delta(101, 105),   # correct starting point
        make_delta(106, 110),   # continues cleanly
    ]

    result = reconcile(snapshot, deltas)

    assert len(result) == 2
    assert result[0].first_update_id == 101
    assert result[1].final_update_id == 110


def test_reconcile_raises_on_gap():
    """A gap between deltas must raise an error, not silently continue."""
    snapshot = make_snapshot(last_update_id=100)
    deltas = [
        make_delta(101, 105),
        make_delta(110, 115),  # gap! should start at 106, not 110
    ]

    with pytest.raises(ValueError, match="Gap detected"):
        reconcile(snapshot, deltas)


def test_reconcile_raises_when_no_bridging_delta():
    """If no delta bridges the snapshot's last_update_id, must raise."""
    snapshot = make_snapshot(last_update_id=100)
    deltas = [
        make_delta(200, 205),  # way past — nothing bridges 100→101
    ]

    with pytest.raises(ValueError, match="No delta found"):
        reconcile(snapshot, deltas)


def test_reconcile_raises_when_all_deltas_too_old():
    """If every delta is already reflected in the snapshot, must raise."""
    snapshot = make_snapshot(last_update_id=100)
    deltas = [
        make_delta(50, 90),
        make_delta(90, 100),
    ]

    with pytest.raises(ValueError, match="No usable deltas"):
        reconcile(snapshot, deltas)