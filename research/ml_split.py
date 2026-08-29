"""
research/ml_split.py — chronological train/test split discipline for
ML models (Phase 7). Extends Hansika's Phase 3 look-ahead-bias audit
to the ML-specific case: a random/shuffled split of time-series data
can let a model train on rows that come AFTER a test point it's later
evaluated against - leaking future information into training even
though no single row is, by itself, "from the future."

Core rule (non-negotiable): splits must be chronological, never
randomized or shuffled. Every training row's timestamp must be
strictly before every test row's timestamp - no exceptions, no
"mostly chronological."
"""
from dataclasses import dataclass
from typing import Any, Callable, Sequence


@dataclass
class SplitResult:
    train: list
    test: list
    split_timestamp: int
    embargo_seconds: int = 0


def chronological_split(
    items: Sequence[Any],
    timestamp_fn: Callable[[Any], int],
    split_timestamp: int,
    embargo_seconds: int = 0,
) -> SplitResult:
    """
    Split `items` into train/test by timestamp - never by row order or
    random sampling. Items with timestamp < split_timestamp go to
    train; items with timestamp >= (split_timestamp + embargo) go to
    test. Items strictly inside the embargo window are dropped from
    both sets.

    timestamp_fn: extracts a comparable Unix-ms timestamp from one
    item, e.g. `lambda c: c.close_time` for Candle objects.
    embargo_seconds: an optional gap between train and test. Useful
    when features are computed over rolling windows (e.g. Phase 3's
    rolling_volatility, rsi) - without a gap, a test-set feature
    computed near the boundary could be influenced by rows just inside
    the training set, a subtler form of leakage than a raw timestamp
    overlap.
    """
    embargo_ms = embargo_seconds * 1000
    test_start = split_timestamp + embargo_ms

    train = [i for i in items if timestamp_fn(i) < split_timestamp]
    test = [i for i in items if timestamp_fn(i) >= test_start]

    return SplitResult(
        train=train, test=test,
        split_timestamp=split_timestamp,
        embargo_seconds=embargo_seconds,
    )


def audit_split_for_leakage(result: SplitResult, timestamp_fn: Callable[[Any], int]) -> list[str]:
    """
    Checks a SplitResult for look-ahead leakage. Returns a list of
    human-readable problems found; an empty list means the split is
    clean.
    """
    problems: list[str] = []

    if not result.train or not result.test:
        return problems  # nothing to compare against

    max_train_ts = max(timestamp_fn(i) for i in result.train)
    min_test_ts = min(timestamp_fn(i) for i in result.test)

    if max_train_ts >= min_test_ts:
        offenders = [i for i in result.train if timestamp_fn(i) >= min_test_ts]
        problems.append(
            f"Leakage: {len(offenders)} training item(s) have timestamps "
            f">= the earliest test timestamp ({min_test_ts}). Latest "
            f"training timestamp was {max_train_ts}."
        )

    return problems