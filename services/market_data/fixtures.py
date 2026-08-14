"""
services/market_data/fixtures.py

Replay fixture format for order book snapshot+delta sequences (Phase 2,
Aryan's "Replay Fixture Storage" task — feeds Hansika's replay harness).

FORMAT
------
One JSON object per line (JSON-lines / .jsonl), in the exact order the
events occurred. Each line has a "type" field ("snapshot" or "delta")
and a "data" field holding that event's full Pydantic fields, exactly
as produced by OrderBookSnapshot/OrderBookDelta:

    {"type": "snapshot", "data": {...OrderBookSnapshot fields...}}
    {"type": "delta", "data": {...OrderBookDelta fields...}}
    {"type": "delta", "data": {...OrderBookDelta fields...}}
    {"type": "snapshot", "data": {...}}   <- a second snapshot mid-file
                                              means reconciliation ran
                                              again here (e.g. a real
                                              reconnect happened during
                                              capture)

Why JSON-lines and not one big JSON array: the harness can read and
replay one event at a time without loading the whole fixture into
memory first, and a capture script can append events as they arrive
without holding the whole sequence in memory either — useful for
fixtures spanning a long real reconnect.

Why "type" + raw "data" instead of trying to be clever about ordering:
deterministic replay only needs "what happened, in what order" — the
harness re-validates each event through the real Pydantic model on
load (see load_fixture below), so a corrupted or hand-edited fixture
fails loudly instead of silently replaying bad data.
"""
import json
from pathlib import Path
from typing import Iterator

from services.market_data.models import OrderBookDelta, OrderBookSnapshot

FixtureEvent = OrderBookSnapshot | OrderBookDelta


class FixtureRecorder:
    """
    Appends snapshot/delta events to a .jsonl fixture file as they occur.

    Usage (see scripts/capture_order_book_fixture.py for the real,
    live-capture version):

        with FixtureRecorder(path) as recorder:
            recorder.record(snapshot)
            recorder.record(delta)
            ...
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._count = 0

    def __enter__(self) -> "FixtureRecorder":
        self._file = open(self.path, "w")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._file:
            self._file.close()

    def record(self, event: FixtureEvent) -> None:
        if isinstance(event, OrderBookSnapshot):
            event_type = "snapshot"
        elif isinstance(event, OrderBookDelta):
            event_type = "delta"
        else:
            raise TypeError(
                f"FixtureRecorder only accepts OrderBookSnapshot or "
                f"OrderBookDelta, got {type(event).__name__}"
            )

        line = json.dumps({"type": event_type, "data": event.model_dump(mode="json")})
        self._file.write(line + "\n")
        self._file.flush()  # so a capture killed mid-run still has everything up to that point
        self._count += 1

    @property
    def count(self) -> int:
        return self._count


def load_fixture(path: str | Path) -> Iterator[FixtureEvent]:
    """
    Reads a .jsonl fixture file and yields real, validated
    OrderBookSnapshot/OrderBookDelta instances in file order — ready to
    feed straight into OrderBook.from_snapshot() / OrderBook.apply().

    Raises ValueError with the line number if a line is malformed or has
    an unrecognized "type" — fails loudly rather than silently skipping
    a corrupted fixture line.
    """
    path = Path(path)
    with open(path) as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_num}: invalid JSON — {e}") from e

            event_type = record.get("type")
            data = record.get("data")

            if event_type == "snapshot":
                yield OrderBookSnapshot(**data)
            elif event_type == "delta":
                yield OrderBookDelta(**data)
            else:
                raise ValueError(
                    f"{path}:{line_num}: unrecognized fixture type {event_type!r} "
                    f"(expected 'snapshot' or 'delta')"
                )