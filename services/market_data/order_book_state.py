"""
OrderBook — maintains live, in-memory order book state and applies
incoming deltas (Phase 2, replay harness + live use).

Deliberately separate from order_book.py (which handles the reconciliation
PROCEDURE — fetching snapshots, buffering, finding the right starting
point). This class handles APPLYING deltas once reconciliation has decided
they're safe to apply.
"""
from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel


class OrderBook:
    """
    In-memory representation of a live order book for one symbol.

    Bids and asks are stored as dicts keyed by price for O(1) updates.
    A quantity of 0 in a delta means "remove this price level."
    """

    def __init__(self, snapshot: OrderBookSnapshot):
        self.symbol = snapshot.symbol
        self.last_update_id = snapshot.last_update_id
        self._bids: dict[float, float] = {level.price: level.quantity for level in snapshot.bids}
        self._asks: dict[float, float] = {level.price: level.quantity for level in snapshot.asks}

    def apply_delta(self, delta: OrderBookDelta) -> None:
        """
        Apply a single delta's bid/ask updates to the current state.

        Caller is responsible for having already verified contiguity
        (delta.first_update_id == self.last_update_id + 1) — this method
        trusts that check has been done and just applies the update.
        """
        self._apply_levels(self._bids, delta.bids)
        self._apply_levels(self._asks, delta.asks)
        self.last_update_id = delta.final_update_id

    @staticmethod
    def _apply_levels(book_side: dict[float, float], levels: list[PriceLevel]) -> None:
        """Add/update a price level, or remove it if quantity is 0."""
        for level in levels:
            if level.quantity == 0:
                book_side.pop(level.price, None)
            else:
                book_side[level.price] = level.quantity

    @property
    def best_bid(self) -> float | None:
        """Highest price someone is willing to buy at, or None if book is empty."""
        return max(self._bids.keys()) if self._bids else None

    @property
    def best_ask(self) -> float | None:
        """Lowest price someone is willing to sell at, or None if book is empty."""
        return min(self._asks.keys()) if self._asks else None

    def snapshot_state(self) -> dict:
        """Return a plain-dict snapshot of current state, useful for test assertions."""
        return {
            "symbol": self.symbol,
            "last_update_id": self.last_update_id,
            "bids": dict(self._bids),
            "asks": dict(self._asks),
        }