"""
Tests for BaselineMarketMaker's decide() and inventory tracking.
Pure math (compute_fair_price, compute_skewed_quotes) already covered
in test_baseline_market_maker.py - these test the strategy class itself.
"""
from core.strategy.baseline_market_maker import BaselineMarketMaker
from core.strategy.base import Signal
from services.market_data.models import Candle


def test_decide_returns_two_signals_bid_and_ask():
    strat = BaselineMarketMaker(symbol="ADAUSDT")
    result = strat.decide({"price": 0.1750})

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].action == "buy"
    assert result[1].action == "sell"


def test_decide_quotes_bracket_fair_price():
    strat = BaselineMarketMaker(symbol="ADAUSDT", base_half_spread=0.0005)
    bid_signal, ask_signal = strat.decide({"price": 0.1750})

    assert bid_signal.price < 0.1750
    assert ask_signal.price > 0.1750


def test_decide_holds_when_no_fair_price_available():
    strat = BaselineMarketMaker(symbol="ADAUSDT")
    result = strat.decide({"symbol": "ADAUSDT", "timestamp": 123})

    assert isinstance(result, Signal)
    assert result.action == "hold"


def test_inventory_starts_at_zero():
    strat = BaselineMarketMaker(symbol="ADAUSDT")
    assert strat.inventory == 0.0


def test_record_fill_updates_inventory_correctly():
    strat = BaselineMarketMaker(symbol="ADAUSDT")
    strat.record_fill("buy", 50.0)
    assert strat.inventory == 50.0

    strat.record_fill("sell", 20.0)
    assert strat.inventory == 30.0


def test_quotes_reflect_updated_inventory_skew():
    strat = BaselineMarketMaker(symbol="ADAUSDT", inventory_skew_sensitivity=0.00002)

    _, ask_before = strat.decide({"price": 0.1750})

    strat.record_fill("buy", 1000.0)  # go long
    _, ask_after = strat.decide({"price": 0.1750})

    # Long inventory -> both quotes skew down -> ask should be lower/more attractive to sell into
    assert ask_after.price < ask_before.price


def test_all_signals_carry_the_configured_symbol():
    strat = BaselineMarketMaker(symbol="ADAUSDT")
    bid, ask = strat.decide({"price": 0.1750})
    assert bid.symbol == "ADAUSDT"
    assert ask.symbol == "ADAUSDT"

def test_candle_to_engine_to_fair_price_integration():
    """
    Regression guard, per Gauri's Phase 5 review: every other test here
    hand-builds market_data directly, so nothing would catch a future
    engine.py refactor breaking the Candle.close -> market_data["price"]
    mapping. This strategy is the permanent Phase 5 benchmark - worth
    protecting the real wiring, not just the isolated function.
    """
    from core.backtest.engine import BacktestEngine

    candle = Candle(
        event_type="candle", exchange="binance", symbol="ADAUSDT",
        event_time=1_700_000_000_000, received_time=1_700_000_000_000,
        interval="1m", open_time=1_700_000_000_000, close_time=1_700_000_060_000,
        open=0.1750, high=0.1755, low=0.1748, close=0.1752,
        volume=1000.0, is_closed=True,
    )

    strategy = BaselineMarketMaker(symbol="ADAUSDT")
    engine = BacktestEngine(strategy=strategy)

    signals = engine.run([candle])

    # decide() returns [bid_signal, ask_signal] for a market maker;
    # engine.run() correctly flattens this into 2 individual signals,
    # not 1 - confirmed by the earlier list[Signal] flattening fix.
    assert len(signals) == 2
    bid = next(s for s in signals if s.action == "buy")
    ask = next(s for s in signals if s.action == "sell")
    assert bid.price < 0.1752 < ask.price  # brackets the real candle close, not a hand-built price