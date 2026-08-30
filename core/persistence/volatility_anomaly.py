"""
core/persistence/volatility_anomaly.py — extreme volatility detection.

New for Phase 6 (kill-switch trigger conditions). Tracks recent price
observations in a sliding time window per symbol and flags when the
price has moved more than a configured percentage within that window -
a signal that market conditions have become unusually violent, which
is itself a reason to pause trading regardless of what any individual
strategy signal says.

Deliberately separate from anomaly.py's existing monitors (sequence
gaps, reconnect frequency) since this tracks price data, not stream
health - different inputs, same "flag it, don't crash on it" spirit.
"""
from collections import deque
from datetime import datetime, timezone

import structlog

log = structlog.get_logger("volatility_anomaly")


class ExtremeVolatilityMonitor:
    """
    Tracks (timestamp, price) observations in a sliding window per
    symbol and flags when price has moved more than `max_pct_move`
    within `window_seconds`.
    """

    def __init__(self, window_seconds: int = 60, max_pct_move: float = 0.02):
        self.window_seconds = window_seconds
        self.max_pct_move = max_pct_move
        self._observations: dict[str, deque] = {}

    def observe(self, symbol: str, price: float, timestamp: datetime | None = None) -> bool:
        """
        Record a new price observation for `symbol`. Returns True if the
        price has moved more than `max_pct_move` compared to the oldest
        observation still within the window (and logs it).
        """
        now = timestamp or datetime.now(timezone.utc)
        window = self._observations.setdefault(symbol, deque())
        window.append((now, price))

        cutoff = now.timestamp() - self.window_seconds
        while window and window[0][0].timestamp() < cutoff:
            window.popleft()

        if len(window) < 2:
            return False

        oldest_price = window[0][1]
        pct_move = abs(price - oldest_price) / oldest_price

        if pct_move > self.max_pct_move:
            log.warning(
                "extreme_volatility_detected",
                symbol=symbol,
                oldest_price=oldest_price,
                latest_price=price,
                pct_move=round(pct_move, 4),
                threshold=self.max_pct_move,
                window_seconds=self.window_seconds,
            )
            return True
        return False