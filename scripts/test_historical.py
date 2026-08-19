"""Scratch script: download real historical data and check for gaps."""
import asyncio
import time

from services.market_data.historical import (
    fetch_historical_candles,
    fetch_historical_trades,
    find_candle_gaps,
    interval_to_ms,
)


async def main():
    symbol = "BTCUSDT"
    interval = "1m"

    end_time = int(time.time() * 1000)
    start_time = end_time - (24 * 60 * 60 * 1000)  # last 24 hours

    print(f"Downloading {interval} candles for {symbol}...")
    candles = await fetch_historical_candles(
        symbol=symbol, interval=interval,
        start_time_ms=start_time, end_time_ms=end_time,
    )
    print(f"Fetched {len(candles)} candles")
    print(f"Range: {candles[0].open_time} to {candles[-1].close_time}")

    gaps = find_candle_gaps(candles, interval_ms=interval_to_ms(interval))
    print(f"Gaps found: {len(gaps)}")
    for expected, actual in gaps:
        print(f"  Expected candle at {expected}, next actual candle at {actual}")

    print("\nDownloading trades (last 10 minutes, denser data)...")
    trades = await fetch_historical_trades(
        symbol=symbol,
        start_time_ms=end_time - (10 * 60 * 1000),
        end_time_ms=end_time,
    )
    print(f"Fetched {len(trades)} trades")


asyncio.run(main())