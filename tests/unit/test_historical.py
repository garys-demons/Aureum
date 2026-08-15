"""Unit tests for historical candle downloader (Phase 3)."""
import httpx
import pytest
import respx

from services.market_data.historical import fetch_historical_candles, _parse_raw_kline
from services.market_data.models import Candle


def sample_raw_kline(open_time=1700000000000):
    """A realistic fake Binance kline array."""
    return [
        open_time,          # open_time
        "50000.00",         # open
        "50100.00",         # high
        "49900.00",         # low
        "50050.00",         # close
        "12.5",              # volume
        open_time + 59999,  # close_time
        "625000.00",         # quote asset volume (unused)
        100,                 # number of trades (unused)
        "6.0",                # taker buy base volume (unused)
        "300000.00",          # taker buy quote volume (unused)
        "0",                   # unused
    ]


def test_parse_raw_kline_returns_candle():
    raw = sample_raw_kline()
    candle = _parse_raw_kline(raw, symbol="BTCUSDT", interval="1m")

    assert isinstance(candle, Candle)
    assert candle.symbol == "BTCUSDT"
    assert candle.open == 50000.0
    assert candle.close == 50050.0
    assert candle.is_closed is True


@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_candles_single_batch():
    """A date range small enough for one request should return all candles, no pagination needed."""
    raw_candles = [sample_raw_kline(open_time=1700000000000 + i * 60000) for i in range(5)]

    respx.get("https://testnet.binance.vision/api/v3/klines").mock(
        return_value=httpx.Response(200, json=raw_candles)
    )

    candles = await fetch_historical_candles(
        symbol="BTCUSDT",
        interval="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700000300000,
    )

    assert len(candles) == 5
    assert all(isinstance(c, Candle) for c in candles)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_candles_paginates_correctly():
    """A full first batch (hits the limit) should trigger a second request; a smaller final batch should stop the loop."""
    from services.market_data.historical import MAX_CANDLES_PER_REQUEST

    # Batch 1: exactly at the limit -> signals "there might be more"
    batch_1 = [
        sample_raw_kline(open_time=1700000000000 + i * 60000)
        for i in range(MAX_CANDLES_PER_REQUEST)
    ]
    # Batch 2: smaller than the limit -> signals "this is the last one"
    batch_2 = [sample_raw_kline(open_time=1700000000000 + (MAX_CANDLES_PER_REQUEST + i) * 60000) for i in range(2)]

    route = respx.get("https://testnet.binance.vision/api/v3/klines")
    route.side_effect = [
        httpx.Response(200, json=batch_1),
        httpx.Response(200, json=batch_2),
    ]

    candles = await fetch_historical_candles(
        symbol="BTCUSDT",
        interval="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700000000000 + (MAX_CANDLES_PER_REQUEST + 10) * 60000,
    )

    assert len(candles) == MAX_CANDLES_PER_REQUEST + 2
    assert route.call_count == 2