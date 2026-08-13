"""
Replay harness (Phase 2) — feeds a recorded snapshot + delta sequence
through OrderBook and returns the final state, so tests can assert it
matches a known-good expected result deterministically.
"""
from services.market_data.models import OrderBookSnapshot, OrderBookDelta
from services.market_data.order_book_state import OrderBook


def replay_sequence(snapshot: OrderBookSnapshot, deltas: list[OrderBookDelta]) -> OrderBook:
    """
    Apply a sequence of deltas to a fresh OrderBook built from `snapshot`,
    in the exact order given, with contiguity verified at each step.

    Raises ValueError on the first gap found (first_update_id doesn't
    follow directly from the previous final_update_id) — mirrors the
    live pipeline's behavior (TRD §6.1 step 6), so replay tests exercise
    the same failure mode as production.
    """
    book = OrderBook(snapshot)

    for delta in deltas:
        expected_first_id = book.last_update_id + 1
        if delta.first_update_id != expected_first_id:
            raise ValueError(
                f"Gap detected during replay: expected first_update_id="
                f"{expected_first_id}, got {delta.first_update_id}"
            )
        book.apply_delta(delta)

    return book