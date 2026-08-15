"""
Historical data downloader — REST-based, for backtesting/feature-pipeline
inputs (Phase 3). Distinct from the live WebSocket pipeline (Phase 1) —
reuses the same Candle/TradeEvent models so downstream code doesn't care
whether data came from live streaming or historical backfill.
"""
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
            # more data in this range — stop, rather than re-requesting
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
        is_closed=True,  # historical candles are always fully closed
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