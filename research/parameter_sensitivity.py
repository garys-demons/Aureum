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

    Captures actual quoted prices (not just action counts), since
    action_counts alone can't distinguish parameter effects for a
    market maker that always quotes both sides.

    Simulates a fill for every signal via record_fill() after the run,
    so inventory-dependent parameters (e.g. inventory_skew_sensitivity)
    have something real to respond to. This is a known simplification
    ("every quote fills") - real fill simulation is Gauri's paper
    exchange; this is sufficient for isolating parameter *sensitivity*,
    not for measuring realistic PnL.
    """
    engine = BacktestEngine(strategy=strategy)
    signals = engine.run(candles)

    action_counts: dict[str, int] = {}
    spreads = []
    buy_prices = []
    sell_prices = []

    for s in signals:
        action_counts[s.action] = action_counts.get(s.action, 0) + 1
        if s.action == "buy" and s.price is not None:
            buy_prices.append(s.price)
        elif s.action == "sell" and s.price is not None:
            sell_prices.append(s.price)

        # Simulate the fill so inventory actually moves, giving
        # skew-dependent parameters something real to respond to.
        if hasattr(strategy, "record_fill") and s.action in ("buy", "sell") and s.quantity is not None:
            strategy.record_fill(s.action, s.quantity)

    paired = min(len(buy_prices), len(sell_prices))
    for i in range(paired):
        spreads.append(sell_prices[i] - buy_prices[i])

    final_inventory = getattr(strategy, "inventory", None)

    return {
        "total_signals": len(signals),
        "action_counts": action_counts,
        "avg_quoted_spread": sum(spreads) / len(spreads) if spreads else None,
        "avg_buy_price": sum(buy_prices) / len(buy_prices) if buy_prices else None,
        "avg_sell_price": sum(sell_prices) / len(sell_prices) if sell_prices else None,
        "final_inventory": final_inventory,
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