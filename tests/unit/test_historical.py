"""Unit tests for historical candle downloader (Phase 3)."""
import time
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
    
from services.market_data.historical import fetch_historical_trades, _parse_raw_agg_trade
from services.market_data.models import TradeEvent


def sample_raw_agg_trade(trade_id=1000, timestamp=1700000000000):
    """A realistic fake Binance aggTrade object."""
    return {
        "a": trade_id,
        "p": "50000.50",
        "q": "0.01",
        "f": 100,
        "l": 100,
        "T": timestamp,
        "m": True,
        "M": True,
    }


def test_parse_raw_agg_trade_returns_trade_event():
    raw = sample_raw_agg_trade()
    trade = _parse_raw_agg_trade(raw, symbol="BTCUSDT")

    assert isinstance(trade, TradeEvent)
    assert trade.symbol == "BTCUSDT"
    assert trade.trade_id == 1000
    assert trade.price == 50000.50
    assert trade.buyer_maker is True


@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_trades_single_batch():
    """A date range small enough for one request should return all trades, no pagination needed."""
    raw_trades = [
        sample_raw_agg_trade(trade_id=1000 + i, timestamp=1700000000000 + i * 1000)
        for i in range(5)
    ]

    respx.get("https://testnet.binance.vision/api/v3/aggTrades").mock(
        return_value=httpx.Response(200, json=raw_trades)
    )

    trades = await fetch_historical_trades(
        symbol="BTCUSDT",
        start_time_ms=1700000000000,
        end_time_ms=1700000010000,
    )

    assert len(trades) == 5
    assert all(isinstance(t, TradeEvent) for t in trades)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_trades_paginates_correctly():
    """A full first batch should trigger a second request; a smaller final batch should stop the loop."""
    from services.market_data.historical import MAX_CANDLES_PER_REQUEST

    batch_1 = [
        sample_raw_agg_trade(trade_id=1000 + i, timestamp=1700000000000 + i * 1000)
        for i in range(MAX_CANDLES_PER_REQUEST)
    ]
    batch_2 = [
        sample_raw_agg_trade(trade_id=1000 + MAX_CANDLES_PER_REQUEST + i, timestamp=1700000000000 + (MAX_CANDLES_PER_REQUEST + i) * 1000)
        for i in range(3)
    ]

    route = respx.get("https://testnet.binance.vision/api/v3/aggTrades")
    route.side_effect = [
        httpx.Response(200, json=batch_1),
        httpx.Response(200, json=batch_2),
    ]

    trades = await fetch_historical_trades(
        symbol="BTCUSDT",
        start_time_ms=1700000000000,
        end_time_ms=1700000000000 + (MAX_CANDLES_PER_REQUEST + 10) * 1000,
    )

    assert len(trades) == MAX_CANDLES_PER_REQUEST + 3
    assert route.call_count == 2
    
from services.market_data.historical import find_candle_gaps, interval_to_ms


def make_test_candle(open_time: int) -> Candle:
    return Candle(
        event_type="kline", exchange="binance", symbol="BTCUSDT",
        event_time=open_time, received_time=open_time,
        interval="1m", open_time=open_time, close_time=open_time + 59999,
        open=100, high=100, low=100, close=100, volume=1, is_closed=True,
    )


def test_find_candle_gaps_none_when_contiguous():
    candles = [make_test_candle(1700000000000 + i * 60000) for i in range(5)]
    gaps = find_candle_gaps(candles, interval_ms=60000)
    assert gaps == []


def test_find_candle_gaps_detects_single_gap():
    candles = [
        make_test_candle(1700000000000),
        make_test_candle(1700000060000),
        # gap here — skips straight to +3 minutes instead of +2
        make_test_candle(1700000240000),
    ]
    gaps = find_candle_gaps(candles, interval_ms=60000)
    assert len(gaps) == 1
    assert gaps[0] == (1700000120000, 1700000240000)


def test_interval_to_ms_known_values():
    assert interval_to_ms("1m") == 60000
    assert interval_to_ms("5m") == 300000
    assert interval_to_ms("1h") == 3600000


def test_interval_to_ms_unknown_raises():
    with pytest.raises(ValueError):
        interval_to_ms("3d")
        
@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_candles_marks_in_progress_candle_not_closed():
    """If the last candle's close_time hasn't happened yet in real time,
    it must be marked is_closed=False, not hardcoded True."""
    now_ms = int(time.time() * 1000)
    in_progress = sample_raw_kline(open_time=now_ms - 30000)
    in_progress[6] = now_ms + 30000  # close_time in the future

    respx.get("https://testnet.binance.vision/api/v3/klines").mock(
        return_value=httpx.Response(200, json=[in_progress])
    )

    candles = await fetch_historical_candles(
        symbol="BTCUSDT", interval="1m",
        start_time_ms=now_ms - 60000, end_time_ms=now_ms + 60000,
    )

    assert candles[-1].is_closed is False


@pytest.mark.asyncio
@respx.mock
async def test_fetch_historical_candles_keeps_past_candle_closed():
    """A candle whose close_time is genuinely in the past should stay is_closed=True."""
    raw = sample_raw_kline(open_time=1700000000000)  # far in the past

    respx.get("https://testnet.binance.vision/api/v3/klines").mock(
        return_value=httpx.Response(200, json=[raw])
    )

    candles = await fetch_historical_candles(
        symbol="BTCUSDT", interval="1m",
        start_time_ms=1700000000000, end_time_ms=1700000060000,
    )

    assert candles[-1].is_closed is True


def test_find_candle_gaps_does_not_misreport_duplicate_as_gap():
    """A duplicate open_time is not a gap - must not be flagged as one."""
    candles = [
        make_test_candle(1700000000000),
        make_test_candle(1700000000000),  # exact duplicate
    ]
    gaps = find_candle_gaps(candles, interval_ms=60000)
    assert gaps == []