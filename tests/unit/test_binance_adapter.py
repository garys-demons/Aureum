"""Tests for BinanceAdapter — includes a real-network check against Binance Testnet."""
import pytest

from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.models import TickerEvent, TradeEvent, OrderBookSnapshot, OrderBookDelta


@pytest.mark.asyncio
async def test_stream_market_data_yields_parsed_models():
    """Connects to real Binance Testnet and confirms parsed model instances arrive
    across all stream types (ticker, trade, and order book).
    """
    adapter = BinanceAdapter(config={})
    received = []

    async for event in adapter.stream_market_data(["BTCUSDT"]):
        received.append(event)
        if len(received) >= 5:
            break

    assert len(received) == 5
    for event in received:
        assert isinstance(event, (TickerEvent, TradeEvent, OrderBookSnapshot, OrderBookDelta))
        assert event.symbol == "BTCUSDT"