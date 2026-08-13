"""
FR-12 isolation test (Phase 2): proves that force-disconnecting ONLY the
order book stream does not interrupt ticker/trade, and that the order
book independently recovers via full reconciliation. This directly
observes per-stream independence, closing the gap noted in Phase 1
(where only a full-network disconnect was tested).
"""
import asyncio

import pytest

from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.models import TickerEvent, TradeEvent, OrderBookSnapshot, OrderBookDelta


@pytest.mark.asyncio
async def test_order_book_disconnect_does_not_interrupt_ticker_trade():
    """
    Force-disconnects only the order book stream mid-run and confirms:
    1. Ticker/trade events continue arriving throughout (no interruption)
    2. The order book stream independently reconnects and fully
       reconciles again (a second OrderBookSnapshot arrives)
    """
    adapter = BinanceAdapter(config={})
    counts = {"ticker": 0, "trade": 0, "snapshot": 0, "delta": 0}

    async def consume():
        async for event in adapter.stream_market_data(["BTCUSDT"]):
            if isinstance(event, TickerEvent):
                counts["ticker"] += 1
            elif isinstance(event, TradeEvent):
                counts["trade"] += 1
            elif isinstance(event, OrderBookSnapshot):
                counts["snapshot"] += 1
            elif isinstance(event, OrderBookDelta):
                counts["delta"] += 1

    task = asyncio.create_task(consume())

    try:
        # Let the order book reach "live" state (first snapshot received)
        await asyncio.sleep(15)
        assert counts["snapshot"] >= 1, "Order book never reached live state before test could proceed"

        ticker_before = counts["ticker"]
        trade_before = counts["trade"]
        snapshot_before = counts["snapshot"]

        await adapter._force_disconnect("order_book_BTCUSDT")

        # Give it time to notice, reconnect, and fully re-reconcile
        await asyncio.sleep(20)

        # Ticker/trade must have kept flowing — proves isolation (FR-12)
        assert counts["ticker"] > ticker_before, "Ticker stream stopped after order book disconnect — isolation failed"
        assert counts["trade"] > trade_before, "Trade stream stopped after order book disconnect — isolation failed"

        # Order book must have fully recovered — a second snapshot proves
        # full reconciliation re-ran, not just a resubscribe
        assert counts["snapshot"] > snapshot_before, "Order book never recovered after forced disconnect"

    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)