"""
Sample end-to-end backtest run (Phase 4): loads real historical data
saved via research.storage (Phase 3), runs it through BacktestEngine
against StubStrategy, and prints a summary.

Proves the full chain works together: historical download -> versioned
storage -> chronological event processing -> strategy decisions,
all via the same interfaces used elsewhere in the project.
"""
import pandas as pd

from core.backtest.engine import BacktestEngine
from core.strategy.stub_strategy import StubStrategy
from research.storage import load_dataset
from services.market_data.models import Candle


def dataframe_to_candles(df: pd.DataFrame) -> list[Candle]:
    """Convert a saved candles DataFrame back into Candle model instances."""
    return [Candle(**row) for row in df.to_dict(orient="records")]


def main():
    df = load_dataset("raw", "btcusdt_candles_1m")
    candles = dataframe_to_candles(df)

    print(f"Loaded {len(candles)} candles from storage")

    engine = BacktestEngine(strategy=StubStrategy())
    signals = engine.run(candles)

    print(f"Backtest processed {len(signals)} events")
    print(f"First signal: {signals[0]}")
    print(f"Last signal: {signals[-1]}")

    action_counts = {}
    for s in signals:
        action_counts[s.action] = action_counts.get(s.action, 0) + 1
    print(f"Action breakdown: {action_counts}")


if __name__ == "__main__":
    main()
    