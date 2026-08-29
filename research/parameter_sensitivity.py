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
from core.backtest.candle_fill_model import fill_limit_order_candle, Candle as FillCandle
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

    Uses core.backtest.candle_fill_model.fill_limit_order_candle() to
    simulate realistic asymmetric fills - a quote only fills if the
    candle's actual price range touched it, so only one side (or
    neither, or both) may fill per candle. This replaces an earlier
    "every quote fills" simplification, which made inventory always
    cancel to exactly zero and made inventory_skew_sensitivity
    untestable in isolation (see phase5_parameter_sensitivity_findings.md).
    """
    engine = BacktestEngine(strategy=strategy)

    action_counts: dict[str, int] = {}
    spreads = []
    buy_fill_prices = []
    sell_fill_prices = []
    fills_count = 0

    for original_candle in candles:
        signals = engine.run([original_candle])

        fill_candle = FillCandle(
            open=original_candle.open, high=original_candle.high,
            low=original_candle.low, close=original_candle.close,
        )

        for s in signals:
            action_counts[s.action] = action_counts.get(s.action, 0) + 1

            if s.action in ("buy", "sell") and s.price is not None and s.quantity is not None:
                fill = fill_limit_order_candle(fill_candle, s.action, s.quantity, s.price)
                if fill is not None:
                    fill_price, fill_qty = fill
                    fills_count += 1
                    if hasattr(strategy, "record_fill"):
                        strategy.record_fill(s.action, fill_qty)
                    if s.action == "buy":
                        buy_fill_prices.append(fill_price)
                    else:
                        sell_fill_prices.append(fill_price)

    paired = min(len(buy_fill_prices), len(sell_fill_prices))
    for i in range(paired):
        spreads.append(sell_fill_prices[i] - buy_fill_prices[i])

    final_inventory = getattr(strategy, "inventory", None)
    max_abs_inventory = getattr(strategy, "max_abs_inventory", None)

    return {
        "total_signals": sum(action_counts.values()),
        "action_counts": action_counts,
        "fills_count": fills_count,
        "avg_quoted_spread": sum(spreads) / len(spreads) if spreads else None,
        "avg_buy_fill_price": sum(buy_fill_prices) / len(buy_fill_prices) if buy_fill_prices else None,
        "avg_sell_fill_price": sum(sell_fill_prices) / len(sell_fill_prices) if sell_fill_prices else None,
        "final_inventory": final_inventory,
        "max_abs_inventory": max_abs_inventory,
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
    param_grid: e.g. {"base_half_spread": [0.0005, 0.001], "inventory_skew_sensitivity": [0.00001, 0.00002]}
    window_datasets: names of datasets already saved via research.storage,
        e.g. ["adausdt_candles_1m_recent_24h", "adausdt_candles_1m_prior_24h"]
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