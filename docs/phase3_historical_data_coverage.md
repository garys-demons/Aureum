# Phase 3 - Historical Data Coverage

**Owner:** Hansika
**Status:** Initial coverage run - BTCUSDT, 1m candles + recent trades

---

## Candle Data

| Field | Value |
|---|---|
| Symbol | BTCUSDT |
| Interval | 1m |
| Source | Binance Spot Testnet REST (`/api/v3/klines`) |
| Start (UTC) | 2026-08-14 16:57:00 |
| End (UTC) | 2026-08-15 16:56:59 |
| Start (Unix ms) | 1786726620000 |
| End (Unix ms) | 1786813019999 |
| Candles fetched | 1440 |
| Expected candles (24h / 1m) | 1440 |
| Gaps found | 0 |

**Verification method:** `find_candle_gaps()` checks that every consecutive pair of candles is exactly `interval_ms` apart (60,000ms for 1m). Any deviation is flagged as a gap with the expected vs. actual timestamp.

**Result:** Full, contiguous coverage - 1440/1440 candles present, zero gaps detected across the full 24-hour window.

---

## Trade Tick Data

| Field | Value |
|---|---|
| Symbol | BTCUSDT |
| Source | Binance Spot Testnet REST (`/api/v3/aggTrades`) |
| Window | Last 10 minutes of the same period |
| Trades fetched | 270 |

**Note:** Trade tick data doesn't have a fixed expected interval (trades happen irregularly, driven by market activity, not a clock) - so gap detection doesn't apply the same way as candles. Coverage is verified instead by confirming pagination completed without truncation (batch size < limit reached, per `fetch_historical_trades`'s stopping condition).

---

## Known Limitations

- This run covers only BTCUSDT - other symbols not yet tested.
- Only the 1m interval has been gap-checked; 5m and 1h intervals use the same downloader but haven't been separately verified yet.
- Testnet data availability/history depth may differ from production Binance - not yet compared.

---

## Reproduction

```python
from services.market_data.historical import fetch_historical_candles, find_candle_gaps, interval_to_ms

candles = await fetch_historical_candles(
    symbol="BTCUSDT", interval="1m",
    start_time_ms=<start>, end_time_ms=<end>,
)
gaps = find_candle_gaps(candles, interval_ms=interval_to_ms("1m"))
```

---
*Last updated: 15-08-2026*