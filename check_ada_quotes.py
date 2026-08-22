from core.strategy.baseline_market_maker import compute_fair_price, compute_skewed_quotes

md = {"price": 0.1750}
fair = compute_fair_price(md)
bid, ask = compute_skewed_quotes(
    fair, inventory=0.0, base_half_spread=0.0001, inventory_skew_sensitivity=0.00001
)
print(f"fair={fair}, bid={bid}, ask={ask}")

from core.strategy.base import Signal, StrategyInterface

# Starting parameters for ADA (Phase 5 baseline pair). Not yet validated
# by real backtesting — Hansika's parameter-sensitivity task covers that.
# Scaled to ADA's price level (~$0.17-0.19 on testnet at time of writing),
# NOT the BTC-scale numbers used in early hand-verification.
DEFAULT_BASE_HALF_SPREAD = 0.0005       # ~0.3% of price, a starting guess
DEFAULT_INVENTORY_SKEW_SENSITIVITY = 0.00002
DEFAULT_ORDER_QUANTITY = 100.0          # units of ADA per quote


class BaselineMarketMaker(StrategyInterface):
    """
    Inventory-aware market maker — the mandatory zero-AI baseline
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