"""
Baseline inventory-aware market maker (Phase 5).

Per the Baseline-First Rule: this is the mandatory, zero-AI reference
strategy every future AI comparison gets measured against. References
the Avellaneda-Stoikov model's core ideas (fair-price quoting, inventory
skew) without implementing the full paper's volatility/time-horizon terms
- those are a documented future refinement, not needed for a first
correct baseline.

This module contains the pure math only (fair price, skewed quotes) -
no Signal construction yet, since Signal's shape (single action vs.
price/quantity, single vs. two-sided) is still being finalized with
Gauri's execution-wiring work. Keeping this pure and Signal-agnostic
means it's usable regardless of how that resolves.
"""


def compute_fair_price(market_data: dict) -> float | None:
    """
    Derives a fair price from whatever the current event actually gives us.

    Preference order:
    1. Real order book midpoint (order_book_best_bid/ask) - most accurate,
       but only present if this backtest run includes order-book events.
    2. Candle close - the settled price of the most recent completed bar.
       The current baseline dataset (btcusdt_candles_1m) has NO
       order-book events at all, so this is the path actually exercised
       right now, not a fallback edge case.
    3. Trade price - if all we have is a single trade event.

    Returns None if none of the above are available (e.g. an
    OrderBookDelta arriving before the book is initialized) - the
    strategy must handle this by holding, not by guessing a price.
    """
    best_bid = market_data.get("order_book_best_bid")
    best_ask = market_data.get("order_book_best_ask")
    if best_bid is not None and best_ask is not None:
        return (best_bid + best_ask) / 2

    if "price" in market_data:
        return market_data["price"]

    return None


def compute_skewed_quotes(
    fair_price: float,
    inventory: float,
    *,
    base_half_spread: float,
    inventory_skew_sensitivity: float,
) -> tuple[float, float]:
    """
    Returns (bid_price, ask_price) around fair_price, adjusted for
    current inventory.

    Convention, stated explicitly: positive inventory means net LONG.

    Derivation:
    - Long inventory -> we want to reduce it -> we want to sell.
    - To sell faster, our ASK must be more attractive to buyers,
      i.e. LOWER than it would otherwise be.
    - To slow further buying (avoid getting more long), our BID must
      be less attractive to sellers, i.e. also LOWER.
    - So: long inventory -> skew BOTH quotes down.
    - Symmetric case: short inventory -> skew both quotes up.

    skew = -inventory * inventory_skew_sensitivity
    (positive inventory -> negative skew -> quotes shift down, confirmed
    by the derivation above)

    base_half_spread: distance from fair_price to each unskewed quote.
    inventory_skew_sensitivity: price-unit shift per unit of inventory.
    Starting parameter, not yet validated - real tuning is Hansika's
    Phase 5 parameter-sensitivity task.
    """
    skew = -inventory * inventory_skew_sensitivity

    bid_price = fair_price - base_half_spread + skew
    ask_price = fair_price + base_half_spread + skew

    return bid_price, ask_price