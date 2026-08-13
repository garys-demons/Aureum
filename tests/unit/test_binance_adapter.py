"""Tests for BinanceAdapter — includes a real-network check against Binance Testnet."""
import pytest

from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.models import Candle, TickerEvent, TradeEvent


@pytest.mark.asyncio
async def test_stream_market_data_yields_parsed_models():
    """Connects to real Binance Testnet and confirms parsed model instances arrive.

    This hits the real network — if it ever becomes slow/flaky in CI, mark
    it with @pytest.mark.skip and revisit; for Phase 1 solo dev, keeping it
    real is more valuable than mocking too early.

    Now that @kline_1m is subscribed (FR-6), Candle instances can arrive
    here too, not just TickerEvent/TradeEvent.
    """
    adapter = BinanceAdapter(config={})
    received = []

    async for event in adapter.stream_market_data(["BTCUSDT"]):
        received.append(event)
        if len(received) >= 3:
            break

    assert len(received) == 3
    for event in received:
        assert isinstance(event, (TickerEvent, TradeEvent, Candle))
        assert event.symbol == "BTCUSDT"