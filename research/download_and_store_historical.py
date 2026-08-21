"""
Downloads historical market data (via services.market_data.historical)
and saves it into the versioned research storage (research.storage).

This script is the bridge between the two — it may import from both
services/ and research/, but neither of those may import from each
other or from this script.
"""
import asyncio

import pandas as pd

from services.market_data.historical import (
    fetch_historical_candles,
    fetch_historical_trades,
    find_candle_gaps,
    interval_to_ms,
)
from research.storage import save_dataset


async def download_and_store_candles(
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int,
) -> int:
    """
    Fetch historical candles, check for gaps, and save as a versioned
    dataset. Returns the new version number.
    """
    candles = await fetch_historical_candles(
        symbol=symbol, interval=interval,
        start_time_ms=start_time_ms, end_time_ms=end_time_ms,
    )

    if not candles:
        raise ValueError(f"No candles returned for {symbol} {interval} in given range")

    gaps = find_candle_gaps(candles, interval_ms=interval_to_ms(interval))

    df = pd.DataFrame([c.model_dump() for c in candles])

    version = save_dataset(
        f"{symbol.lower()}_candles_{interval}",
        df,
        category="raw",
        source="hansika/historical_downloader",
        metadata={
            "symbol": symbol,
            "interval": interval,
            "start_time_ms": candles[0].open_time,
            "end_time_ms": candles[-1].close_time,
            "candle_count": len(candles),
            "expected_candle_count": (end_time_ms - start_time_ms) // interval_to_ms(interval),
            "gaps_found": len(gaps),
            "gap_details": gaps,
        },
    )

    return version


async def download_and_store_trades(
    symbol: str,
    start_time_ms: int,
    end_time_ms: int,
) -> int:
    """Fetch historical trades and save as a versioned dataset."""
    trades = await fetch_historical_trades(
        symbol=symbol, start_time_ms=start_time_ms, end_time_ms=end_time_ms,
    )

    if not trades:
        raise ValueError(f"No trades returned for {symbol} in given range")

    df = pd.DataFrame([t.model_dump() for t in trades])

    version = save_dataset(
        f"{symbol.lower()}_trades",
        df,
        category="raw",
        source="hansika/historical_downloader",
        metadata={
            "symbol": symbol,
            "start_time_ms": start_time_ms,
            "end_time_ms": end_time_ms,
            "trade_count": len(trades),
        },
    )

    return version


if __name__ == "__main__":
    import time

    async def main():
        end_time = int(time.time() * 1000)
        start_time = end_time - (24 * 60 * 60 * 1000)

        candle_version = await download_and_store_candles(
            symbol="ADAUSDT", interval="1m",
            start_time_ms=start_time, end_time_ms=end_time,
        )
        print(f"Saved candles as version {candle_version}")

        trade_version = await download_and_store_trades(
            symbol="ADAUSDT",
            start_time_ms=end_time - (10 * 60 * 1000),
            end_time_ms=end_time,
        )
        print(f"Saved trades as version {trade_version}")

    asyncio.run(main())