"""
research/run_phase8_comparison.py — Phase 8 real statistical comparison.

Loads Samarth's persisted Baseline vs Baseline+AI runs across all 3
pinned windows (recent_24h, prior_24h, prior_48h) and applies genuine
confidence framing via bootstrap comparison, rather than reporting
which point estimate is bigger.
"""
from research.storage import load_dataset
from research.statistical_comparison import returns_from_equity_curve, compare_two_runs


WINDOWS = ["recent_24h", "prior_24h", "prior_48h"]


def load_equity_returns(run_name: str) -> list[float]:
    """Load a run's equity curve and convert it to period returns."""
    equity_df = load_dataset("results", f"{run_name}_equity")
    equity_values = equity_df["equity"].tolist()
    return returns_from_equity_curve(equity_values)


def main():
    print("=" * 70)
    print("Phase 8: Baseline vs Baseline+AI — Statistical Comparison")
    print("=" * 70)

    for window in WINDOWS:
        baseline_run = f"phase8_compare_baseline_{window}"
        ai_run = f"phase8_compare_ai_{window}"

        print(f"\n--- Window: {window} ---")

        try:
            baseline_returns = load_equity_returns(baseline_run)
            ai_returns = load_equity_returns(ai_run)
        except FileNotFoundError as e:
            print(f"  SKIPPED: dataset not found ({e})")
            continue

        print(f"  Baseline: n={len(baseline_returns)} return observations")
        print(f"  AI variant: n={len(ai_returns)} return observations")

        if len(baseline_returns) == 0 or len(ai_returns) == 0:
            print("  SKIPPED: insufficient data for comparison")
            continue

        result = compare_two_runs(baseline_returns, ai_returns, n_resamples=10_000)

        print(f"  Baseline mean return: {result.baseline_estimate.point_estimate:.6f} "
              f"[{result.baseline_estimate.ci_lower:.6f}, {result.baseline_estimate.ci_upper:.6f}]")
        print(f"  AI variant mean return: {result.variant_estimate.point_estimate:.6f} "
              f"[{result.variant_estimate.ci_lower:.6f}, {result.variant_estimate.ci_upper:.6f}]")
        print(f"  Difference CI: [{result.difference_ci_lower:.6f}, {result.difference_ci_upper:.6f}]")
        print(f"  Conclusive: {result.conclusive}")
        print(f"  {result.interpretation}")


if __name__ == "__main__":
    main()