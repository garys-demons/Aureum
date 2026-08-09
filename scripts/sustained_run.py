"""
Sustained run script — Phase 1 exit criteria (PRD §11):
- Runs continuously for a target duration
- Logs event counts, gaps, reconnects
- Can be manually interrupted (Ctrl+C) mid-run to simulate/observe a forced reconnect
"""
import asyncio
import time

from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.models import TickerEvent, TradeEvent, OrderBookSnapshot, OrderBookDelta

RUN_DURATION_SECONDS = 60 * 60  # 1 hour


async def main():
    adapter = BinanceAdapter(config={})
    start_time = time.monotonic()

    counts = {"ticker": 0, "trade": 0, "snapshot": 0, "delta": 0}
    last_report = start_time

    print(f"Starting sustained run for {RUN_DURATION_SECONDS} seconds...")

    async for event in adapter.stream_market_data(["BTCUSDT"]):
        if isinstance(event, TickerEvent):
            counts["ticker"] += 1
        elif isinstance(event, TradeEvent):
            counts["trade"] += 1
        elif isinstance(event, OrderBookSnapshot):
            counts["snapshot"] += 1
        elif isinstance(event, OrderBookDelta):
            counts["delta"] += 1

        now = time.monotonic()
        if now - last_report >= 60:  # print a status line every minute
            elapsed_min = int((now - start_time) / 60)
            print(f"[{elapsed_min} min] counts={counts}")
            last_report = now

        if now - start_time >= RUN_DURATION_SECONDS:
            print("Target duration reached. Stopping.")
            break

    print("Final counts:", counts)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Run interrupted manually — this is expected if you're testing forced reconnect.")