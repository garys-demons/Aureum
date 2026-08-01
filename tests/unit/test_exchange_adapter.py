import pytest
from services.market_data.adapters.binance import BinanceAdapter


def test_binance_adapter_instantiates():
    adapter = BinanceAdapter(config={"symbols": ["BTCUSDT"]})
    assert adapter.config["symbols"] == ["BTCUSDT"]


@pytest.mark.asyncio
async def test_connect_not_yet_implemented():
    # Day 1: interface exists, implementation lands Day 3.
    adapter = BinanceAdapter(config={})
    with pytest.raises(NotImplementedError):
        await adapter.connect()
