"""
StrategyInterface — every trading strategy must follow this shape.
Right now this is a stub: it doesn't make real decisions yet,
but Gauri's execution code can already be built against it.
"""

from abc import ABC, abstractmethod
from typing import Any


class Signal:
    """A decision the strategy hands off to execution."""
    def __init__(self, action: str, symbol: str, reason: str = ""):
        # action must be one of: "buy", "sell", "hold"
        self.action = action
        self.symbol = symbol
        self.reason = reason

    def __repr__(self):
        return f"Signal(action={self.action}, symbol={self.symbol}, reason={self.reason})"


class StrategyInterface(ABC):
    """Base class every strategy must implement."""

    @abstractmethod
    def decide(self, market_data: dict[str, Any]) -> Signal:
        """
        Given the latest market data, return a Signal.
        market_data will contain things like price, volume, etc.
        (exact shape gets finalized once Hansika's data models are done)
        """
        raise NotImplementedError