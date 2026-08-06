"""
Order book reconciliation logic — the highest-risk part of the market data
module. See TRD §6.1 for the full spec this implements.
"""
from typing import Any

import httpx
import structlog

from services.market_data.models import OrderBookSnapshot, OrderBookDelta
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