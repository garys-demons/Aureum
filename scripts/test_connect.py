"""Scratch script: full reconciliation procedure against real Binance Testnet data."""
import asyncio
import websockets
import json

from services.market_data.order_book import fetch_snapshot, reconcile
from services.market_data.parsers import parse_order_book_delta


async def main():
    symbol = "BTCUSDT"
    stream_url = f"wss://stream.testnet.binance.vision/ws/{symbol.lower()}@depth"

    buffered_deltas = []

    async with websockets.connect(stream_url) as ws:
        print("Buffering live deltas...")
        # Buffer a handful of deltas first (simulates "buffer while fetching snapshot")
        for _ in range(5):
            raw = json.loads(await ws.recv())
            # raw stream (not combined) — wrap it to match parser's expected shape
            wrapped = {"stream": f"{symbol.lower()}@depth", "data": raw}
            buffered_deltas.append(parse_order_book_delta(wrapped))

    print("Fetching snapshot...")
    snapshot = await fetch_snapshot(symbol)
    print("Snapshot last_update_id:", snapshot.last_update_id)

    try:
        result = reconcile(snapshot, buffered_deltas)
        print(f"Reconciliation succeeded! {len(result)} deltas applied.")
    except ValueError as e:
        print("Reconciliation failed (expected sometimes with a small buffer):", e)


asyncio.run(main())