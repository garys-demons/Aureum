"""Scratch script: verify BinanceAdapter.stream_market_data() works end-to-end."""
import asyncio

from services.market_data.adapters.binance import BinanceAdapter


async def main():
    adapter = BinanceAdapter(config={})
    count = 0
    async for event in adapter.stream_market_data(["BTCUSDT"]):
        print(event)
        count += 1
        if count >= 5:  # just grab 5 messages, then stop, so it doesn't run forever
            break


asyncio.run(main())