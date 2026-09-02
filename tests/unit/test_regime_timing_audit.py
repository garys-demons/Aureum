"""Tests for the Phase 8 regime-classification timing audit."""
from research.regime_timing_audit import audit_regime_call_timing, replay_and_audit_regime_calls


def test_correct_prefix_up_to_decision_point_is_safe():
    full_history = [100.0, 101.0, 102.0, 103.0, 104.0]
    decision_index = 2  # deciding at price 102.0
    prices_passed = full_history[:decision_index + 1]  # [100, 101, 102] - correct

    result = audit_regime_call_timing(full_history, decision_index, prices_passed)

    assert result.is_safe is True
    assert result.problems == []


def test_passing_future_prices_is_flagged_as_look_ahead():
    """The centerpiece test: deliberately hand the classifier prices
    that extend past the decision point, and confirm it's caught."""
    full_history = [100.0, 101.0, 102.0, 103.0, 104.0]
    decision_index = 2  # deciding at price 102.0
    prices_passed = full_history[:4]  # [100, 101, 102, 103] - includes index 3, the FUTURE

    result = audit_regime_call_timing(full_history, decision_index, prices_passed)

    assert result.is_safe is False
    assert any("Look-ahead detected" in p for p in result.problems)


def test_shuffled_prices_are_flagged_even_if_length_matches():
    full_history = [100.0, 101.0, 102.0, 103.0]
    decision_index = 2
    prices_passed = [100.0, 102.0, 101.0]  # same length as a correct prefix, but reordered

    result = audit_regime_call_timing(full_history, decision_index, prices_passed)

    assert result.is_safe is False
    assert any("not a genuine prefix" in p for p in result.problems)


def test_empty_prices_passed_is_not_flagged_as_unsafe():
    """An empty list (e.g. the very first decision, no history yet) has
    nothing to check against - shouldn't be a false positive."""
    full_history = [100.0, 101.0]
    result = audit_regime_call_timing(full_history, decision_index=0, prices_passed_to_classifier=[])

    assert result.is_safe is True


def test_replay_and_audit_catches_a_buggy_call_site():
    """
    Simulates a real, buggy strategy call site that accidentally passes
    ONE extra price beyond the decision point (an off-by-one), and
    confirms replay_and_audit_regime_calls() catches it across multiple
    decision points, not just one.
    """
    full_history = [float(i) for i in range(10)]

    def buggy_prices_fn(decision_index):
        return full_history[:decision_index + 2]  # off-by-one bug: one price too many

    results = replay_and_audit_regime_calls(full_history, decision_indices=[2, 4, 6], prices_fn=buggy_prices_fn)

    assert all(r.is_safe is False for r in results)


def test_replay_and_audit_passes_a_correct_call_site():
    full_history = [float(i) for i in range(10)]

    def correct_prices_fn(decision_index):
        return full_history[:decision_index + 1]  # correct

    results = replay_and_audit_regime_calls(full_history, decision_indices=[2, 4, 6], prices_fn=correct_prices_fn)

    assert all(r.is_safe is True for r in results)