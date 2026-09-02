# Phase 8 - Real Statistical Findings

**Owner:** Hansika
**Data:** Baseline vs Baseline+AI, 3 pinned windows, real trade-level PnL (2026-09-02)

---

## Bug Fixed Before This Analysis

The initial comparison script bootstrapped over candle-level equity returns, which was dominated by structural zeros (equity is flat between trades with only 2-34 fills across 1,440-2,880 candles). Fixed to bootstrap over trade-level realized PnL, filtering to CLOSING trades only - opening trades always carry realized_pnl=0.0 by construction (nothing to realize yet), not a genuine zero-PnL outcome. Verified this filter exactly matches each run's own num_closing_trades summary field before relying on it.

---

## Results by Window

### recent_24h
- Baseline: 2 closing trades, PnLs [0.189, -0.040]
- AI variant: 1 closing trade, PnL [-0.040]
- **Cannot compare** - AI variant has only 1 observation, below the minimum of 2 needed for bootstrap resampling to be meaningful.

### prior_24h
- Baseline: 8 closing trades
- AI variant: 1 closing trade, PnL [-0.091]
- **Cannot compare** - same reason as above.

### prior_48h
- Baseline: 17 closing trades, mean PnL -0.0106 [95% CI: -0.0417, 0.0259]
- AI variant: 9 closing trades, mean PnL -0.0090 [95% CI: -0.0390, 0.0288]
- Difference CI: [-0.0465, 0.0520] - **includes zero**
- **Inconclusive.** The AI variant's point estimate is slightly better (-0.0090 vs -0.0106), matching the directional pattern Samarth described, but the confidence interval is wide relative to the difference and cannot rule out the baseline being equal or better.

---

## Honest Overall Conclusion

**No window supports a confident claim that Baseline+AI outperforms the baseline.** Two of three windows have too few AI-variant trades (1 each) to run a statistical comparison at all - this is itself informative: the AI variant's volatility-avoidance behavior means it trades far less often, which is consistent with its design (reduce/pause quoting during HIGH_VOLATILITY), but it also means we have very little data to evaluate it on in the two shorter windows.

The one window with enough data on both sides (prior_48h) shows a directionally favorable but statistically inconclusive result for the AI variant.

**This matches exactly what docs/phase8_statistical_rigor.md predicted in advance: an inconclusive result given this sample size is the expected, correct outcome - not a sign the analysis failed.**

---

## Outstanding Caveat (flagged by Samarth, not yet addressed)

MAKER_FEE_RATE is currently set to 0.0005, half of Binance's real spot maker fee (0.001). Given how thin every result is (fractions of a percent either way), this could plausibly flip the sign of some of these already-small differences. **These findings should be treated as provisional until re-run at the correct fee rate.**

---

## Recommendation

- Do not report Baseline+AI as "better than baseline" based on this data - the evidence does not support that claim.
- The most useful next step is likely NOT more statistical squeezing of this same small sample, but either (a) running across more/longer windows to get enough AI-variant trades for a real comparison, or (b) fixing the fee-rate issue first, since it affects the interpretation of any number here.
- Two of three windows had too few AI trades to evaluate at all - worth discussing with Samarth whether the volatility-avoidance threshold is appropriately calibrated, or too conservative for these particular windows.

## Reproduction

```
python -m research.download_sensitivity_windows
python -c "from research.backtest.run_comparison_evaluation import run_comparison_across_windows; run_comparison_across_windows()"
python -m research.run_phase8_comparison
```