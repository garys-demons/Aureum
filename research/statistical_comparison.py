"""
research/statistical_comparison.py — Phase 8 statistical rigor.

"Statistically compared" means more than "which number is bigger."
This module provides genuine measures of confidence/variability for
comparing two backtest runs (e.g. phase5_baseline vs
phase8_baseline_plus_ai), rather than just comparing point estimates.

Core principle: with a small sample (a few days of data), an
inconclusive result is a valid, honest finding. This module is built
to make "we can't tell" a clearly representable outcome, not an
awkward edge case.
"""
import math
import random
from dataclasses import dataclass


def returns_from_equity_curve(equity_values: list[float]) -> list[float]:
    """
    Convert a sequence of equity values into period-over-period
    percentage returns. len(returns) == len(equity_values) - 1.
    """
    if len(equity_values) < 2:
        return []
    return [
        (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
        for i in range(1, len(equity_values))
    ]


@dataclass
class BootstrapResult:
    point_estimate: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    n_samples: int
    n_resamples: int


def bootstrap_mean_return(
    returns: list[float],
    confidence_level: float = 0.95,
    n_resamples: int = 10_000,
    seed: int | None = 42,
) -> BootstrapResult:
    """
    Estimates a confidence interval for the mean return via bootstrap
    resampling: repeatedly resample (with replacement) from the
    observed returns, compute the mean each time, and take the
    percentiles of that distribution as the interval bounds.

    This is deliberately used instead of assuming a normal
    distribution (e.g. a plain t-test) — financial returns are
    frequently non-normal (fat tails, skew), and with a small sample
    the normality assumption is exactly the kind of thing that
    silently overstates confidence.
    """
    if len(returns) == 0:
        raise ValueError("Cannot bootstrap an empty returns series")

    rng = random.Random(seed)
    n = len(returns)
    point_estimate = sum(returns) / n

    resampled_means = []
    for _ in range(n_resamples):
        resample = [returns[rng.randrange(n)] for _ in range(n)]
        resampled_means.append(sum(resample) / n)

    resampled_means.sort()
    alpha = 1 - confidence_level
    lower_idx = int((alpha / 2) * n_resamples)
    upper_idx = int((1 - alpha / 2) * n_resamples)

    return BootstrapResult(
        point_estimate=point_estimate,
        ci_lower=resampled_means[lower_idx],
        ci_upper=resampled_means[upper_idx],
        confidence_level=confidence_level,
        n_samples=n,
        n_resamples=n_resamples,
    )


@dataclass
class ComparisonResult:
    baseline_estimate: BootstrapResult
    variant_estimate: BootstrapResult
    difference_ci_lower: float
    difference_ci_upper: float
    intervals_overlap: bool
    conclusive: bool
    interpretation: str


def compare_two_runs(
    baseline_returns: list[float],
    variant_returns: list[float],
    confidence_level: float = 0.95,
    n_resamples: int = 10_000,
    seed: int | None = 42,
) -> ComparisonResult:
    """
    Compares two return series via bootstrap confidence intervals on
    the DIFFERENCE in mean returns, not just each series' own interval
    separately — comparing two overlapping individual intervals is a
    common but statistically weaker shortcut than directly bootstrapping
    the paired difference.

    A result is only reported as "conclusive" (one variant is genuinely
    better) if the confidence interval for the DIFFERENCE excludes
    zero. Otherwise, per Phase 8's own requirement, this returns an
    honest "inconclusive" interpretation rather than picking a winner
    based on point estimates alone.
    """
    baseline_est = bootstrap_mean_return(baseline_returns, confidence_level, n_resamples, seed)
    variant_est = bootstrap_mean_return(variant_returns, confidence_level, n_resamples, seed)

    rng = random.Random(seed)
    n_base = len(baseline_returns)
    n_var = len(variant_returns)

    diffs = []
    for _ in range(n_resamples):
        base_resample = [baseline_returns[rng.randrange(n_base)] for _ in range(n_base)]
        var_resample = [variant_returns[rng.randrange(n_var)] for _ in range(n_var)]
        diffs.append((sum(var_resample) / n_var) - (sum(base_resample) / n_base))

    diffs.sort()
    alpha = 1 - confidence_level
    lower_idx = int((alpha / 2) * n_resamples)
    upper_idx = int((1 - alpha / 2) * n_resamples)
    diff_lower = diffs[lower_idx]
    diff_upper = diffs[upper_idx]

    conclusive = not (diff_lower <= 0 <= diff_upper)
    intervals_overlap = not (
        baseline_est.ci_upper < variant_est.ci_lower or variant_est.ci_upper < baseline_est.ci_lower
    )

    if conclusive and diff_lower > 0:
        interpretation = (
            f"The variant's mean return is statistically distinguishable from the "
            f"baseline's at the {confidence_level:.0%} level (difference CI: "
            f"[{diff_lower:.5f}, {diff_upper:.5f}], excludes zero)."
        )
    elif conclusive and diff_upper < 0:
        interpretation = (
            f"The baseline's mean return is statistically distinguishable from the "
            f"variant's at the {confidence_level:.0%} level (difference CI: "
            f"[{diff_lower:.5f}, {diff_upper:.5f}], excludes zero)."
        )
    else:
        interpretation = (
            f"INCONCLUSIVE: the {confidence_level:.0%} confidence interval for the "
            f"difference in mean returns is [{diff_lower:.5f}, {diff_upper:.5f}], "
            f"which includes zero. With n={n_base}/{n_var} return observations, "
            f"this sample size cannot support a confident claim that either "
            f"strategy outperforms the other."
        )

    return ComparisonResult(
        baseline_estimate=baseline_est,
        variant_estimate=variant_est,
        difference_ci_lower=diff_lower,
        difference_ci_upper=diff_upper,
        intervals_overlap=intervals_overlap,
        conclusive=conclusive,
        interpretation=interpretation,
    )