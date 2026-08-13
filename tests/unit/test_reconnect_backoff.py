"""Unit tests for reconnection backoff timing logic."""
from services.market_data.adapters.binance import (
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    BACKOFF_MULTIPLIER,
)


def test_backoff_doubles_correctly():
    """Simulate the backoff progression and confirm it matches config (1s -> 60s cap)."""
    backoff = INITIAL_BACKOFF_SECONDS
    sequence = [backoff]

    for _ in range(8):
        backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
        sequence.append(backoff)

    assert sequence[0] == 1
    assert sequence[1] == 2
    assert sequence[2] == 4
    assert sequence[-1] == 60  # should be capped, not growing forever


def test_backoff_never_exceeds_max():
    """No matter how many failures, backoff should never exceed MAX_BACKOFF_SECONDS."""
    backoff = INITIAL_BACKOFF_SECONDS
    for _ in range(20):
        backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
    assert backoff == MAX_BACKOFF_SECONDS