"""
Tests for the baseline market maker's pure math (Phase 5).
Hand-calculated expected values, same rigor as Phase 2-4 work.
"""
import pytest

from core.strategy.baseline_market_maker import compute_fair_price, compute_skewed_quotes


def test_fair_price_uses_order_book_midpoint_when_available():
    market_data = {"order_book_best_bid": 64990.0, "order_book_best_ask": 65010.0, "price": 64995.0}
    assert compute_fair_price(market_data) == 65000.0


def test_fair_price_falls_back_to_candle_or_trade_price():
    market_data = {"price": 65000.0}
    assert compute_fair_price(market_data) == 65000.0


def test_fair_price_none_when_nothing_available():
    market_data = {"symbol": "BTCUSDT", "timestamp": 123}
    assert compute_fair_price(market_data) is None


def test_flat_inventory_produces_symmetric_quotes():
    bid, ask = compute_skewed_quotes(
        fair_price=65000.0, inventory=0.0,
        base_half_spread=5.0, inventory_skew_sensitivity=0.1,
    )
    assert bid == 64995.0
    assert ask == 65005.0


def test_long_inventory_skews_both_quotes_down():
    bid, ask = compute_skewed_quotes(
        fair_price=65000.0, inventory=10.0,
        base_half_spread=5.0, inventory_skew_sensitivity=0.1,
    )
    assert bid == 64994.0
    assert ask == 65004.0
    # Ask closer to fair price than bid's distance -> more attractive to sell into
    assert (ask - 65000.0) < (65000.0 - bid)


def test_short_inventory_skews_both_quotes_up():
    bid, ask = compute_skewed_quotes(
        fair_price=65000.0, inventory=-10.0,
        base_half_spread=5.0, inventory_skew_sensitivity=0.1,
    )
    assert bid == 64996.0
    assert ask == 65006.0
    assert (65000.0 - bid) < (ask - 65000.0)


def test_larger_inventory_produces_larger_skew():
    _, ask_small = compute_skewed_quotes(
        fair_price=65000.0, inventory=5.0,
        base_half_spread=5.0, inventory_skew_sensitivity=0.1,
    )
    _, ask_large = compute_skewed_quotes(
        fair_price=65000.0, inventory=50.0,
        base_half_spread=5.0, inventory_skew_sensitivity=0.1,
    )
    assert ask_large < ask_small