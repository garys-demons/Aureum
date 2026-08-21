"""
StrategyInterface — every trading strategy must follow this shape.

Signal now carries optional price/quantity (Phase 5), needed for
strategies like the baseline market maker that quote specific prices
rather than just "buy"/"sell" at market. decide() may return a single
Signal or a list[Signal] - a market maker naturally returns two
(bid + ask) from one call. Confirmed compatible with paper_exchange's
match_market_order/match_limit_order by Gauri.
"""
from abc import ABC, abstractmethod
from typing import Any, Union


class Signal:
    """A decision the strategy hands off to execution."""

    def __init__(
        self,
        action: str,
        symbol: str,
        reason: str = "",
        price: float | None = None,
        quantity: float | None = None,
    ):
        # action must be one of: "buy", "sell", "hold"
        # price: set for limit orders (e.g. a market maker's quote).
        #        None means market order / not applicable (e.g. "hold").
        # quantity: order size. None only valid alongside action="hold".
        self.action = action
        self.symbol = symbol
        self.reason = reason
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        return (
            f"Signal(action={self.action}, symbol={self.symbol}, "
            f"price={self.price}, quantity={self.quantity}, reason={self.reason})"
        )


class StrategyInterface(ABC):
    """Base class every strategy must implement."""

    @abstractmethod
    def decide(self, market_data: dict[str, Any]) -> Union[Signal, list[Signal]]:
        """
        Given the latest market data, return a Signal or list[Signal].

        A market maker returning [bid_signal, ask_signal] produces TWO
        independent Fill objects if both are eventually matched - callers
        (e.g. portfolio tracking) must treat these as separate fills, not
        assume one decide() call means one fill (Gauri, Phase 5 review).
        """
        raise NotImplementedError