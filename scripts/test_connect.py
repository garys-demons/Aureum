"""Scratch script: verify the fully unified pipeline (ticker + trade + order book)."""
import asyncio

from services.market_data.adapters.binance import BinanceAdapter


async def main():
    adapter = BinanceAdapter(config={})
    count = 0
    async for event in adapter.stream_market_data(["BTCUSDT"]):
        print(type(event).__name__, "-", event)
        count += 1
        if count >= 20:
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")