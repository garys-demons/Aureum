"""
Deduplication logic for market data events (TRD §7).

Trades are the only event type needing explicit dedup — order book deltas
are handled via the reconciliation contiguity check (order_book.py), and
tickers/candles are naturally idempotent (latest value always wins).
"""
from collections import deque

from services.market_data.models import TradeEvent


class TradeDeduplicator:
    """
    Tracks recently-seen trade keys to detect and drop duplicates.

    Uses a bounded cache (deque + set) so memory doesn't grow unbounded
    over a long-running session (TRD §13 performance requirement).
    """

    def __init__(self, max_size: int = 10_000):
        self._max_size = max_size
        self._seen_keys: set[tuple[str, str, int]] = set()
        self._order: deque[tuple[str, str, int]] = deque()

    def _make_key(self, trade: TradeEvent) -> tuple[str, str, int]:
        return (trade.exchange, trade.symbol, trade.trade_id)

    def is_duplicate(self, trade: TradeEvent) -> bool:
        """Returns True if this exact trade has already been seen."""
        key = self._make_key(trade)
        return key in self._seen_keys

    def mark_seen(self, trade: TradeEvent) -> None:
        """Record this trade as seen, evicting the oldest entry if over capacity."""
        key = self._make_key(trade)
        if key in self._seen_keys:
            return

        self._seen_keys.add(key)
        self._order.append(key)

        if len(self._order) > self._max_size:
            oldest = self._order.popleft()
            self._seen_keys.discard(oldest)