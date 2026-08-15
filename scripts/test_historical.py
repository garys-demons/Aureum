"""Scratch script: verify historical candle downloader works against real testnet data."""
import asyncio
import time

from services.market_data.historical import fetch_historical_candles


async def main():
    end_time = int(time.time() * 1000)
    start_time = end_time - (2 * 60 * 60 * 1000)  # last 2 hours

    candles = await fetch_historical_candles(
        symbol="BTCUSDT",
        interval="1m",
        start_time_ms=start_time,
        end_time_ms=end_time,
    )

    print(f"Fetched {len(candles)} candles")
    print("First:", candles[0])
    print("Last:", candles[-1])


asyncio.run(main())