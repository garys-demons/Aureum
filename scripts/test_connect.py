"""Scratch script: verify raw Binance JSON correctly converts into TickerEvent."""
import asyncio

from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.parsers import parse_ticker_event


async def main():
    adapter = BinanceAdapter(config={})
    async for raw_event in adapter.stream_market_data(["BTCUSDT"]):
        ticker = parse_ticker_event(raw_event)
        print(ticker)
        break


asyncio.run(main())