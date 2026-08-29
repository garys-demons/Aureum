"""
Downloads multiple distinct historical windows for Phase 5 parameter
sensitivity analysis. Using several non-overlapping windows (not just
one) is essential to avoid look-ahead bias creeping in through
parameter selection itself - a parameter that only performs well on
one specific window is overfit to that window, not genuinely good.

Phase 7 fix: windows were previously computed relative to time.time()
at download time, meaning "recent_24h" silently meant a different
dataset every single run - confirmed with two runs 9 seconds apart
producing different end timestamps (1787993393566 vs 1787993402815).
AI evaluation (Phase 7/8) needs a genuinely reproducible benchmark:
the same window name must always mean the same data. Windows are now
pinned to a fixed reference timestamp, never recomputed from "now".
"""
import asyncio

from services.market_data.historical import fetch_historical_candles, find_candle_gaps, interval_to_ms
from research.storage import save_dataset

# Pinned to 2026-08-27 00:00:00 UTC, verified via
# datetime.datetime(2026, 8, 27, 0, 0, 0, tzinfo=timezone.utc).
# Never recompute this from time.time(). To add a new window later,
# add a new explicitly-named entry (e.g. "benchmark_v2_...") rather
# than changing what an existing name means.
FIXED_REFERENCE_MS = 1787788800000  # 2026-08-27T00:00:00Z, pinned once, verified, never recomputed


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
    symbol = "ADAUSDT"  # matches BaselineMarketMaker's tuned price scale (Phase 5)
    interval = "1m"
    one_day_ms = 24 * 60 * 60 * 1000
    now_ms = FIXED_REFERENCE_MS

    windows = [
        ("recent_24h", now_ms - (1 * one_day_ms), now_ms),
        ("prior_24h", now_ms - (2 * one_day_ms), now_ms - (1 * one_day_ms)),
        ("prior_48h", now_ms - (4 * one_day_ms), now_ms - (2 * one_day_ms)),
    ]

    for label, start, end in windows:
        await download_window(symbol, interval, start, end, label)


if __name__ == "__main__":
    asyncio.run(main())
