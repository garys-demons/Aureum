"""
tests/unit/test_portfolio.py

Confirms core/portfolio/portfolio.py's PnL math is correct — every
expected value here is hand-calculated, not just "does it run", same
rigor standard as Phase 2/3's metrics work.
"""
from datetime import datetime

import pytest

from core.portfolio.portfolio import Fill, Portfolio


def test_single_buy_updates_cash_and_position():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 1.0, datetime(2024, 1, 1)))

    # cash = 10000 - (1*100) - 1 = 9899
    assert p.cash == 9899.0
    assert p.position("BTCUSDT") == 1.0


def test_two_buys_compute_weighted_average_entry_price():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 1.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 110.0, 1.0, datetime(2024, 1, 2)))

    # avg = (100*1 + 110*1) / 2 = 105
    assert p.cash == 9788.0  # 9899 - 110 - 1
    assert p.position("BTCUSDT") == 2.0


def test_sell_computes_correct_realized_pnl():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 1.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 110.0, 1.0, datetime(2024, 1, 2)))
    # avg_entry_price is now 105
    p.process_fill(Fill("BTCUSDT", "sell", 1.0, 120.0, 1.0, datetime(2024, 1, 3)))

    # realized = (120 - 105) * 1 - 1 = 14
    assert p.realized_pnl == 14.0
    assert p.cash == 9788.0 + 120.0 - 1.0  # = 9907.0
    assert p.position("BTCUSDT") == 1.0  # 1 remaining


def test_unrealized_pnl_marks_open_position_to_market():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 2.0, 100.0, 0.0, datetime(2024, 1, 1)))

    # unrealized = (130 - 100) * 2 = 60
    assert p.unrealized_pnl({"BTCUSDT": 130.0}) == 60.0


def test_summary_computes_correct_final_metrics():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 1.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 110.0, 1.0, datetime(2024, 1, 2)))
    p.process_fill(Fill("BTCUSDT", "sell", 1.0, 120.0, 1.0, datetime(2024, 1, 3)))

    summary = p.summary(current_prices={"BTCUSDT": 130.0})

    assert summary["realized_pnl"] == 14.0
    assert summary["unrealized_pnl"] == 25.0  # (130 - 105) * 1
    assert summary["final_equity"] == 9907.0 + 130.0  # cash + 1 * 130 = 10037.0
    assert summary["total_return_pct"] == pytest.approx(0.37, abs=1e-6)  # (10037-10000)/10000*100
    assert summary["num_trades"] == 3
    assert summary["num_buys"] == 2
    assert summary["num_sells"] == 1
    assert summary["win_rate_pct"] == 100.0  # the one sell was profitable


def test_win_rate_reflects_losing_trades_too():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "sell", 1.0, 90.0, 0.0, datetime(2024, 1, 2)))  # losing sell
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 3)))
    p.process_fill(Fill("BTCUSDT", "sell", 1.0, 110.0, 0.0, datetime(2024, 1, 4)))  # winning sell

    summary = p.summary()
    assert summary["num_sells"] == 2
    assert summary["win_rate_pct"] == 50.0  # 1 of 2 sells profitable


def test_win_rate_is_none_with_no_sells_yet():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 1)))
    summary = p.summary()
    assert summary["win_rate_pct"] is None


def test_insufficient_cash_is_rejected():
    p = Portfolio(starting_cash=100.0)
    with pytest.raises(ValueError, match="Insufficient cash"):
        p.process_fill(Fill("BTCUSDT", "buy", 1.0, 200.0, 1.0, datetime(2024, 1, 1)))


def test_selling_more_than_held_opens_a_short_position():
    """
    Regression test for Phase 5: the original long-only restriction was
    removed because BaselineMarketMaker legitimately needs to sell
    before holding any inventory (two-sided quoting). Selling more than
    currently held should now correctly open a short position, not raise.
    """
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "sell", 3.0, 100.0, 0.0, datetime(2024, 1, 2)))
    # 1 long unit closes, 2 remaining units open a new short
    assert p.position("BTCUSDT") == -2.0


def test_opening_a_short_from_flat():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))

    assert p.position("BTCUSDT") == -10.0
    # Selling receives cash, regardless of long/short
    assert p.cash == 10_000.0 + 1_000.0


def test_covering_a_profitable_short():
    """Short 10 @ $100, cover (buy back) at $90 — price fell, short profits.
    realized = (entry - exit) * qty = (100 - 90) * 10 = 100."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 10.0, 90.0, 0.0, datetime(2024, 1, 2)))

    assert p.position("BTCUSDT") == 0.0
    assert p.realized_pnl == 100.0
    assert p.cash == 10_000.0 + 1_000.0 - 900.0  # = 10100.0


def test_covering_a_losing_short():
    """Short 10 @ $100, cover at $110 — price rose against the short.
    realized = (100 - 110) * 10 = -100 (a loss)."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 10.0, 110.0, 0.0, datetime(2024, 1, 2)))

    assert p.realized_pnl == -100.0


