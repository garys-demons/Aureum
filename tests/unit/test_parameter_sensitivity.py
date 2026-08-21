"""Unit tests for the parameter sensitivity sweep runner (Phase 5)."""
from research.parameter_sensitivity import run_single_backtest, run_parameter_sweep
from core.strategy.stub_strategy import StubStrategy
from services.market_data.models import Candle


def make_candle(open_time: int, close: float = 100) -> Candle:
    return Candle(
        event_type="kline", exchange="binance", symbol="BTCUSDT",
        event_time=open_time, received_time=open_time,
        interval="1m", open_time=open_time, close_time=open_time + 59999,
        open=close, high=close, low=close, close=close, volume=1,
        is_closed=True,
    )


def test_run_single_backtest_returns_summary_stats():
    candles = [make_candle(1700000000000 + i * 60000) for i in range(5)]
    stats = run_single_backtest(StubStrategy(), candles)

    assert stats["total_signals"] == 5
    assert stats["action_counts"] == {"hold": 5}


def test_run_parameter_sweep_covers_every_combination(monkeypatch):
    """Every (param combo x window) pair should produce exactly one result row."""
    candles = [make_candle(1700000000000 + i * 60000) for i in range(3)]

    def fake_load_window(name):
        return candles

    monkeypatch.setattr("research.parameter_sensitivity.load_window", fake_load_window)

    results = run_parameter_sweep(
        strategy_factory=lambda **params: StubStrategy(),
        param_grid={"a": [1, 2], "b": [10, 20]},
        window_datasets=["window_x", "window_y"],
    )

    # 2 values of 'a' x 2 values of 'b' x 2 windows = 8 rows
    assert len(results) == 8
    assert set(results["window"]) == {"window_x", "window_y"}
    assert set(results["a"]) == {1, 2}
    assert set(results["b"]) == {10, 20}


def test_run_parameter_sweep_passes_correct_params_to_factory(monkeypatch):
    """Confirms the factory actually receives the swept parameter values, not placeholders."""
    candles = [make_candle(1700000000000)]
    received_params = []

    def fake_load_window(name):
        return candles

    monkeypatch.setattr("research.parameter_sensitivity.load_window", fake_load_window)

    def tracking_factory(**params):
        received_params.append(params)
        return StubStrategy()

    run_parameter_sweep(
        strategy_factory=tracking_factory,
        param_grid={"spread_width": [0.001, 0.005]},
        window_datasets=["window_x"],
    )

    assert {"spread_width": 0.001} in received_params
    assert {"spread_width": 0.005} in received_params