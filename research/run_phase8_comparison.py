"""
research/run_phase8_comparison.py — Phase 8 real statistical comparison.

Loads Samarth's persisted Baseline vs Baseline+AI runs across all 3
pinned windows (recent_24h, prior_24h, prior_48h) and applies genuine
confidence framing via bootstrap comparison, rather than reporting
which point estimate is bigger.

Bootstraps over TRADE-LEVEL realized PnL, not candle-level equity
returns. With only 2-34 fills across 1,440-2,880 candles, the equity
curve is overwhelmingly flat between fills - a candle-level return
series would be dominated by zeros and obscure the real signal from
the handful of moments a trade actually happened. Trade-level PnL is
the honest unit of comparison here.
"""
from research.storage import load_dataset
from research.statistical_comparison import compare_two_runs


WINDOWS = ["recent_24h", "prior_24h", "prior_48h"]


def load_trade_pnls(run_name: str) -> list[float]:
    """
    Load a run's trade log and return the realized_pnl of only the
    CLOSING trades - opening trades always carry realized_pnl=0.0 by
    construction (nothing to realize yet, per Portfolio's own design),
    not a genuine zero-PnL outcome. Including them would silently
    double the apparent sample size with non-observations and bias
    the bootstrap toward zero. Verified this filter exactly matches
    each run's own num_closing_trades summary field before relying on
    it (see the nonzero-vs-summary check run before this fix).
    """
    trades_df = load_dataset("results", f"{run_name}_trades")
    if "note" in trades_df.columns:
        return []  # placeholder row for a zero-trade run
    return trades_df.loc[trades_df["realized_pnl"] != 0.0, "realized_pnl"].tolist()


def main():
    print("=" * 70)
    print("Phase 8: Baseline vs Baseline+AI - Statistical Comparison")
    print("(bootstrapped over trade-level realized PnL)")
    print("=" * 70)

    for window in WINDOWS:
        baseline_run = f"phase8_compare_baseline_{window}"
        ai_run = f"phase8_compare_ai_{window}"

        print(f"\n--- Window: {window} ---")

        try:
            baseline_pnls = load_trade_pnls(baseline_run)
            ai_pnls = load_trade_pnls(ai_run)
        except FileNotFoundError as e:
            print(f"  SKIPPED: dataset not found ({e})")
            continue

        print(f"  Baseline: n={len(baseline_pnls)} trades, PnLs={baseline_pnls}")
        print(f"  AI variant: n={len(ai_pnls)} trades, PnLs={ai_pnls}")

        if len(baseline_pnls) < 2 or len(ai_pnls) < 2:
            print(
                f"  CANNOT COMPARE: baseline has {len(baseline_pnls)} closing trade(s), "
                f"AI variant has {len(ai_pnls)} closing trade(s). Bootstrap resampling "
                f"requires at least 2 observations per side to be meaningful. This is a "
                f"genuine finding, not a failure - the sample is simply too small in this "
                f"window to say anything statistical."
            )
            continue

        result = compare_two_runs(baseline_pnls, ai_pnls, n_resamples=10_000)

        print(f"  Baseline mean PnL/trade: {result.baseline_estimate.point_estimate:.6f} "
              f"[{result.baseline_estimate.ci_lower:.6f}, {result.baseline_estimate.ci_upper:.6f}]")
        print(f"  AI variant mean PnL/trade: {result.variant_estimate.point_estimate:.6f} "
              f"[{result.variant_estimate.ci_lower:.6f}, {result.variant_estimate.ci_upper:.6f}]")
        print(f"  Difference CI: [{result.difference_ci_lower:.6f}, {result.difference_ci_upper:.6f}]")
        print(f"  Conclusive: {result.conclusive}")
        print(f"  {result.interpretation}")


if __name__ == "__main__":
    main()