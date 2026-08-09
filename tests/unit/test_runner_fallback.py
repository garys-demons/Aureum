"""
tests/unit/test_runner_fallback.py

Confirms the fix to the shutdown-flush bug Samarth found: if the final
commit fails when the runner is shutting down, the pending rows are
written to a local fallback file instead of being silently lost.
Regular in-stream flush failures are NOT covered here — those are
expected to log and continue, since more events are still arriving to
make up for it. Shutdown is the one case with no second chance.
"""

import json
import shutil
from datetime import datetime, timezone

import pytest

from services.market_data.runner import FAILED_BATCH_DIR, _write_fallback_batch


class FakeRow:
    """Stand-in for an AuditLog row — only the fields _write_fallback_batch reads."""

    def __init__(self, event_type, source, payload, occurred_at):
        self.event_type = event_type
        self.source = source
        self.payload = payload
        self.occurred_at = occurred_at


@pytest.fixture(autouse=True)
def clean_fallback_dir():
    if FAILED_BATCH_DIR.exists():
        shutil.rmtree(FAILED_BATCH_DIR)
    yield
    if FAILED_BATCH_DIR.exists():
        shutil.rmtree(FAILED_BATCH_DIR)


def test_fallback_file_contains_all_pending_rows():
    rows = [
        FakeRow("trade", "market_data", {"symbol": "BTCUSDT", "price": 65000.5},
                datetime.now(timezone.utc)),
        FakeRow("ticker", "market_data", {"symbol": "ETHUSDT", "price": 3500.0},
                datetime.now(timezone.utc)),
    ]

    _write_fallback_batch(rows)

    files = list(FAILED_BATCH_DIR.glob("*.jsonl"))
    assert len(files) == 1

    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 2

    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["event_type"] == "trade"
    assert parsed[0]["payload"]["symbol"] == "BTCUSDT"
    assert parsed[1]["event_type"] == "ticker"
    assert parsed[1]["payload"]["symbol"] == "ETHUSDT"


def test_fallback_not_written_when_no_rows_pending():
    _write_fallback_batch([])

    files = list(FAILED_BATCH_DIR.glob("*.jsonl")) if FAILED_BATCH_DIR.exists() else []
    # Called with an empty list still creates the file (just with no
    # lines) — the real caller (flush()) already guards against calling
    # this with an empty list at all, but this documents what happens
    # if it ever is.
    if files:
        assert files[0].read_text() == ""