"""
scripts/capture_order_book_fixture.py

Connects to real Binance Testnet and records a real, live snapshot+delta
sequence to a replay fixture file — the actual capture step behind
Phase 2's "Replay Fixture Storage" task.

WHY THIS HAS TO BE RUN FOR REAL, NOT SIMULATED
------------------------------------------------
A fixture spanning a genuine reconnect needs an actual disconnect and
reconciliation to happen — this can't be faked convincingly, since the
whole point is Hansika's replay harness testing against something that
really happened, not a hand-constructed guess at what a reconnect
"should" look like.

WHERE THE SNAPSHOTS IN THE FIXTURE ACTUALLY COME FROM
--------------------------------------------------------
BinanceAdapter.stream_order_book() only yields (delta, book) tuples to
callers — it never exposes the raw OrderBookSnapshot object it fetched
internally during reconciliation (see adapters/binance.py). Rather than
change that shared interface just for this script, this capture
reconstructs an equivalent snapshot FROM the OrderBook's state at the
moment reconciliation completes (detected by the `book` object's
identity changing — a fresh OrderBook instance is only ever created by
a new reconciliation, see stream_order_book's `book = OrderBook.from_snapshot(...)`).

This is exactly what SnapshotSource.RECONCILED was reserved for
(services/market_data/models.py's docstring: "nothing emits it yet") —
this is the first thing that does. Recorded this way, the fixture is
semantically equivalent to a real snapshot for replay purposes: a
valid, self-consistent starting point plus the deltas that followed.

HOW TO CAPTURE A RECONNECT-SPANNING FIXTURE
---------------------------------------------
1. Run this script (see usage below)
2. While it's running, disconnect your network for ~10-30 seconds
   (same trick used for the Phase 1 forced-reconnect test) — then
   reconnect
3. Let the script keep running a bit longer after reconnecting, so the
   fixture captures deltas both before AND after the reconnect
4. Stop with Ctrl+C — everything captured up to that point is already
   saved (the recorder flushes after every event)

Usage:
    PYTHONPATH=. python scripts/capture_order_book_fixture.py BTCUSDT \\
        tests/fixtures/order_book/btcusdt_live_reconnect.jsonl \\
        --max-events 500
"""
import argparse
import asyncio
import sys

import structlog

from core.logging_config import configure_logging
from services.market_data.adapters.binance import BinanceAdapter
from services.market_data.fixtures import FixtureRecorder
from services.market_data.models import OrderBookSnapshot, PriceLevel, SnapshotSource

log = structlog.get_logger("capture_fixture")


async def capture(symbol: str, output_path: str, max_events: int | None) -> None:
    adapter = BinanceAdapter(config={})

    log.info(
        "capture_starting",
        symbol=symbol,
        output=output_path,
        max_events=max_events or "unlimited (stop with Ctrl+C)",
    )

    last_book_ref = None  # tracks OrderBook object identity, not equality

    with FixtureRecorder(output_path) as recorder:
        async for delta, book in adapter.stream_order_book(symbol):
            if book is not last_book_ref:
                # A new OrderBook instance means reconciliation just ran
                # (either the initial connect, or a real reconnect).
                # Reconstruct an equivalent snapshot from its current
                # state — see module docstring for why.
                snapshot = OrderBookSnapshot(
                    event_type="depth_snapshot",
                    exchange="binance",
                    symbol=symbol,
                    event_time=delta.event_time,
                    received_time=delta.received_time,
                    last_update_id=book.last_update_id,
                    snapshot_time=delta.event_time,
                    source=SnapshotSource.RECONCILED,
                    bids=[PriceLevel(price=p, quantity=q) for p, q in book.bids.items()],
                    asks=[PriceLevel(price=p, quantity=q) for p, q in book.asks.items()],
                )
                recorder.record(snapshot)
                last_book_ref = book

                if recorder.count > 1:
                    log.warning(
                        "reconnect_detected_mid_capture",
                        events_so_far=recorder.count,
                        new_last_update_id=book.last_update_id,
                    )
            else:
                recorder.record(delta)

            if recorder.count % 25 == 0:
                log.info(
                    "capture_progress",
                    events_captured=recorder.count,
                    last_update_id=book.last_update_id,
                    spread=book.spread(),
                )

            if max_events and recorder.count >= max_events:
                log.info("capture_reached_max_events", count=recorder.count)
                break

    log.info("capture_finished", total_events=recorder.count, output=output_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="e.g. BTCUSDT")
    parser.add_argument("output_path", help="where to write the .jsonl fixture")
    parser.add_argument(
        "--max-events", type=int, default=None,
        help="stop automatically after this many events (default: run until Ctrl+C)",
    )
    args = parser.parse_args()

    configure_logging()

    try:
        asyncio.run(capture(args.symbol, args.output_path, args.max_events))
    except KeyboardInterrupt:
        log.info("capture_interrupted_by_user")
        sys.exit(0)


if __name__ == "__main__":
    main()