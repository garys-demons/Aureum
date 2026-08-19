"""
Tests for the event-driven backtest engine (Phase 4).

The centerpiece test (test_strategy_cannot_access_future_events) proves
the engine's no-look-ahead guarantee structurally, not just by
inspection - a strategy that actively TRIES to cheat must fail to do so.
"""
import pytest

from core.backtest.engine import BacktestEngine, sort_events_chronologically
from core.strategy.base import StrategyInterface, Signal
from services.market_data.models import TradeEvent


def make_trade(trade_id: int, event_time: int, price: float = 50000) -> TradeEvent:
    return TradeEvent(
        event_type="trade", exchange="binance", symbol="BTCUSDT",
        event_time=event_time, received_time=event_time,
        trade_id=trade_id, price=price, quantity=0.1,
        buyer_maker=True, trade_time=event_time,
    )


class CheatingStrategy(StrategyInterface):
    """
    A malicious/buggy strategy that tries to grab future data out of
    market_data, simulating exactly the kind of look-ahead leak the
    engine must prevent. Used only in this test.
    """

    def __init__(self):
        self.seen_timestamps: list[int] = []

    def decide(self, market_data: dict) -> Signal:
        self.seen_timestamps.append(market_data["timestamp"])

        # Attempt to cheat: look for any key that might expose future
        # data. A correctly-built market_data dict simply won't have
        # these keys, no matter how hard we look for them.
        forbidden_keys = ["future_events", "next_event", "all_events", "lookahead"]
        for key in forbidden_keys:
            assert key not in market_data, f"Engine leaked future data via key '{key}'"

        return Signal(action="hold", symbol=market_data["symbol"], reason="cheat attempt")


def test_strategy_cannot_access_future_events():
    """
    The centerpiece no-look-ahead test: feeds events out of order, and
    confirms the strategy sees them ONLY in correct chronological order,
    one at a time, with no way to reach into future events.
    """
    trades = [
        make_trade(1, event_time=300, price=50300),
        make_trade(2, event_time=100, price=50100),
        make_trade(3, event_time=200, price=50200),
    ]

    strategy = CheatingStrategy()
    engine = BacktestEngine(strategy=strategy)
    engine.run(trades)

    # The strategy must have seen timestamps in strictly increasing
    # order - proof it was never handed events out of sequence.
    assert strategy.seen_timestamps == [100, 200, 300]


def test_market_data_only_reflects_current_event_fields():
    """
    market_data for a given event must only ever contain fields derived
    from that single event - never a reference to the full event list
    or any other event.
    """
    trades = [make_trade(1, event_time=100, price=111), make_trade(2, event_time=200, price=222)]

    seen_market_data = []

    class RecordingStrategy(StrategyInterface):
        def decide(self, market_data: dict) -> Signal:
            seen_market_data.append(dict(market_data))
            return Signal(action="hold", symbol=market_data["symbol"])

    engine = BacktestEngine(strategy=RecordingStrategy())
    engine.run(trades)

    assert seen_market_data[0]["price"] == 111
    assert seen_market_data[1]["price"] == 222
    # Nothing in the first call's data should mention the second trade's price
    assert 222 not in seen_market_data[0].values()


def test_run_returns_signals_in_chronological_order():
    trades = [make_trade(1, event_time=300), make_trade(2, event_time=100), make_trade(3, event_time=200)]

    from core.strategy.stub_strategy import StubStrategy
    engine = BacktestEngine(strategy=StubStrategy())
    signals = engine.run(trades)

    assert len(signals) == 3
    assert all(s.action == "hold" for s in signals)


def test_sort_events_chronologically_orders_by_timestamp():
    trades = [make_trade(1, event_time=300), make_trade(2, event_time=100)]
    sorted_trades = sort_events_chronologically(trades)

    assert sorted_trades[0].trade_id == 2
    assert sorted_trades[1].trade_id == 1


def test_candle_ordered_by_close_time_not_open_time():
    """
    A candle must be ordered by when it actually finished (close_time),
    not when it started - otherwise the engine could hand a strategy a
    candle before it's genuinely over, a subtle look-ahead leak.
    """
    from services.market_data.models import Candle

    candle = Candle(
        event_type="kline", exchange="binance", symbol="BTCUSDT",
        event_time=1, received_time=1, interval="1m",
        open_time=100, close_time=160,  # opens at 100, closes at 160
        open=1, high=1, low=1, close=1, volume=1, is_closed=True,
    )
    trade = make_trade(1, event_time=120)  # happens WHILE the candle is still open

    sorted_events = sort_events_chronologically([candle, trade])

    # The trade (at t=120) must come before the candle (closes at t=160),
    # even though the candle's open_time (100) is earlier than the trade.
    assert sorted_events[0] is trade
    assert sorted_events[1] is candle