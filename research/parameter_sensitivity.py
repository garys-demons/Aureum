"""
Parameter sensitivity analysis (Phase 5) — runs a strategy across a
grid of parameter combinations AND multiple historical windows, to
check whether it behaves sensibly across conditions rather than being
overfit to one specific dataset.

Look-ahead-bias note: a parameter that only performs well on ONE
window is a red flag, not a recommendation — this module deliberately
reports per-window results side by side rather than picking a single
"best" parameter from one dataset, so overfitting-via-parameter-choice
is visible rather than hidden.
"""
import itertools
from typing import Any, Callable

import pandas as pd

from core.backtest.engine import BacktestEngine
from core.strategy.base import StrategyInterface
from research.storage import load_dataset
from services.market_data.models import Candle


def dataframe_to_candles(df: pd.DataFrame) -> list[Candle]:
    """Convert a saved candles DataFrame back into Candle model instances."""
    return [Candle(**row) for row in df.to_dict(orient="records")]


def load_window(dataset_name: str) -> list[Candle]:
    """Load one historical window (previously saved via research.storage)."""
    df = load_dataset("raw", dataset_name)
    return dataframe_to_candles(df)


def run_single_backtest(strategy: StrategyInterface, candles: list[Candle]) -> dict:
    """
    Run one backtest and return summary statistics for a single
    (parameter combination, window) pair.
    """
    engine = BacktestEngine(strategy=strategy)
    signals = engine.run(candles)

    action_counts: dict[str, int] = {}
    for s in signals:
        action_counts[s.action] = action_counts.get(s.action, 0) + 1

    return {
        "total_signals": len(signals),
        "action_counts": action_counts,
    }


def run_parameter_sweep(
    strategy_factory: Callable[..., StrategyInterface],
    param_grid: dict[str, list[Any]],
    window_datasets: list[str],
) -> pd.DataFrame:
    """
    Run every combination of parameters in `param_grid`, across every
    dataset in `window_datasets`, and return a results table.

    strategy_factory: a function that takes the swept parameters as
        keyword arguments and returns a fresh StrategyInterface instance
        (e.g. lambda **params: InventoryAwareMarketMaker(**params)).
    param_grid: e.g. {"spread_width": [0.001, 0.005, 0.01], "skew_factor": [0.1, 0.5]}
    window_datasets: names of datasets already saved via research.storage,
        e.g. ["btcusdt_candles_1m_recent_24h", "btcusdt_candles_1m_prior_24h"]
    """
    param_names = list(param_grid.keys())
    param_combinations = list(itertools.product(*param_grid.values()))

    windows = {name: load_window(name) for name in window_datasets}

    results = []
    for combo in param_combinations:
        params = dict(zip(param_names, combo))

        for window_name, candles in windows.items():
            strategy = strategy_factory(**params)
            stats = run_single_backtest(strategy, candles)

            row = {**params, "window": window_name, **stats}
            results.append(row)

    return pd.DataFrame(results)