def test_position_flip_from_short_to_long():
    """Short 15 @ $50, then buy 20 @ $45: 15 closes the short (realizing
    PnL), remaining 5 opens a new LONG position at the fill price."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 15.0, 50.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 20.0, 45.0, 0.0, datetime(2024, 1, 2)))

    assert p.position("BTCUSDT") == 5.0  # flipped from -15 to +5
    assert p.realized_pnl == 75.0  # (50-45)*15 closing the short


def test_position_flip_from_long_to_short():
    """Buy 10 @ $100, then sell 15 @ $105: 10 closes the long (realizing
    PnL), remaining 5 opens a new SHORT position at the fill price."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "sell", 15.0, 105.0, 0.0, datetime(2024, 1, 2)))

    assert p.position("BTCUSDT") == -5.0  # flipped from +10 to -5
    assert p.realized_pnl == 50.0  # (105-100)*10 closing the long


def test_unrealized_pnl_correct_for_short_position():
    """Short 10 @ $100. Price drops to $90 -> short is profitable.
    unrealized = (current - entry) * quantity = (90 - 100) * -10 = 100."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))

    assert p.unrealized_pnl({"BTCUSDT": 90.0}) == 100.0
    # Price rising against the short should show a loss
    assert p.unrealized_pnl({"BTCUSDT": 110.0}) == -100.0


def test_total_equity_includes_short_position_value():
    """A short position should REDUCE total equity by its market value
    (you owe those units back), not be excluded from the calculation."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))
    # cash = 10000 + 1000 = 11000; position value = -10 * 100 = -1000
    assert p.total_equity({"BTCUSDT": 100.0}) == 11_000.0 - 1_000.0


def test_win_rate_counts_profitable_short_covers_as_wins():
    """A profitable BUY that covers a short must count toward win rate,
    not just profitable sells — this only matters once shorting exists."""
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "sell", 10.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("BTCUSDT", "buy", 10.0, 90.0, 0.0, datetime(2024, 1, 2)))  # winning cover

    summary = p.summary()
    assert summary["num_closing_trades"] == 1
    assert summary["win_rate_pct"] == 100.0


def test_no_cash_check_for_opening_a_short():
    """Opening a short receives cash immediately — it should never be
    blocked by an affordability check the way a buy is."""
    p = Portfolio(starting_cash=10.0)  # very little cash
    # Should not raise, even though this "trade" is much bigger than
    # available cash — selling brings cash IN, doesn't require it upfront.
    p.process_fill(Fill("BTCUSDT", "sell", 100.0, 100.0, 0.0, datetime(2024, 1, 1)))
    assert p.position("BTCUSDT") == -100.0


def test_max_drawdown_hand_calculated():
    """Equity path: 1000 -> 1200 (peak) -> 900 (trough) -> 1100.
    Max drawdown = (1200 - 900) / 1200 = 25%."""
    p = Portfolio(starting_cash=1000.0)
    p.record_equity_snapshot(datetime(2024, 1, 1), {})
    p.cash = 1200
    p.record_equity_snapshot(datetime(2024, 1, 2), {})
    p.cash = 900
    p.record_equity_snapshot(datetime(2024, 1, 3), {})
    p.cash = 1100
    p.record_equity_snapshot(datetime(2024, 1, 4), {})

    assert p.max_drawdown() == pytest.approx(0.25, abs=1e-9)


def test_max_drawdown_is_zero_with_insufficient_history():
    p = Portfolio(starting_cash=1000.0)
    assert p.max_drawdown() == 0.0
    p.record_equity_snapshot(datetime(2024, 1, 1), {})
    assert p.max_drawdown() == 0.0  # only 1 point, no drawdown possible


def test_fill_validates_its_own_fields():
    with pytest.raises(ValueError, match="side must be"):
        Fill("BTCUSDT", "hold", 1.0, 100.0, 0.0, datetime(2024, 1, 1))
    with pytest.raises(ValueError, match="quantity must be positive"):
        Fill("BTCUSDT", "buy", -1.0, 100.0, 0.0, datetime(2024, 1, 1))
    with pytest.raises(ValueError, match="price must be positive"):
        Fill("BTCUSDT", "buy", 1.0, -100.0, 0.0, datetime(2024, 1, 1))
    with pytest.raises(ValueError, match="fee cannot be negative"):
        Fill("BTCUSDT", "buy", 1.0, 100.0, -1.0, datetime(2024, 1, 1))


def test_starting_cash_must_be_positive():
    with pytest.raises(ValueError, match="starting_cash must be positive"):
        Portfolio(starting_cash=0.0)


def test_position_for_unheld_symbol_returns_zero():
    p = Portfolio(starting_cash=1000.0)
    assert p.position("NEVERBOUGHT") == 0.0


def test_multi_symbol_portfolio_tracks_independently():
    p = Portfolio(starting_cash=10_000.0)
    p.process_fill(Fill("BTCUSDT", "buy", 1.0, 100.0, 0.0, datetime(2024, 1, 1)))
    p.process_fill(Fill("ETHUSDT", "buy", 2.0, 50.0, 0.0, datetime(2024, 1, 1)))

    assert p.position("BTCUSDT") == 1.0
    assert p.position("ETHUSDT") == 2.0

    total_equity = p.total_equity({"BTCUSDT": 100.0, "ETHUSDT": 50.0})
    # cash = 10000 - 100 - 100 = 9800; positions = 100 + 100 = 200
    assert total_equity == 9800.0 + 200.0