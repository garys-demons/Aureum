import pytest
from services.market_data.adapters.binance import BinanceAdapter


def test_binance_adapter_instantiates():
    adapter = BinanceAdapter(config={"symbols": ["BTCUSDT"]})
    assert adapter.config["symbols"] == ["BTCUSDT"]


@pytest.mark.asyncio
async def test_connect_succeeds():
    """Day 3: connect() now actually connects to Binance Testnet."""
    adapter = BinanceAdapter(config={})
    await adapter.connect()
    assert adapter._ws is not None
    await adapter.disconnect()