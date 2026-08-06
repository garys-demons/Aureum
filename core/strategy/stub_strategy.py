"""
StubStrategy — the simplest possible strategy: always holds.
Exists only to prove the interface works end-to-end.
Real strategy logic comes in a later phase.
"""

from core.strategy.base import StrategyInterface, Signal


class StubStrategy(StrategyInterface):
    def decide(self, market_data: dict) -> Signal:
        symbol = market_data.get("symbol", "UNKNOWN")
        return Signal(action="hold", symbol=symbol, reason="stub strategy — always holds")