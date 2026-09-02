"""
Paper exchange — simulates realistic order fills against historical
OrderBook state. No side effects, no network calls: given a book and an
order, returns what would honestly have happened.

Deliberately avoids "touch = fill" (master architecture's explicit
warning against unrealistic optimism): an order only fills against
liquidity that actually existed in the book at that moment, walked
level by level. Requesting more than the book can supply produces a
partial fill, not a magically complete one.
"""
from dataclasses import dataclass
from services.market_data.order_book import OrderBook

TAKER_FEE_RATE = 0.001  # 0.1% — placeholder, confirm real schedule with team
MAKER_FEE_RATE = 0.001  # 0.1% — confirmed against Binance's real spot maker fee schedule (Aryan, Phase 8)


@dataclass
class Fill:
    symbol: str
    side: str            # "buy" or "sell"
    quantity: float       # actually filled — may be less than requested
    price: float            # volume-weighted average fill price
    fee: float                # fee charged on this fill, in quote currency
    fully_filled: bool          # False if the book ran out before quantity was met


def match_market_order(book: OrderBook, side: str, quantity: float) -> Fill | None:
    """
    Simulates a market order: takes liquidity immediately, walking price
    levels in order (best price first) until `quantity` is filled or the
    book runs out.

    This is where slippage comes from naturally — if the top level can't
    cover the full order, the average fill price drifts away from the
    best price as deeper, worse-priced levels get consumed. No separate
    slippage formula needed; it falls out of walking real depth.

    Returns None if the book has zero liquidity on the relevant side
    (nothing to fill against at all) — a market order matching zero
    liquidity isn't a fill, it's a no-op.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    # Buying consumes asks (lowest price first); selling consumes bids (highest first)
    levels = sorted(book.asks.items()) if side == "buy" else sorted(book.bids.items(), reverse=True)

    remaining = quantity
    total_cost = 0.0
    filled_qty = 0.0

    for price, available_qty in levels:
        if remaining <= 0:
            break
        take = min(remaining, available_qty)
        total_cost += take * price
        filled_qty += take
        remaining -= take

    if filled_qty == 0:
        return None

    avg_price = total_cost / filled_qty
    fee = filled_qty * avg_price * TAKER_FEE_RATE

    return Fill(
        symbol=book.symbol,
        side=side,
        quantity=filled_qty,
        price=avg_price,
        fee=fee,
        fully_filled=(remaining <= 0),
    )


def match_limit_order(
    book: OrderBook, side: str, quantity: float, limit_price: float
) -> Fill | None:
    """
    Simulates a limit order: only fills against price levels at least as
    good as `limit_price` (<=, for buy; >=, for sell). Unlike a market
    order, this never fills at a worse price than requested — it may
    fill partially, or not at all, but never "spills over" into worse
    price levels the way a market order does.

    A limit order treated as a maker fill (resting liquidity), so uses
    MAKER_FEE_RATE rather than the taker rate.

    Returns None if no price level satisfies the limit at all.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    if side == "buy":
        levels = sorted((p, q) for p, q in book.asks.items() if p <= limit_price)
    else:
        levels = sorted(((p, q) for p, q in book.bids.items() if p >= limit_price), reverse=True)

    remaining = quantity
    total_cost = 0.0
    filled_qty = 0.0

    for price, available_qty in levels:
        if remaining <= 0:
            break
        take = min(remaining, available_qty)
        total_cost += take * price
        filled_qty += take
        remaining -= take

    if filled_qty == 0:
        return None

    avg_price = total_cost / filled_qty
    fee = filled_qty * avg_price * MAKER_FEE_RATE

    return Fill(
        symbol=book.symbol,
        side=side,
        quantity=filled_qty,
        price=avg_price,
        fee=fee,
        fully_filled=(remaining <= 0),
    )