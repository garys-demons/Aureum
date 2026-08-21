"""
Tests for BaselineMarketMaker's decide() and inventory tracking.
Pure math (compute_fair_price, compute_skewed_quotes) already covered
in test_baseline_market_maker.py - these test the strategy class itself.
"""
from core.strategy.baseline_market_maker import BaselineMarketMaker
from core.strategy.base import Signal


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