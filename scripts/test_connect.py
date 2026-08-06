"""Scratch script: verify the unified, deduplicated event pipeline works live."""
import asyncio

from services.market_data.adapters.binance import BinanceAdapter


async def main():
    adapter = BinanceAdapter(config={})
    count = 0
    async for event in adapter.stream_market_data(["BTCUSDT"]):
        print(type(event).__name__, "-", event)
        count += 1
        if count >= 10:
            break


asyncio.run(main())