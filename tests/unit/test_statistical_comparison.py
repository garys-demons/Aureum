"""Unit tests for statistical comparison toolkit (Phase 8)."""
import pytest

from research.statistical_comparison import (
    returns_from_equity_curve,
    bootstrap_mean_return,
    compare_two_runs,
)


def test_returns_from_equity_curve_hand_calculated():
    equity = [100.0, 110.0, 99.0]
    returns = returns_from_equity_curve(equity)

    assert returns == pytest.approx([0.10, -0.10])


def test_returns_from_equity_curve_empty_when_too_short():
    assert returns_from_equity_curve([100.0]) == []
    assert returns_from_equity_curve([]) == []


def test_bootstrap_mean_return_point_estimate_matches_simple_mean():
    returns = [0.01, 0.02, -0.01, 0.03, 0.00]
    result = bootstrap_mean_return(returns, n_resamples=1000)

    assert result.point_estimate == pytest.approx(sum(returns) / len(returns))


def test_bootstrap_mean_return_ci_contains_point_estimate():
    returns = [0.01, 0.02, -0.01, 0.03, 0.00, 0.015, -0.005]
    result = bootstrap_mean_return(returns, n_resamples=2000)

    assert result.ci_lower <= result.point_estimate <= result.ci_upper


def test_bootstrap_mean_return_raises_on_empty():
    with pytest.raises(ValueError):
        bootstrap_mean_return([], n_resamples=100)


def test_bootstrap_is_reproducible_with_fixed_seed():
    returns = [0.01, -0.02, 0.03, 0.01, -0.01]
    r1 = bootstrap_mean_return(returns, n_resamples=1000, seed=7)
    r2 = bootstrap_mean_return(returns, n_resamples=1000, seed=7)

    assert r1.ci_lower == r2.ci_lower
    assert r1.ci_upper == r2.ci_upper


def test_compare_two_runs_identical_series_is_inconclusive():
    """Identical data must never claim one side beats the other."""
    returns = [0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.005]
    result = compare_two_runs(returns, list(returns), n_resamples=2000)

    assert result.conclusive is False
    assert "INCONCLUSIVE" in result.interpretation


def test_compare_two_runs_detects_clear_difference_with_enough_data():
    """A large, consistent difference with a reasonably large sample
    should be detected as conclusive."""
    baseline = [0.001] * 200  # tiny, consistent positive return
    variant = [0.05] * 200    # dramatically larger, consistent return

    result = compare_two_runs(baseline, variant, n_resamples=2000)

    assert result.conclusive is True
    assert result.difference_ci_lower > 0


def test_compare_two_runs_tiny_sample_with_small_difference_is_inconclusive():
    """
    The realistic Phase 8 scenario: a small sample (a few days of
    data) with a modest difference should honestly report
    inconclusive, not overstate confidence.
    """
    baseline = [0.001, -0.002, 0.0015, 0.0005, -0.001]
    variant = [0.002, -0.001, 0.002, 0.001, -0.0005]

    result = compare_two_runs(baseline, variant, n_resamples=2000)

    assert result.conclusive is False
    assert "cannot support a confident claim" in result.interpretation


def test_compare_two_runs_reports_sample_sizes_in_interpretation():
    baseline = [0.01, 0.02, -0.01]
    variant = [0.005, 0.015]

    result = compare_two_runs(baseline, variant, n_resamples=1000)

    assert "n=3/2" in result.interpretation