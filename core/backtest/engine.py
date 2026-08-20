"""
Event-driven backtest engine (Phase 4).

Core rule (non-negotiable, per Phase 4 task doc): strategies are fed
through the SAME core.strategy.StrategyInterface used live. This module
never defines a parallel/backtest-only strategy interface — doing so
would mean backtest results stop meaning anything about live behavior.

No-look-ahead is enforced structurally: events are processed strictly
one at a time, in chronological order, and the strategy is only ever
given data derived from events up to and including the current one.
"""
from typing import Union
from services.market_data.order_book_state import OrderBook

from core.strategy.base import StrategyInterface, Signal
from services.market_data.models import Candle, TradeEvent, OrderBookDelta, OrderBookSnapshot

HistoricalEvent = Union[Candle, TradeEvent, OrderBookDelta, OrderBookSnapshot]


def _event_timestamp(event: HistoricalEvent) -> int:
    """
    Extract the timestamp used for chronological ordering.

    Candles are ordered by close_time (when the bar actually finished -
    using open_time would let a strategy "see" a candle before it's
    really over, which is itself a subtle look-ahead leak).
    Trades and order book events are ordered by event_time.
    """
    if isinstance(event, Candle):
        return event.close_time
    return event.event_time


def sort_events_chronologically(events: list[HistoricalEvent]) -> list[HistoricalEvent]:
    """
    Merge and sort historical events (candles, trades, order book
    snapshots/deltas) into strict chronological order, ready for
    one-at-a-time processing by the engine.
    """
    return sorted(events, key=_event_timestamp)

class BacktestEngine:
    """
    Processes historical events one at a time, in strict chronological
    order, feeding each one to a strategy through the SAME
    StrategyInterface used live (core.strategy.base). Records every
    Signal the strategy returns, in order, for later analysis.
    """

    def __init__(self, strategy: StrategyInterface):
        self.strategy = strategy
        self.signals: list[Signal] = []
        self._order_book: OrderBook | None = None

    def run(self, events: list[HistoricalEvent]) -> list[Signal]:
        """
        Run the backtest over `events`. Events are sorted chronologically
        first, then processed one at a time - the strategy only ever
        sees data derived from the current event and everything before
        it, never anything later in the list.
        """
        sorted_events = sort_events_chronologically(events)
        self.signals = []


        for event in sorted_events:
            self._update_order_book(event)
            market_data = self._build_market_data(event)
            signal = self.strategy.decide(market_data)
            self.signals.append(signal)
        return self.signals
    
    def _update_order_book(self, event: HistoricalEvent) -> None:
        
        if isinstance(event, OrderBookSnapshot):
            self._order_book = OrderBook(event)

        elif isinstance(event, OrderBookDelta):
            if self._order_book is None:
                return  # no snapshot yet to apply against

            expected_first_id = self._order_book.last_update_id + 1
            if event.first_update_id != expected_first_id:
                raise ValueError(
                    f"Order book gap detected during backtest: expected "
                    f"delta.first_update_id={expected_first_id}, got "
                    f"{event.first_update_id}. Refusing to apply - would "
                    f"silently corrupt book state for the rest of the run."
                )

            self._order_book.apply_delta(event)
 
    def _build_market_data(self, event: HistoricalEvent) -> dict:
        """
        Convert a single historical event into the market_data dict
        shape the strategy interface expects. Only fields derivable
        from THIS event are included - never anything from later events.
        """
        market_data: dict = {
            "symbol": event.symbol,
            "timestamp": _event_timestamp(event),
            "event_type": event.event_type,
        }

        if self._order_book is not None:
            market_data["order_book_best_bid"] = self._order_book.best_bid
            market_data["order_book_best_ask"] = self._order_book.best_ask

        if isinstance(event, Candle):
            market_data["price"] = event.close
            market_data["open"] = event.open
            market_data["high"] = event.high
            market_data["low"] = event.low
            market_data["volume"] = event.volume

        elif isinstance(event, TradeEvent):
            market_data["price"] = event.price
            market_data["quantity"] = event.quantity

        elif isinstance(event, OrderBookSnapshot):
            market_data["best_bid"] = event.bids[0].price if event.bids else None
            market_data["best_ask"] = event.asks[0].price if event.asks else None

        elif isinstance(event, OrderBookDelta):
            market_data["update_id"] = event.final_update_id

        return market_data