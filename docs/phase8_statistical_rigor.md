# Phase 8 - Statistical Rigor & Sample-Size Framing

**Owner:** Hansika
**Purpose:** Ensure "Baseline vs. Baseline+AI" comparison is judged by genuine statistical confidence, not just point estimates.

---

## The Core Tool

research/statistical_comparison.py - compare_two_runs(baseline_returns, variant_returns)

Uses bootstrap resampling (10,000 resamples by default) on the difference between the two runs' mean returns, rather than comparing each run's own confidence interval separately (a weaker, common shortcut). A result is only reported as conclusive if the difference's confidence interval excludes zero.

Bootstrap resampling was chosen over a standard t-test because financial returns are frequently non-normal (fat tails, skew) - a t-test's normality assumption is exactly the kind of thing that can silently overstate confidence with a small, non-representative sample.

---

## What Our Sample Size Can and Cannot Support

Our backtest windows (Phase 5's recent_24h/prior_24h/prior_48h, now fixed and reproducible per Phase 7) provide 1-minute candles over 24-48 hour windows, roughly 1,440-2,880 return observations per window at the candle level.

However, trade-level returns (what actually matters for PnL comparison) are far fewer. A market-making strategy quoting continuously does not mean every candle produces a realized trade. The actual number of realized round-trip trades in a 24-48h window is typically in the tens, not thousands.

**What this CAN support:**
- Detecting a large, consistent difference in behavior, such as the AI variant clearly avoiding quoting during extreme volatility events, visible directly in trade counts and timing around those events.
- A directional signal worth further investigation.

**What this CANNOT support:**
- A confident claim that one strategy has a genuinely higher expected return than the other. With tens of trade observations, the bootstrap confidence interval on mean return will typically be wide relative to any realistic difference in strategy quality, meaning small, real improvements will often be statistically indistinguishable from noise at this sample size.
- Any claim of statistical significance based on p-values from a single short backtest window. A single 24-48h window is one sample path, not many independent trials.

**The honest conclusion, stated in advance:** given this sample size, an inconclusive result should be the EXPECTED outcome, not a disappointing one. If compare_two_runs() reports inconclusive, that is very likely the statistically correct answer, not a sign the analysis failed.

---

## Look-Ahead Audit: Regime-Classification Timing

See docs/phase8_regime_timing_audit.md for the specific audit of whether the regime classifier's assessment at each decision point uses only data available at that point in time.

---

## Reproduction

python -m pytest tests/unit/test_statistical_comparison.py -v

Real comparison to be run once Samarth's Baseline+AI variant and Gauri's evaluation harness produce phase5_baseline and phase8_baseline_plus_ai results under research.storage.