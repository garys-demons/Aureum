# Phase 5 — Parameter Sensitivity Analysis Findings

**Owner:** Hansika
**Strategy tested:** `BaselineMarketMaker` (core/strategy/baseline_market_maker.py)
**Symbol:** ADAUSDT (matches the strategy's tuned price scale)
**Windows tested:** 3 independent, non-overlapping 24-48h windows
(recent_24h, prior_24h, prior_48h) — avoids tuning parameters against
a single dataset
**Fill simulation:** core/backtest/candle_fill_model.py — candle-level
limit-order fill checking (a quote fills if the candle's high/low range
touched it)

---

## Correction (2026-08-24): Earlier "amplification" finding retracted

An earlier version of this document reported that
`inventory_skew_sensitivity` amplifies rather than dampens inventory
drift, based on a run that showed `final_inventory` growing with
sensitivity. **That result has since been traced to a data/reporting
issue in an intermediate run, not a real effect** — the corrected
analysis below (with direct instrumentation) shows something different
and more fundamental. See "Finding 2" for the real, verified result.

---

## Parameters Tested

| Parameter | Values tested |
|---|---|
| `base_half_spread` | 0.0003, 0.0005, 0.001, 0.0015 |
| `inventory_skew_sensitivity` | 0.00001, 0.00002 (default), 0.00005 |

---

## Finding 1: `base_half_spread` — Sound

`avg_quoted_spread` scales correctly as `2 × base_half_spread` under
the candle-level fill model, consistent across all 3 windows.

**Verdict: sound.**

---

## Finding 2: `inventory_skew_sensitivity` — Genuinely Untestable at Candle-Level Fill Granularity (root cause confirmed)

### What was directly verified

`record_fill()` itself is correct — confirmed in isolation:
```python
s = BaselineMarketMaker(symbol='ADAUSDT')
s.record_fill('buy', 100)   # inventory: 0.0 -> 100.0
s.record_fill('sell', 50)   # inventory: 100.0 -> 50.0
```

The sweep runner correctly reuses one strategy instance across an
entire backtest (not recreated per-candle) and correctly calls
`record_fill()` only on actual fills, not on every quote.

### The real finding: buy fills and sell fills happen in matched pairs

Direct instrumentation on `adausdt_candles_1m_recent_24h`
(base_half_spread=0.0003, skew=0.00005):