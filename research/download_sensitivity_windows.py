"""
Downloads multiple distinct historical windows for Phase 5 parameter
sensitivity analysis. Using several non-overlapping windows (not just
one) is essential to avoid look-ahead bias creeping in through
parameter selection itself - a parameter that only performs well on
one specific window is overfit to that window, not genuinely good.
"""
import asyncio
import time

from services.market_data.historical import fetch_historical_candles, find_candle_gaps, interval_to_ms
from research.storage import save_dataset


async def download_window(symbol: str, interval: str, start_time_ms: int, end_time_ms: int, window_label: str) -> int:
    """Download one window of candles and save it as a distinctly-named dataset."""
    candles = await fetch_historical_candles(
        symbol=symbol, interval=interval,
        start_time_ms=start_time_ms, end_time_ms=end_time_ms,
    )

    if not candles:
        raise ValueError(f"No candles returned for window {window_label}")

    gaps = find_candle_gaps(candles, interval_ms=interval_to_ms(interval))

    import pandas as pd
    df = pd.DataFrame([c.model_dump() for c in candles])

    version = save_dataset(
        f"{symbol.lower()}_candles_{interval}_{window_label}",
        df,
        category="raw",
        source="hansika/sensitivity_windows",
        metadata={
            "symbol": symbol,
            "interval": interval,
            "window_label": window_label,
            "start_time_ms": candles[0].open_time,
            "end_time_ms": candles[-1].close_time,
            "candle_count": len(candles),
            "gaps_found": len(gaps),
        },
    )
    print(f"Window '{window_label}': saved {len(candles)} candles as version {version}")
    return version


async def main():
    symbol = "BTCUSDT"
    interval = "1m"
    now_ms = int(time.time() * 1000)
    one_day_ms = 24 * 60 * 60 * 1000

    # Three distinct, non-overlapping windows - avoids tuning parameters
    # against just one slice of market conditions.
    windows = [
        ("recent_24h", now_ms - (1 * one_day_ms), now_ms),
        ("prior_24h", now_ms - (2 * one_day_ms), now_ms - (1 * one_day_ms)),
        ("prior_48h", now_ms - (4 * one_day_ms), now_ms - (2 * one_day_ms)),
    ]

    for label, start, end in windows:
        await download_window(symbol, interval, start, end, label)


if __name__ == "__main__":
    asyncio.run(main())