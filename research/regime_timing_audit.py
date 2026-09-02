"""
research/regime_timing_audit.py — Phase 8 look-ahead audit for
regime-classification timing.

core.ai_reasoning.regime_classifier.classify_regime() is safe by
construction: it only ever assesses the LAST element of whatever price
list it's given. The real risk is not inside that function - it's in
whatever code calls it during a backtest, which must only ever pass
prices available up to and including the current decision point.

This module verifies that guarantee holds for a given call site,
rather than re-verifying classify_regime() itself (already covered by
its own tests in test_regime_classifier.py).
"""
from dataclasses import dataclass

from core.ai_reasoning.regime_classifier import classify_regime, RegimeAssessment


@dataclass
class TimingAuditResult:
    is_safe: bool
    problems: list[str]


def audit_regime_call_timing(
    full_price_history: list[float],
    decision_index: int,
    prices_passed_to_classifier: list[float],
) -> TimingAuditResult:
    """
    Given the FULL price history, the index in that history where a
    trading decision was made, and the actual prices that were passed
    to classify_regime() for that decision, confirms:

    1. prices_passed_to_classifier is a genuine prefix of
       full_price_history (not a random slice, not shuffled).
    2. Its last element corresponds to decision_index or earlier -
       never later. This is the actual look-ahead check: if the
       classifier's assessment describes a price index PAST the
       decision point, the decision used information from the future.
    """
    problems: list[str] = []

    n_passed = len(prices_passed_to_classifier)
    if n_passed > 0:
        expected_prefix = full_price_history[:n_passed]
        if prices_passed_to_classifier != expected_prefix:
            problems.append(
                "prices_passed_to_classifier is not a genuine prefix of "
                "full_price_history - the classifier may have been given "
                "reordered, shuffled, or non-contiguous data."
            )

        last_price_index = n_passed - 1  # index in full_price_history the last element corresponds to
        if last_price_index > decision_index:
            problems.append(
                f"Look-ahead detected: classifier's assessment describes "
                f"price index {last_price_index}, which is AFTER the "
                f"decision point at index {decision_index}. The decision "
                f"used {last_price_index - decision_index} future price(s)."
            )

    return TimingAuditResult(is_safe=(len(problems) == 0), problems=problems)


def replay_and_audit_regime_calls(
    full_price_history: list[float],
    decision_indices: list[int],
    prices_fn,
) -> list[TimingAuditResult]:
    """
    Convenience runner: for each decision_index, calls prices_fn(index)
    to get whatever prices the real strategy code WOULD pass to
    classify_regime() at that point, and audits it.

    prices_fn: a callable matching the real call site's own logic for
    "what prices do I hand the classifier at decision index i" - e.g.
    `lambda i: full_price_history[:i+1]` for a strategy that correctly
    passes everything up to and including the current point.
    """
    results = []
    for idx in decision_indices:
        prices_at_decision = prices_fn(idx)
        result = audit_regime_call_timing(full_price_history, idx, prices_at_decision)
        results.append(result)
    return results