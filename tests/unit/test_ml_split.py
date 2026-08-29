"""Unit tests for chronological ML train/test splitting (Phase 7)."""
from dataclasses import dataclass

from research.ml_split import chronological_split, audit_split_for_leakage


@dataclass
class FakeCandle:
    timestamp: int
    price: float


def ts_fn(c: FakeCandle) -> int:
    return c.timestamp


def make_candles(timestamps: list[int]) -> list[FakeCandle]:
    return [FakeCandle(timestamp=t, price=100 + i) for i, t in enumerate(timestamps)]


def test_split_correctly_separates_by_timestamp():
    candles = make_candles([100, 200, 300, 400, 500, 600])
    result = chronological_split(candles, ts_fn, split_timestamp=400)

    assert [c.timestamp for c in result.train] == [100, 200, 300]
    assert [c.timestamp for c in result.test] == [400, 500, 600]


def test_split_never_reorders_items():
    """Split must respect natural timestamp order, not input order."""
    candles = make_candles([500, 100, 300, 200, 400])  # deliberately out of order
    result = chronological_split(candles, ts_fn, split_timestamp=300)

    assert sorted(c.timestamp for c in result.train) == [100, 200]
    assert sorted(c.timestamp for c in result.test) == [300, 400, 500]


def test_embargo_drops_items_in_the_gap():
    # Using realistic ms-scale timestamps so embargo_seconds math is meaningful
    base = 1_700_000_000_000
    candles = make_candles([base, base + 60_000, base + 90_000, base + 120_000, base + 150_000, base + 240_000])
    # split at base+120_000, embargo of 60 seconds (60_000ms) -> test starts at base+180_000
    result = chronological_split(candles, ts_fn, split_timestamp=base + 120_000, embargo_seconds=60)

    assert [c.timestamp for c in result.train] == [base, base + 60_000, base + 90_000]
    assert [c.timestamp for c in result.test] == [base + 240_000]  # base+120_000 and base+150_000 dropped by embargo


def test_audit_finds_no_problems_on_clean_split():
    candles = make_candles([100, 200, 300, 400])
    result = chronological_split(candles, ts_fn, split_timestamp=300)

    problems = audit_split_for_leakage(result, ts_fn)
    assert problems == []


def test_audit_detects_leakage_when_train_overlaps_test():
    """Manually construct a leaking split to prove the auditor catches it."""
    candles = make_candles([100, 200, 300, 400])
    bad_result_train = candles[:3]  # includes timestamp 300
    bad_result_test = candles[2:]   # also includes timestamp 300 - overlap!

    from research.ml_split import SplitResult
    bad_split = SplitResult(train=bad_result_train, test=bad_result_test, split_timestamp=300)

    problems = audit_split_for_leakage(bad_split, ts_fn)
    assert len(problems) == 1
    assert "Leakage" in problems[0]


def test_audit_handles_empty_train_or_test_gracefully():
    candles = make_candles([100, 200])
    result = chronological_split(candles, ts_fn, split_timestamp=50)  # everything goes to test

    problems = audit_split_for_leakage(result, ts_fn)
    assert problems == []  # nothing to compare, not an error