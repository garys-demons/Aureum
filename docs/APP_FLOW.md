# Application Flow

## Aureum – Live Market Data Collection Module
**Version:** 2.0 (revised post-audit)

---

## 1. Cold Start Flow (initial connection)

```
Application Start
      │
      ▼
Load Configuration (config/exchange.yaml, .env)
      │
      ▼
Initialize Binance Adapter
      │
      ▼
Start two independent tasks:
  - market data stream (ticker + trade)
  - order book stream (depth)
      │
      ▼
For the order-book stream specifically:
Subscribe → buffer deltas → fetch REST snapshot (once) → reconcile (TRD §6.1)
      │
      ▼
Receive JSON (all streams, book stream now "live")
      │
      ▼
Identify Event Type
      │
      ▼
Deduplicate (TRD §7)
      │
      ▼
Validate Data
      │
      ▼
Create Pydantic Model
      │
      ▼
Forward Event (see §3 — Forwarding Contract)
      │
      ▼
Repeat
```

---

## 2. Reconnect Flow (distinct from cold start)

Reconnection is **not** a simple loop back to cold start. It differs by stream:

### 2.1 Trade / Ticker / Candle stream reconnect
```
Connection Lost (this stream only)
      │
      ▼
Log disconnect + reason
      │
      ▼
Backoff (per config/exchange.yaml: 1s → 60s, 2x multiplier)
      │
      ▼
Reconnect → Resubscribe → Resume forwarding
```

### 2.2 Order-book stream reconnect (materially different — requires reconciliation)
```
Connection Lost (book stream)
      │
      ▼
Log disconnect + reason
      │
      ▼
Backoff
      │
      ▼
Reconnect
      │
      ▼
Mark book stream state = "reconciling" (NOT yet "live")
      │
      ▼
Full reconciliation procedure (TRD §6.1):
  Buffer live deltas → fetch fresh REST snapshot (once) →
  keep buffering until a delta bridges it → apply in contiguous order
      │
      ▼
Reconciliation succeeds? ──No──▶ Keep buffering; re-snapshot only if
      │ Yes                       the buffer runs away (stale snapshot)
      ▼
Mark book stream state = "live"
      │
      ▼
Resume normal forwarding
```

**Why this matters:** other streams are stateless/append-only, so "resubscribe and resume" is correct for them. The order book is cumulative state — resuming without reconciliation risks a book that looks structurally valid but has silently missed updates. This is the single highest-risk path in the module and is drawn separately rather than folded into a generic "reconnect" arrow.

---

## 3. Forwarding Contract

Validated, deduplicated events are forwarded via async generators exposed by the adapter:

- `stream_market_data(symbols)` — yields `TickerEvent` / `TradeEvent`
- `stream_order_book(symbol)` — yields `(OrderBookDelta, OrderBook)` tuples, so consumers can persist the delta and read current book state without re-deriving it

`services/market_data/runner.py` consumes both as independent `asyncio` tasks, batching writes to the persistence layer.

**Phase 1 scope:** one process, in-memory generators — no external message bus (Kafka, etc.); that's explicitly a Future Enhancement (TRD §16).

**Contract guarantees to downstream consumers:**
- Every event yielded has already passed validation and deduplication.
- Order-book events are only yielded once the book stream is in "live" (reconciled) state — never during reconciliation.
- Forwarding failure (e.g. a DB commit failing) is logged; it does not crash the ingestion loop, and does not block other streams' event delivery.

---

## 4. Shutdown Flow

```
Shutdown Signal Received (e.g. SIGINT)
      │
      ▼
Stop accepting new events from all streams
      │
      ▼
Flush any in-flight/buffered events to the database (shielded from
cancellation so the final commit can complete)
      │
      ▼
If the final flush fails: write pending rows to a JSON-lines fallback
file rather than losing them
      │
      ▼
Log final state per stream
      │
      ▼
Process exits
```

Distinguish this from a **disconnect** (§2), which is unplanned and triggers reconnection; shutdown is planned and triggers cleanup instead.

**Known limitation:** on manual Ctrl+C the event loop begins tearing down before the shielded flush can always complete, so the final batch on one stream may land in the fallback file rather than the database. A SIGINT handler performing an orderly shutdown before loop teardown is the proper fix.

---

## 5. End State
The application continuously processes validated, deduplicated market events — with the order book held to a stricter reconciliation guarantee than other streams — until a shutdown signal is received, at which point it exits per §4.

---
*End of Document*
