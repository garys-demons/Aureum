# Phase 5 — Parameter Sensitivity Analysis Findings

**Owner:** Hansika
**Strategy tested:** `BaselineMarketMaker` (core/strategy/baseline_market_maker.py)
**Symbol:** ADAUSDT (matches the strategy's tuned price scale)
**Windows tested:** 3 independent, non-overlapping 24-48h windows
(recent_24h, prior_24h, prior_48h) — avoids tuning parameters against
a single dataset
**Fill simulation:** core/backtest/candle_fill_model.py — realistic
asymmetric fills (a quote only fills if the candle's price range
actually touched it), replacing an earlier "every quote fills"
simplification that made inventory always cancel to zero

---

## Update (2026-08-24): Re-run with realistic fills

The original version of this analysis used a simplification where
every quote was assumed to fill, which made inventory always cancel
to exactly zero and made `inventory_skew_sensitivity` untestable.
Gauri's `candle_fill_model.py` (realistic asymmetric fills based on
candle high/low) has since landed, making a real re-test possible.
`base_half_spread`'s default was also retuned by Samarth (0.0005 →
0.001) based on real evaluation evidence. Both changes are reflected
below.

---

## Parameters Tested

| Parameter | Values tested |
|---|---|
| `base_half_spread` | 0.0005, 0.001 (new default), 0.0015 |
| `inventory_skew_sensitivity` | 0.00001, 0.00002 (default), 0.00005 |

---

## Finding 1: `base_half_spread` — Still Sound

`avg_quoted_spread` continues to scale correctly as `2 × base_half_spread`
under the realistic fill model, consistent across all 3 windows.
The retuned default (0.001) behaves predictably.

**Verdict: sound, no further concern from this analysis.**

---

## Finding 2: `inventory_skew_sensitivity` — Now Testable, and the Result Is Counterintuitive

With realistic asymmetric fills, inventory now moves meaningfully
away from zero (final_inventory ranged from -1700 to +2100 across
the tested grid, vs. always exactly 0 under the old simplification).

**The direction of inventory drift (positive vs. negative) differs by
window** — this reflects genuine underlying market movement during
that window, not the skew parameter itself, and is expected.

**The important, consistent result across ALL 3 windows:** higher
`inventory_skew_sensitivity` correlates with LARGER final inventory
magnitude, not smaller. At base_half_spread=0.001:

| Window | skew=0.00001 | skew=0.00002 | skew=0.00005 |
|---|---|---|---|
| recent_24h | -400 | -700 | -1300 |
| prior_24h | +900 | +1300 | +1500 |
| prior_48h | +700 | +1300 | +2100 |

In every window, magnitude grows monotonically with skew sensitivity.
This is the opposite of the parameter's documented intent (shifting
quotes to encourage trades that bring inventory back toward neutral).

**Possible explanation (not yet confirmed):** a stronger skew shifts
quotes more aggressively in the direction of existing inventory,
which may cause the strategy to chase the prevailing trend rather
than counteract it, amplifying drift instead of dampening it -
especially plausible in trending (vs. mean-reverting) market
conditions, which may describe all 3 tested windows.

**Verdict: needs adjustment or further investigation before this
parameter can be trusted at higher values.** Do not increase
`inventory_skew_sensitivity` above the current default (0.00002)
without first understanding why higher values amplify rather than
dampen inventory drift. Recommend Samarth review this finding before
any parameter change, since it may indicate an issue with the sign or
formulation of the skew calculation itself, not just its magnitude.

---

## Look-Ahead-Bias-via-Parameter-Selection Check

The skew finding was checked for consistency across all 3 independent
windows before being reported - the monotonic magnitude-growth pattern
holds in every window, which is what makes this a genuine finding
rather than a single-window artifact. No parameter was selected based
on outperforming on one window; this finding is being surfaced
specifically BECAUSE it holds consistently, which is the opposite of
cherry-picking.

---

## Recommendation

- `base_half_spread` = 0.001 (retuned default): confirmed sound.
- `inventory_skew_sensitivity`: **do not increase above current
  default without further investigation.** Recommend Samarth review
  whether the skew calculation's sign/formulation is behaving as
  intended, given it consistently amplifies rather than dampens
  inventory drift across all 3 tested windows.

## Reproduction