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


from core.strategy.base import Signal, StrategyInterface

# Tuned via evaluation across 3 independent windows (Phase 5, 2026-08-22):
# 0.0005 (original guess) lost money consistently (4-7% win rate, fee
# drag + tight spread relative to ADA's intra-candle volatility).
# 0.001 is profitable across all 3 windows with meaningful trade volume
# (20-46 fills). 0.002 showed 100% win rate but too few fills (4-10) to
# be statistically meaningful, and lower total returns than 0.001.
DEFAULT_BASE_HALF_SPREAD = 0.001DEFAULT_INVENTORY_SKEW_SENSITIVITY = 0.00002
DEFAULT_ORDER_QUANTITY = 100.0          # units of ADA per quote


class BaselineMarketMaker(StrategyInterface):
    """
    Inventory-aware market maker - the mandatory zero-AI baseline
    (Phase 5). References Avellaneda-Stoikov's core ideas (fair-price
    quoting, inventory skew); does not implement the full paper's
    volatility/time-horizon terms - documented simplification, not
    an oversight.

    Tracks its own inventory internally, updated externally via
    record_fill() after each backtest fill - the strategy itself has
    no visibility into the paper exchange or portfolio, per the
    architecture's Strategy -> Risk -> Execution separation.
    """

    def __init__(
        self,
        symbol: str,
        base_half_spread: float = DEFAULT_BASE_HALF_SPREAD,
        inventory_skew_sensitivity: float = DEFAULT_INVENTORY_SKEW_SENSITIVITY,
        order_quantity: float = DEFAULT_ORDER_QUANTITY,
    ):
        self.symbol = symbol
        self.base_half_spread = base_half_spread
        self.inventory_skew_sensitivity = inventory_skew_sensitivity
        self.order_quantity = order_quantity
        self.inventory: float = 0.0

    def record_fill(self, action: str, quantity: float) -> None:
        """
        Called externally (by whatever drives the backtest loop) after
        a fill actually happens, so the strategy's inventory tracking
        matches reality rather than assuming every quote fills.
        """
        if action == "buy":
            self.inventory += quantity
        elif action == "sell":
            self.inventory -= quantity

    def decide(self, market_data: dict) -> list[Signal] | Signal:
        """
        Returns [bid_signal, ask_signal] - two independent quotes per
        Gauri's confirmed paper_exchange design. Returns a single
        "hold" Signal if no fair price can be derived from this event
        (e.g. an OrderBookDelta before the book is initialized).
        """
        fair_price = compute_fair_price(market_data)
        if fair_price is None:
            return Signal(action="hold", symbol=self.symbol, reason="no fair price available")

        bid_price, ask_price = compute_skewed_quotes(
            fair_price,
            self.inventory,
            base_half_spread=self.base_half_spread,
            inventory_skew_sensitivity=self.inventory_skew_sensitivity,
        )

        return [
            Signal(
                action="buy", symbol=self.symbol, price=bid_price,
                quantity=self.order_quantity,
                reason=f"quote bid: fair={fair_price:.5f} inventory={self.inventory}",
            ),
            Signal(
                action="sell", symbol=self.symbol, price=ask_price,
                quantity=self.order_quantity,
                reason=f"quote ask: fair={fair_price:.5f} inventory={self.inventory}",
            ),
        ]