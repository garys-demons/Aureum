# core/backtest/signal_router.py
"""
Routes strategy Signals to paper exchange fills. Bridges core/strategy's
decide() output to core/backtest's fill simulation.
"""
from core.strategy.base import Signal
from core.backtest.paper_exchange import match_market_order, match_limit_order, Fill
from services.market_data.order_book import OrderBook


def route_signal(signal: Signal, book: OrderBook) -> Fill | None:
    if signal.action == "hold":
        return None
    if signal.price is not None:
        return match_limit_order(
            book, side=signal.action, quantity=signal.quantity, limit_price=signal.price
        )
    return match_market_order(book, side=signal.action, quantity=signal.quantity)


def route_signal_and_record(signal: Signal, book: OrderBook, strategy) -> Fill | None:
    """
    Routes one signal to a fill, then immediately calls
    strategy.record_fill() — enforces the timing requirement: inventory
    must update before the next decide() call.
    """
    fill = route_signal(signal, book)
    if fill is not None:
        strategy.record_fill(action=fill.side, quantity=fill.quantity)
    return fill


def route_signals_and_record(signals: Signal | list[Signal], book: OrderBook, strategy) -> list[Fill]:
    """
    Handles a single Signal or list[Signal]. Each fill is recorded
    immediately after it happens, one at a time.
    """
    if isinstance(signals, Signal):
        signals = [signals]

    fills = []
    for signal in signals:
        fill = route_signal_and_record(signal, book, strategy)
        if fill is not None:
            fills.append(fill)
    return fills
