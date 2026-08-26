"""
Validates the ExtremeVolatilityMonitor threshold (Phase 6) against real
historical data — checks how often a given threshold would have fired,
so it's tuned against evidence rather than guessed.
"""
from core.persistence.volatility_anomaly import ExtremeVolatilityMonitor
from research.parameter_sensitivity import load_window


def count_triggers(window_dataset: str, window_seconds: int, max_pct_move: float) -> dict:
    candles = load_window(window_dataset)
    monitor = ExtremeVolatilityMonitor(window_seconds=window_seconds, max_pct_move=max_pct_move)

    trigger_count = 0
    for candle in candles:
        # Use each candle's close time and close price as one observation
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(candle.close_time / 1000, tz=timezone.utc)
        if monitor.observe(candle.symbol, candle.close, timestamp=ts):
            trigger_count += 1

    return {
        "window": window_dataset,
        "total_candles": len(candles),
        "trigger_count": trigger_count,
        "trigger_rate_pct": round(trigger_count / len(candles) * 100, 2) if candles else 0,
    }


def main():
    windows = [
        "adausdt_candles_1m_recent_24h",
        "adausdt_candles_1m_prior_24h",
        "adausdt_candles_1m_prior_48h",
    ]

    # Test a few candidate thresholds to see which is reasonable
    for window_seconds in [30, 60]:
        for max_pct_move in [0.01, 0.02, 0.03]:
            print(f"\n=== max_pct_move = {max_pct_move}, window_seconds = {window_seconds} ===")
            for w in windows:
                result = count_triggers(w, window_seconds=window_seconds, max_pct_move=max_pct_move)
                print(f"  {result['window']}: {result['trigger_count']}/{result['total_candles']} candles triggered ({result['trigger_rate_pct']}%)")
            print(f"  {result['window']}: {result['trigger_count']}/{result['total_candles']} candles triggered ({result['trigger_rate_pct']}%)")


if __name__ == "__main__":
    main()