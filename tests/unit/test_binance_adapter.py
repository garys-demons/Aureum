"""Tests for BinanceAdapter — includes a real-network check against Binance Testnet."""
import pytest

from services.market_data.adapters.binance import BinanceAdapter


@pytest.mark.asyncio
async def test_stream_market_data_receives_real_events():
    """Connects to real Binance Testnet and confirms at least one valid event arrives.

    This hits the real network — if it ever becomes slow/flaky in CI, mark
    it with @pytest.mark.skip and revisit; for Phase 1 solo dev, keeping it
    real is more valuable than mocking too early.
    """
    adapter = BinanceAdapter(config={})
    received = []

    async for event in adapter.stream_market_data(["BTCUSDT"]):
        received.append(event)
        break

    assert len(received) == 1
    assert received[0]["data"]["s"] == "BTCUSDT"