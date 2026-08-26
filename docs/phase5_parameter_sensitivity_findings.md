# Phase 5 - Parameter Sensitivity Analysis Findings

**Owner:** Hansika
**Strategy tested:** `BaselineMarketMaker` (core/strategy/baseline_market_maker.py)
**Symbol:** ADAUSDT (matches the strategy's tuned price scale)
**Windows tested:** 3 independent, non-overlapping 24-48h windows (recent_24h, prior_24h, prior_48h) - avoids tuning parameters against a single dataset
**Fill simulation:** core/backtest/candle_fill_model.py - candle-level limit-order fill checking (a quote fills if the candle's high/low range touched it)

---

## Correction (2026-08-24): Earlier "amplification" finding retracted

An earlier version of this document reported that `inventory_skew_sensitivity` amplifies rather than dampens inventory drift, based on a run that showed `final_inventory` growing with sensitivity. That result has since been traced to a data/reporting issue in an intermediate run, not a real effect - the corrected analysis below (with direct instrumentation) shows something different and more fundamental. See Finding 2 for the real, verified result.

---

## Parameters Tested

| Parameter | Values tested |
|---|---|
| base_half_spread | 0.0003, 0.0005, 0.001, 0.0015 |
| inventory_skew_sensitivity | 0.00001, 0.00002 (default), 0.00005 |

---

## Finding 1: base_half_spread - Sound

avg_quoted_spread scales correctly as 2x base_half_spread under the candle-level fill model, consistent across all 3 windows.

Verdict: sound.

---

## Finding 2: inventory_skew_sensitivity - Genuinely Untestable at Candle-Level Fill Granularity

### What was directly verified

record_fill() itself is correct - confirmed in isolation: a buy of 100 moves inventory from 0.0 to 100.0, a subsequent sell of 50 moves it from 100.0 to 50.0. Works exactly as expected.

The sweep runner correctly reuses one strategy instance across an entire backtest (not recreated per-candle) and correctly calls record_fill() only on actual fills, not on every quote.

### The real finding: buy fills and sell fills happen in matched pairs

Direct instrumentation on adausdt_candles_1m_recent_24h (base_half_spread=0.0003, skew=0.00005) showed buy_fills=184 and sell_fills=184 - an exact match, resulting in final inventory of exactly 0.0.

This exact-match pattern held across every tested parameter combination and window.

Root cause: candle_fill_model.py checks each side of the quote independently against that single candle's high/low range. Because BaselineMarketMaker quotes symmetrically around fair price (bid and ask equidistant from it), a candle volatile enough to touch one side is, at 1-minute granularity, very often volatile enough to touch the other side too - so both legs tend to fill together, almost every time, keeping inventory pinned near zero regardless of inventory_skew_sensitivity's value.

This matches candle_fill_model.py's own documented limitation: limit fills use the candle's high/low as a proxy for whether price traded there, which is coarser than tick-level reality. A tick-level or order-book-level fill model would show price touching bid and ask at genuinely different moments, allowing realistic one-sided fills and real inventory accumulation. Candle-level granularity cannot represent that.

Verdict: inventory_skew_sensitivity cannot be meaningfully sensitivity-tested with the current candle-level fill model. This is not a strategy bug - compute_skewed_quotes is mathematically correct as a dampener on direct code review. It is a limitation of the fill model's granularity, which is explicitly documented as an approximation, not a realistic-fill claim.

---

## Look-Ahead-Bias-via-Parameter-Selection Check

No parameter was selected based on single-window performance. base_half_spread behaves consistently across all 3 windows. inventory_skew_sensitivity could not be evaluated at all under this fill model (see Finding 2) - flagged as a limitation rather than silently reported as "no effect," or, as in an earlier draft of this document, misreported as an effect that further investigation showed was not real.

---

## Recommendation

base_half_spread = 0.001 (retuned default): confirmed sound.

inventory_skew_sensitivity: genuinely untestable with the current candle-level fill model. Recommend re-testing once a tick-level or order-book-level fill simulation exists (e.g. Gauri's paper exchange running against real order-book replay data, per Phase 4/2 infra), which can produce the asymmetric, non-simultaneous fills needed to actually exercise this parameter.

## Reproduction

Run: python -m research.download_sensitivity_windows, then python -m research.run_baseline_sensitivity

Full raw results: docs/phase5_parameter_sensitivity_results.csv