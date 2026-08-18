"""
Tests for the feature engine. Every expected value is calculated by hand
first (see comments) — same standard as Phase 2's microstructure tests.
"""
import math
from services.market_data.order_book import OrderBook
from core.features.feature_engine import (
    simple_returns, log_returns, rolling_volatility, rsi,
    historical_spread, historical_order_book_imbalance,
)


def test_simple_returns_hand_calculated():
    prices = [100.0, 105.0, 103.0]
    # (105-100)/100 = 0.05
    # (103-105)/105 = -2/105 = -0.019047619...
    expected = [0.05, -2 / 105]
    result = simple_returns(prices)
    assert result == expected


def test_simple_returns_empty_when_fewer_than_2_prices():
    assert simple_returns([100.0]) == []
    assert simple_returns([]) == []


def test_simple_returns_length_is_one_less_than_input():
    prices = [100.0, 101.0, 102.0, 103.0]
    assert len(simple_returns(prices)) == len(prices) - 1


def test_log_returns_hand_calculated():
    prices = [100.0, 105.0, 103.0]
    # ln(105/100) = ln(1.05)
    # ln(103/105) = ln(0.980952...)
    expected = [math.log(105 / 100), math.log(103 / 105)]
    result = log_returns(prices)
    assert result == expected


def test_log_returns_empty_when_fewer_than_2_prices():
    assert log_returns([100.0]) == []
    assert log_returns([]) == []


def test_log_returns_zero_when_price_unchanged():
    # ln(1) = 0 — price staying flat should give exactly zero return
    prices = [100.0, 100.0]
    assert log_returns(prices) == [0.0]

def test_rolling_volatility_hand_calculated():
    returns = [0.01, -0.02, 0.03, 0.01]
    # window 2, first chunk: [0.01, -0.02]
    #   mean = (0.01 + -0.02) / 2 = -0.005
    #   squared diffs = [(0.01 - -0.005)^2, (-0.02 - -0.005)^2] = [0.000225, 0.000225]
    #   variance = (0.000225 + 0.000225) / 1 = 0.00045
    #   std dev = 0.00045 ** 0.5 = 0.021213203435596427
    result = rolling_volatility(returns, window=2)
    assert result[0] == 0.00045 ** 0.5


def test_rolling_volatility_output_length():
    returns = [0.01, -0.02, 0.03, 0.01, 0.02]
    # 5 returns, window 3 -> 5 - 3 + 1 = 3 output values
    result = rolling_volatility(returns, window=3)
    assert len(result) == 3


def test_rolling_volatility_zero_when_returns_constant():
    # identical returns -> zero spread -> zero volatility
    returns = [0.01, 0.01, 0.01, 0.01]
    result = rolling_volatility(returns, window=2)
    assert all(v == 0.0 for v in result)


def test_rolling_volatility_empty_when_fewer_than_window():
    returns = [0.01, 0.02]
    result = rolling_volatility(returns, window=5)
    assert result == []


def test_rolling_volatility_raises_on_window_too_small():
    import pytest
    with pytest.raises(ValueError):
        rolling_volatility([0.01, 0.02, 0.03], window=1)

def test_rolling_volatility_alignment_is_window_minus_one():
    """
    Proves result[0] corresponds to index (window - 1) in the returns
    list, not index 0 — locks in the alignment documented in the
    docstring so a future refactor can't silently break it.
    """
    returns = [0.01, -0.02, 0.03, 0.01, 0.02]
    window = 3
    result = rolling_volatility(returns, window)

    # result[0] should be the std dev of returns[0:3] — i.e. "as of" 
    # returns[window - 1] = returns[2], not returns[0]
    manual_first_chunk = returns[0:window]
    mean = sum(manual_first_chunk) / window
    variance = sum((r - mean) ** 2 for r in manual_first_chunk) / (window - 1)
    expected_first_value = variance ** 0.5

    assert result[0] == expected_first_value
    # explicitly documenting: this value represents index (window - 1) = 2

