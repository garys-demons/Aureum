"""
Tests for the OrderBook state class (services/market_data/order_book.py).

Separate from test_order_book.py, which covers reconcile(). This file
covers the book itself: applying deltas, sequence enforcement, and
Binance's quantity-0-means-delete semantics.
"""
import pytest

from services.market_data.models import (
    OrderBookDelta,
    OrderBookSnapshot,
    PriceLevel,
    SnapshotSource,
)
from services.market_data.order_book import OrderBook


def make_snapshot(last_update_id=100, symbol="BTCUSDT"):
    return OrderBookSnapshot(
        event_type="depth_snapshot",
        exchange="binance",
        symbol=symbol,
        event_time=1_700_000_000_000,
        received_time=1_700_000_000_000,
        last_update_id=last_update_id,
        bids=[PriceLevel(price=100.0, quantity=1.0), PriceLevel(price=99.0, quantity=2.0)],
        asks=[PriceLevel(price=101.0, quantity=1.5), PriceLevel(price=102.0, quantity=3.0)],
        snapshot_time=1_700_000_000_000,
        source=SnapshotSource.REST_FULL,
    )


def make_delta(first, final, bids=None, asks=None, symbol="BTCUSDT"):
    return OrderBookDelta(
        event_type="depth_update",
        exchange="binance",
        symbol=symbol,
        event_time=1_700_000_000_000,
        received_time=1_700_000_000_000,
        first_update_id=first,
        final_update_id=final,
        bids=bids or [],
        asks=asks or [],
    )


def test_from_snapshot_populates_both_sides():
    book = OrderBook.from_snapshot(make_snapshot())
    assert book.bids == {100.0: 1.0, 99.0: 2.0}
    assert book.asks == {101.0: 1.5, 102.0: 3.0}
    assert book.last_update_id == 100
    assert book.is_live is False


def test_cannot_apply_delta_before_snapshot():
    book = OrderBook("BTCUSDT")
    with pytest.raises(ValueError, match="before a snapshot"):
        book.apply(make_delta(101, 105))


def test_bridging_delta_is_accepted_before_live():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    # Straddles 101 — exactly what reconcile() selects.
    book.apply(make_delta(98, 103, bids=[PriceLevel(price=100.0, quantity=5.0)]))
    assert book.bids[100.0] == 5.0
    assert book.last_update_id == 103


def test_non_bridging_first_delta_is_rejected():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    with pytest.raises(ValueError, match="does not bridge"):
        book.apply(make_delta(105, 110))


def test_contiguous_deltas_apply_once_live():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    book.apply(make_delta(98, 103))
    book.mark_live()
    book.apply(make_delta(104, 107, asks=[PriceLevel(price=101.0, quantity=9.0)]))
    assert book.asks[101.0] == 9.0
    assert book.last_update_id == 107


def test_sequence_gap_raises_once_live():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    book.apply(make_delta(98, 103))
    book.mark_live()
    with pytest.raises(ValueError, match="Sequence gap"):
        book.apply(make_delta(110, 115))  # skipped 104-109


def test_zero_quantity_removes_level():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    book.apply(make_delta(98, 103, bids=[PriceLevel(price=99.0, quantity=0.0)]))
    assert 99.0 not in book.bids
    assert 100.0 in book.bids


def test_zero_quantity_on_missing_level_is_harmless():
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    book.apply(make_delta(98, 103, bids=[PriceLevel(price=55.0, quantity=0.0)]))
    assert 55.0 not in book.bids


def test_snapshot_drops_zero_quantity_levels():
    snap = make_snapshot()
    snap.bids.append(PriceLevel(price=98.0, quantity=0.0))
    book = OrderBook.from_snapshot(snap)
    assert 98.0 not in book.bids


def test_best_bid_ask_and_spread():
    book = OrderBook.from_snapshot(make_snapshot())
    assert book.best_bid() == (100.0, 1.0)
    assert book.best_ask() == (101.0, 1.5)
    assert book.spread() == pytest.approx(1.0)
    assert book.depth() == (2, 2)


def test_best_bid_ask_on_empty_book():
    book = OrderBook("BTCUSDT")
    assert book.best_bid() is None
    assert book.best_ask() is None
    assert book.spread() is None

def test_gap_within_reconciled_batch_is_rejected():
    """
    Regression: apply() used to check is_live, which isn't set until the
    whole reconciled batch is applied — so deltas 2..n were checked with
    the bridging rule instead of the contiguity rule, and a gap inside
    the batch could slip through.
    """
    book = OrderBook.from_snapshot(make_snapshot(last_update_id=100))
    book.apply(make_delta(98, 103))          # bridging delta, fine
    with pytest.raises(ValueError, match="Sequence gap"):
        book.apply(make_delta(110, 115))     # gap: 104-109 missing