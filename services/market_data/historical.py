"""
Historical data downloader - REST-based, for backtesting/feature-pipeline
inputs (Phase 3). Distinct from the live WebSocket pipeline (Phase 1) -
reuses the same Candle/TradeEvent models so downstream code doesn't care
whether data came from live streaming or historical backfill.
"""
import time

import httpx
import structlog

from services.market_data.models import Candle, TradeEvent

logger = structlog.get_logger()

BINANCE_TESTNET_REST_BASE = "https://testnet.binance.vision"
MAX_CANDLES_PER_REQUEST = 1000


async def fetch_historical_candles(
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int,
) -> list[Candle]:
    """
    Fetch all candles for `symbol`/`interval` between start_time_ms and
    end_time_ms (inclusive), handling pagination automatically since
    Binance caps each request at 1000 candles.
    """
    all_candles: list[Candle] = []
    current_start = start_time_ms

    async with httpx.AsyncClient() as client:
        while current_start < end_time_ms:
            url = f"{BINANCE_TESTNET_REST_BASE}/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": MAX_CANDLES_PER_REQUEST,
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            raw_candles = response.json()

            if not raw_candles:
                break  # no more data in range

            for raw in raw_candles:
                all_candles.append(_parse_raw_kline(raw, symbol, interval))

            # A batch smaller than the request limit means Binance has no
            # more data in this range - stop, rather than re-requesting
            # forever (this was a real infinite-loop bug, caught by a test
            # whose mock returns the same fixed batch every call).
            if len(raw_candles) < MAX_CANDLES_PER_REQUEST:
                break

            # Binance kline format: raw[0] = open_time. Next request starts
            # 1ms after the last candle's open_time to avoid re-fetching it.
            last_open_time = raw_candles[-1][0]
            current_start = last_open_time + 1

            logger.info(
                "fetched_candle_batch",
                symbol=symbol,
                interval=interval,
                batch_size=len(raw_candles),
                total_so_far=len(all_candles),
            )

    # Binance can return the still-forming current candle as the last item
    # if end_time_ms is close to (or past) the real current time. Its
    # close_time hasn't actually happened yet, so it must not be labeled
    # closed - treating a still-changing price as final would corrupt
    # anything downstream that assumes closed candles never change
    # (Samarth's Phase 3 review finding).
    if all_candles:
        now_ms = int(time.time() * 1000)
        if all_candles[-1].close_time >= now_ms:
            all_candles[-1] = all_candles[-1].model_copy(update={"is_closed": False})

    return all_candles


def _parse_raw_kline(raw: list, symbol: str, interval: str) -> Candle:
    """
    Convert a raw Binance kline array into a Candle model.

    Raw format: [open_time, open, high, low, close, volume, close_time, ...]
    """
    open_time, open_, high, low, close, volume, close_time = raw[0:7]

    return Candle(
        event_type="kline",
        exchange="binance",
        symbol=symbol,
        event_time=close_time,
        received_time=close_time,
        interval=interval,
        open_time=open_time,
        close_time=close_time,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
        is_closed=True,  # corrected after the fact in fetch_historical_candles if still in-progress
    )


async def fetch_historical_trades(
    symbol: str,
    start_time_ms: int,
    end_time_ms: int,
) -> list[TradeEvent]:
    """
    Fetch all aggregated trades for `symbol` between start_time_ms and
    end_time_ms, handling pagination via Binance's aggTrades endpoint.
    """
    all_trades: list[TradeEvent] = []
    current_start = start_time_ms

    async with httpx.AsyncClient() as client:
        while current_start < end_time_ms:
            url = f"{BINANCE_TESTNET_REST_BASE}/api/v3/aggTrades"
            params = {
                "symbol": symbol,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": MAX_CANDLES_PER_REQUEST,
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            raw_trades = response.json()

            if not raw_trades:
                break

            for raw in raw_trades:
                all_trades.append(_parse_raw_agg_trade(raw, symbol))

            # Same safety fix as fetch_historical_candles: a batch smaller
            # than the limit means there's no more data, stop rather than
            # re-requesting forever.
            if len(raw_trades) < MAX_CANDLES_PER_REQUEST:
                break

            last_trade_time = raw_trades[-1]["T"]
            current_start = last_trade_time + 1

            logger.info(
                "fetched_trade_batch",
                symbol=symbol,
                batch_size=len(raw_trades),
                total_so_far=len(all_trades),
            )

    return all_trades


def _parse_raw_agg_trade(raw: dict, symbol: str) -> TradeEvent:
    """
    Convert a raw Binance aggTrade object into a TradeEvent.

    Raw format: {"a": agg_trade_id, "p": price, "q": quantity, "T": timestamp, "m": buyer_is_maker, ...}
    """
    return TradeEvent(
        event_type="trade",
        exchange="binance",
        symbol=symbol,
        event_time=raw["T"],
        received_time=raw["T"],
        trade_id=raw["a"],
        price=float(raw["p"]),
        quantity=float(raw["q"]),
        buyer_maker=raw["m"],
        trade_time=raw["T"],
    )


def find_candle_gaps(candles: list[Candle], interval_ms: int) -> list[tuple[int, int]]:
    """
    Scan a list of candles (assumed sorted by open_time) and return any
    gaps found - pairs of (expected_next_open_time, actual_open_time)
    where consecutive candles aren't exactly interval_ms apart.

    Duplicate open_time values are skipped, not reported as gaps -
    a repeated candle isn't missing data, it's a separate (low-priority)
    concern (Samarth's Phase 3 review finding).
    """
    gaps = []
    for prev, curr in zip(candles, candles[1:]):
        if curr.open_time == prev.open_time:
            continue  # duplicate, not a gap
        expected_next = prev.open_time + interval_ms
        if curr.open_time != expected_next:
            gaps.append((expected_next, curr.open_time))
    return gaps


INTERVAL_TO_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "1h": 60 * 60_000,
}


def interval_to_ms(interval: str) -> int:
    """Convert a Binance interval string (e.g. '1m', '5m', '1h') to milliseconds."""
    if interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_TO_MS[interval]