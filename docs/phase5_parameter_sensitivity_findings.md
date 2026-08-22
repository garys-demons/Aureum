# Phase 5 — Parameter Sensitivity Analysis Findings

**Owner:** Hansika
**Strategy tested:** `BaselineMarketMaker` (core/strategy/baseline_market_maker.py)
**Symbol:** ADAUSDT (matches the strategy's tuned price scale)
**Windows tested:** 3 independent, non-overlapping 24-48h windows
(recent_24h, prior_24h, prior_48h) — avoids tuning parameters against
a single dataset

---

## Parameters Tested

| Parameter | Values tested | Default |
|---|---|---|
| `base_half_spread` | 0.0003, 0.0005, 0.001 | 0.0005 |
| `inventory_skew_sensitivity` | 0.00001, 0.00002, 0.00005 | 0.00002 |

---

## Finding 1: `base_half_spread` — Works Correctly, Consistent Across All Windows

`avg_quoted_spread` scales exactly as `2 × base_half_spread` in every
single test case (0.0006 / 0.0010 / 0.0020 for the three tested
values), consistently across all 3 windows. This confirms the quoting
math (`compute_skewed_quotes`) behaves exactly as documented.

**Verdict: sound. No adjustment needed.**

---

## Finding 2: `inventory_skew_sensitivity` — Cannot Be Meaningfully Tested With Current Harness

`final_inventory` was `0.0` in every single test run, regardless of
the `inventory_skew_sensitivity` value tested. Buy and sell average
prices showed zero variation across all three tested values.

**Root cause:** `BaselineMarketMaker.decide()` always returns exactly
one buy and one sell Signal per event, both with the same fixed
`order_quantity`. When simulating "every quote fills" (a reasonable
simplification for isolating parameter effects), the buy and sell
exactly cancel every time (+100, -100 = 0), so inventory can never
move away from zero. Since `skew = -inventory × inventory_skew_sensitivity`,
a permanently-zero inventory means the skew parameter has literally
nothing to act on, regardless of its value.

**This is not a flaw in the strategy's design** — `record_fill()` is
explicitly documented as expecting realistic, asymmetric fills driven
by actual market conditions (only the bid fills sometimes, only the
ask other times), which requires Gauri's real paper exchange fill
simulation, not a simplified "everything fills" assumption.

**Verdict: genuinely untestable in isolation with this harness.**
Meaningful inventory-skew sensitivity testing requires running the
full pipeline (strategy → paper exchange → portfolio) with realistic
fill simulation, not a standalone parameter sweep. Recommend re-running
this specific parameter's sensitivity analysis once Gauri's
strategy-to-execution wiring (her Phase 5 task) is complete and can
produce realistic, asymmetric fills.

---

## Look-Ahead-Bias-via-Parameter-Selection Check

No parameter value was selected based on outperforming on a single
window — `base_half_spread`'s consistent behavior held across all 3
independent windows, and `inventory_skew_sensitivity` couldn't be
evaluated at all (see Finding 2), so there was no risk of cherry-picking
a window-specific "winning" value for either parameter in this round.

---

## Recommendation

- `base_half_spread` default (0.0005) is reasonable and behaves
  predictably; no change needed based on this analysis.
- `inventory_skew_sensitivity` requires re-testing with real fill
  simulation before any recommendation can be made — flagging as a
  known gap, not silently reporting a false "no effect" conclusion.

## Reproduction