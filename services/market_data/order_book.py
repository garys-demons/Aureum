"""
Order book reconciliation logic — the highest-risk part of the market data
module. See TRD §6.1 for the full spec this implements.
"""
from typing import Any

import httpx
import structlog

from services.market_data.models import OrderBookSnapshot, OrderBookDelta, PriceLevel
from services.market_data.parsers import parse_order_book_snapshot, parse_order_book_delta

logger = structlog.get_logger()

BINANCE_TESTNET_REST_BASE = "https://testnet.binance.vision"


async def fetch_snapshot(symbol: str, limit: int = 1000) -> OrderBookSnapshot:
    """Fetch a fresh full order book snapshot via REST (TRD §6.1 step 2)."""
    url = f"{BINANCE_TESTNET_REST_BASE}/api/v3/depth"
    params = {"symbol": symbol, "limit": limit}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        raw = response.json()

    logger.info("fetched_order_book_snapshot", symbol=symbol, last_update_id=raw["lastUpdateId"])
    return parse_order_book_snapshot(raw, symbol=symbol)


def reconcile(snapshot: OrderBookSnapshot, buffered_deltas: list[OrderBookDelta]) -> list[OrderBookDelta]:
    """
    Given a snapshot and a buffer of deltas received during the fetch,
    return the correctly-ordered list of deltas that should be applied
    starting from the snapshot (TRD §6.1 steps 4-6).

    Raises ValueError if no valid starting delta is found — caller should
    re-fetch the snapshot and try again (step 5's "re-fetch" instruction).
    """
    # Step 4: discard deltas already reflected in the snapshot
    usable = [d for d in buffered_deltas if d.final_update_id > snapshot.last_update_id]

    if not usable:
        raise ValueError("No usable deltas after filtering — buffer window was too short, re-fetch snapshot")

    # Step 5: find the first delta that correctly picks up from the snapshot
    first_valid_index = None
    for i, delta in enumerate(usable):
        if delta.first_update_id <= snapshot.last_update_id + 1 <= delta.final_update_id:
            first_valid_index = i
            break

    if first_valid_index is None:
        raise ValueError("No delta found that bridges the snapshot's last_update_id — re-fetch snapshot")

    ordered = usable[first_valid_index:]

    # Step 6: verify contiguity across all remaining deltas — any gap = failure
    for prev, curr in zip(ordered, ordered[1:]):
        if curr.first_update_id != prev.final_update_id + 1:
            raise ValueError(
                f"Gap detected between update_id {prev.final_update_id} and {curr.first_update_id} — re-fetch snapshot"
            )

    logger.info("reconciliation_successful", num_deltas_applied=len(ordered))
    return ordered

class OrderBook:
    """
    Maintains local bid/ask state for one symbol.

    Built from a REST snapshot, then updated by applying deltas in
    contiguous order. Any gap raises — the caller must re-snapshot and
    re-reconcile rather than continuing with a book that has silently
    missed updates (TRD §6.1 step 6).

    Binance semantics: a price level with quantity 0 means "remove this
    level", not "there is zero quantity here".
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self.last_update_id: int | None = None
        self.is_live: bool = False

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookSnapshot) -> "OrderBook":
        book = cls(snapshot.symbol)
        book.bids = {lvl.price: lvl.quantity for lvl in snapshot.bids if lvl.quantity > 0}
        book.asks = {lvl.price: lvl.quantity for lvl in snapshot.asks if lvl.quantity > 0}
        book.last_update_id = snapshot.last_update_id
        return book

    def apply(self, delta: OrderBookDelta) -> None:
        """
        Apply one delta. Raises ValueError on a sequence gap.

        The first delta after a snapshot is allowed to straddle
        last_update_id (that's what reconcile() selected it for);
        every delta after that must be exactly contiguous.
        """
        if self.last_update_id is None:
            raise ValueError("Cannot apply a delta before a snapshot has been loaded")

        if self.is_live:
            if delta.first_update_id != self.last_update_id + 1:
                raise ValueError(
                    f"Sequence gap on {self.symbol}: expected first_update_id="
                    f"{self.last_update_id + 1}, got {delta.first_update_id}"
                )
        else:
            # Bridging delta from reconcile() — must span last_update_id + 1.
            if not (delta.first_update_id <= self.last_update_id + 1 <= delta.final_update_id):
                raise ValueError(
                    f"First delta does not bridge snapshot on {self.symbol}: "
                    f"snapshot last_update_id={self.last_update_id}, "
                    f"delta covers {delta.first_update_id}-{delta.final_update_id}"
                )

        self._apply_levels(self.bids, delta.bids)
        self._apply_levels(self.asks, delta.asks)
        self.last_update_id = delta.final_update_id

    @staticmethod
    def _apply_levels(side: dict[float, float], updates: list[PriceLevel]) -> None:
        for lvl in updates:
            if lvl.quantity == 0:
                side.pop(lvl.price, None)
            else:
                side[lvl.price] = lvl.quantity

    def mark_live(self) -> None:
        """Called once reconciliation has completed successfully."""
        self.is_live = True
        logger.info("order_book_live", symbol=self.symbol, last_update_id=self.last_update_id)

    def best_bid(self) -> tuple[float, float] | None:
        if not self.bids:
            return None
        price = max(self.bids)
        return price, self.bids[price]

    def best_ask(self) -> tuple[float, float] | None:
        if not self.asks:
            return None
        price = min(self.asks)
        return price, self.asks[price]

    def spread(self) -> float | None:
        bid, ask = self.best_bid(), self.best_ask()
        if bid is None or ask is None:
            return None
        return ask[0] - bid[0]

    def depth(self) -> tuple[int, int]:
        return len(self.bids), len(self.asks)