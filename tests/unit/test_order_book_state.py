"""Unit tests for OrderBook state tracking and delta application (Phase 2)."""
from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel, SnapshotSource
from services.market_data.order_book_state import OrderBook


def make_snapshot() -> OrderBookSnapshot:
    return OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol="BTCUSDT",
        event_time=1,
        received_time=1,
        last_update_id=100,
        bids=[
            PriceLevel(price=50000, quantity=1.0),
            PriceLevel(price=49999, quantity=2.0),
        ],
        asks=[
            PriceLevel(price=50001, quantity=1.5),
            PriceLevel(price=50002, quantity=0.5),
        ],
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


def test_order_book_initializes_from_snapshot():
    book = OrderBook(make_snapshot())

    assert book.symbol == "BTCUSDT"
    assert book.last_update_id == 100
    assert book.best_bid == 50000
    assert book.best_ask == 50001


def test_apply_delta_updates_existing_price_level():
    """A delta with a new quantity at an existing price should update it, not add a duplicate."""
    book = OrderBook(make_snapshot())
    delta = make_delta(101, 101, bids=[PriceLevel(price=50000, quantity=3.5)])

    book.apply_delta(delta)

    assert book.snapshot_state()["bids"][50000] == 3.5
    assert book.last_update_id == 101


def test_apply_delta_adds_new_price_level():
    book = OrderBook(make_snapshot())
    delta = make_delta(101, 101, bids=[PriceLevel(price=49998, quantity=0.75)])

    book.apply_delta(delta)

    assert book.snapshot_state()["bids"][49998] == 0.75


def test_apply_delta_zero_quantity_removes_price_level():
    """quantity=0 means 'this price level is gone' — must be removed, not stored as 0."""
    book = OrderBook(make_snapshot())
    delta = make_delta(101, 101, asks=[PriceLevel(price=50002, quantity=0)])

    book.apply_delta(delta)

    assert 50002 not in book.snapshot_state()["asks"]


def test_best_bid_and_ask_update_after_delta():
    book = OrderBook(make_snapshot())
    delta = make_delta(101, 101, bids=[PriceLevel(price=50000.5, quantity=1.0)])

    book.apply_delta(delta)

    assert book.best_bid == 50000.5  # new higher bid


def test_multiple_deltas_apply_in_sequence_correctly():
    """Simulates a short realistic run: several deltas applied one after another."""
    book = OrderBook(make_snapshot())

    book.apply_delta(make_delta(101, 101, bids=[PriceLevel(price=50000, quantity=2.0)]))
    book.apply_delta(make_delta(102, 102, asks=[PriceLevel(price=50001, quantity=0)]))
    book.apply_delta(make_delta(103, 105, bids=[PriceLevel(price=49997, quantity=0.5)]))

    state = book.snapshot_state()
    assert state["bids"][50000] == 2.0
    assert 50001 not in state["asks"]
    assert state["bids"][49997] == 0.5
    assert book.last_update_id == 105