def test_rsi_hand_calculated():
    # prices -> changes: [1, 1, -1, 2, -1] (window = 5, all changes used)
    prices = [100, 101, 102, 101, 103, 102]
    # changes: 101-100=1, 102-101=1, 101-102=-1, 103-101=2, 102-103=-1
    # gains = [1, 1, 2] -> sum=4, avg_gain = 4/5 = 0.8
    # losses = [1, 1] -> sum=2, avg_loss = 2/5 = 0.4
    # RS = 0.8 / 0.4 = 2.0
    # RSI = 100 - (100 / (1 + 2.0)) = 100 - 33.333... = 66.666...
    result = rsi(prices, window=5)
    assert result[0] == 100 - (100 / 3)


def test_rsi_100_when_no_losses():
    prices = [100, 101, 102, 103, 104, 105]  # strictly increasing
    result = rsi(prices, window=5)
    assert result[0] == 100.0


def test_rsi_output_length():
    prices = [100, 101, 102, 101, 103, 102, 104]  # 6 changes
    result = rsi(prices, window=5)
    # 6 changes, window 5 -> 6 - 5 + 1 = 2 values
    assert len(result) == 2


def test_rsi_empty_when_fewer_changes_than_window():
    prices = [100, 101, 102]  # only 2 changes
    result = rsi(prices, window=5)
    assert result == []


def test_rsi_raises_on_invalid_window():
    import pytest
    with pytest.raises(ValueError):
        rsi([100, 101, 102], window=0)

def test_rsi_alignment_corresponds_to_price_index_window():
    """
    Proves result[0] corresponds to price index `window` (not window - 1,
    since changes are offset by 1 from prices) — locks in the alignment
    documented in the docstring so a future refactor can't silently break it.
    """
    prices = [100, 101, 102, 101, 103, 102]
    window = 5
    result = rsi(prices, window)

    # result[0] should be computed from changes[0:5], i.e. prices[0:6] —
    # representing RSI "as of" price index 5 (window), not index 0
    manual_changes = [prices[i] - prices[i - 1] for i in range(1, 6)]
    manual_gains = [c for c in manual_changes if c > 0]
    manual_losses = [-c for c in manual_changes if c < 0]
    avg_gain = sum(manual_gains) / window
    avg_loss = sum(manual_losses) / window
    expected_first_value = 100 - (100 / (1 + avg_gain / avg_loss))

    assert result[0] == expected_first_value
    # explicitly documenting: this value represents price index window = 5

def _make_book(bids: dict, asks: dict) -> OrderBook:
    book = OrderBook(symbol="BTCUSDT")
    book.bids = bids
    book.asks = asks
    return book


def test_historical_spread_hand_calculated():
    books = [
        _make_book({100.0: 5.0}, {101.0: 5.0}),  # spread = 1
        _make_book({102.0: 5.0}, {105.0: 5.0}),  # spread = 3
    ]
    result = historical_spread(books)
    assert result == [1.0, 3.0]


def test_historical_spread_none_when_one_side_empty():
    books = [_make_book({}, {101.0: 5.0})]
    result = historical_spread(books)
    assert result == [None]


def test_historical_spread_preserves_length_and_order():
    books = [
        _make_book({100.0: 1.0}, {101.0: 1.0}),
        _make_book({}, {}),
        _make_book({50.0: 1.0}, {52.0: 1.0}),
    ]
    result = historical_spread(books)
    assert len(result) == 3
    assert result[1] is None


def test_historical_imbalance_hand_calculated():
    # book 1: bid qty 10, ask qty 10 -> imbalance = 10/20 = 0.5
    # book 2: bid qty 15, ask qty 5  -> imbalance = 15/20 = 0.75
    books = [
        _make_book({100.0: 10.0}, {101.0: 10.0}),
        _make_book({100.0: 15.0}, {101.0: 5.0}),
    ]
    result = historical_order_book_imbalance(books)
    assert result == [0.5, 0.75]


def test_historical_imbalance_none_when_empty_book():
    books = [_make_book({}, {})]
    result = historical_order_book_imbalance(books)
    assert result == [None]

