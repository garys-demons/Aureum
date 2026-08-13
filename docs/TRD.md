# Technical Requirements Document (TRD)

## Project
Aureum – Live Market Data Collection Module

**Version:** 2.0 (revised post-audit)
**Author:** Hansika Saini
**Sprint:** Phase 1 – Data Collection
**Status:** Approved for implementation

---

## 1. Purpose
Establish and maintain a persistent WebSocket connection with Binance Spot Testnet; receive, validate, standardize, and forward real-time market events; recover from failures **without corrupting state or duplicating data**.

---

## 2. System Overview
- Establish and maintain WS connection
- Receive market events in real time across independently-tracked streams (trade, book, ticker, candle)
- Parse, validate, standardize into Pydantic models
- De-duplicate before forwarding
- Reconstruct order-book state correctly across reconnects
- Forward validated events via a defined contract (App Flow v2.0)

---

## 3. Technology Stack
| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Protocol | WebSocket + REST (for order book snapshot + historical) |
| Exchange | Binance Spot Testnet |
| Data Format | JSON |
| Validation | Pydantic |
| Testing | Pytest, pytest-asyncio |
| Logging | Structlog (project standard) |

---

## 4. Architecture

```
                Binance Spot Testnet
                        │
        ┌───────────────┴────────────────┐
        │                                 │
   WebSocket (live)                 REST (snapshot/backfill)
        │                                 │
        ▼                                 ▼
              Binance Adapter (binance.py)
                        │
          Per-stream connection state tracker
          (trade / book / ticker / candle — tracked independently)
                        │
                 Receive JSON Messages
                        │
                        ▼
                JSON Parsing & Validation
                        │
                        ▼
        Deduplication (trade_id / update_id keyed)
                        │
                        ▼
              Pydantic Event Models
      ┌─────────────────┼──────────────────┬───────────────┐
      ▼                 ▼                  ▼               ▼
 TradeEvent      OrderBookSnapshot/   CandleEvent     TickerEvent
                     Delta
                        │
                        ▼
          Forwarding Contract (see App Flow §3)
                        │
                        ▼
               Downstream Services
```

**Import boundary (explicit):** `services/market_data` must not import from `core/strategy` or `core/risk`. This mirrors the isolation already enforced for `core/risk` in the master architecture, and prevents circular dependencies as the codebase grows. Enforce via code review; a lint rule (e.g. `import-linter`) is a Phase 2+ nice-to-have.

---

## 5. Module Responsibilities
1. Open WebSocket connection; track each subscribed stream's state independently.
2. Subscribe to market data streams; confirm each subscription.
3. Receive live JSON messages.
4. Detect message type.
5. Validate incoming data.
6. De-duplicate by `(exchange, symbol, trade_id)` for trades and `update_id` for book deltas.
7. Convert messages into internal models.
8. Forward validated events per the App Flow contract.
9. Detect and handle **per-stream** connection failure (not monolithic — see §6).
10. Reconnect automatically with defined backoff.
11. **Reconcile order-book state after any book-stream reconnect** (see §6.1) before resuming delta processing.

---

## 6. Reconnection & Reconciliation Procedure

This is the highest-risk part of the module: an incorrectly resumed order book looks valid but isn't, and every strategy/risk decision built on top of it inherits that corruption silently.

### 6.1 Order Book Reconciliation (mandatory procedure)
1. On initial connect **or** any book-stream reconnect, do **not** resume applying deltas immediately.
2. Subscribe to the depth stream and begin buffering incoming deltas.
3. Fetch a fresh full order book snapshot via REST (`/api/v3/depth`), recording its `last_update_id`. **Fetch once** — re-fetching on each failed reconcile attempt is a trap: every new snapshot is newer than the buffered deltas, so they are all filtered out and reconciliation can never converge.
4. Discard any buffered delta where `final_update_id <= snapshot.last_update_id` (already reflected in the snapshot).
5. The first delta applied must satisfy: `delta.first_update_id <= snapshot.last_update_id + 1 <= delta.final_update_id`. If no buffered delta satisfies this yet, keep buffering — do not apply a delta with a gap.
6. Once the first valid delta is applied, apply all subsequent deltas in order, verifying each one's `first_update_id == previous.final_update_id + 1`. Any gap triggers a return to step 2 (full resync), not a skip-and-continue. Note this contiguity rule applies from the *second* delta onward, including the remainder of the batch returned by `reconcile()` — not only after the book is marked live.
7. Only after step 6 completes does the book stream mark itself "live" and resume normal forwarding.

This procedure is implemented in `BinanceAdapter.stream_order_book()` and `services/market_data/order_book.py`, not left as an implicit consequence of "resubscribe."

### 6.2 Per-Stream Failure Handling *(FR-12)*
Trade, ticker, and candle streams do **not** require the reconciliation procedure above (they're append-only/stateless per message) — on reconnect they simply resubscribe and resume. Only the order-book stream requires §6.1. Each stream runs on its own WebSocket connection with its own DB session, so a book-stream reconnect doesn't interrupt trade/ticker/candle flow.

### 6.3 Backoff Parameters (single source of truth)
Defined in `config/exchange.yaml`: 1s initial, 2x multiplier, 60s cap. This TRD does not restate the numbers to avoid drift — refer to config for current values.

### 6.4 Ownership of Sequence-Gap Detection
**Decision:** Sequence-gap detection for the order book (`update_id` contiguity, §6.1 step 6) is owned by `services/market_data`, since it requires direct access to in-flight stream state.

Aryan's sequence-gap detection is scoped to **general structured-logging-level anomaly detection** (e.g., unexpected gaps in `received_time` deltas, connection drop frequency) — a monitoring concern, not the correctness-critical reconciliation logic in §6.1.

---

## 7. Deduplication *(FR-11)*
- **Trades:** dedup key = `(exchange, symbol, trade_id)`. Bounded recent-keys cache (deque + set, default 10,000 entries) to detect duplicates without unbounded memory growth.
- **Order book deltas:** inherently deduplicated by the contiguity check in §6.1 step 6 — a delta with an already-applied `final_update_id` is rejected as non-contiguous.
- **Tickers/Candles:** naturally idempotent (latest value wins); no dedup key needed, but candle `is_closed` transitions should not be forwarded twice for the same `(symbol, interval, open_time)`.

---

## 8. Components

### 8.1 Binance Adapter
File: `services/market_data/adapters/binance.py`
Responsibilities: connection lifecycle, per-stream state tracking, subscription, parsing, reconciliation (§6.1), backoff, forwarding.

### 8.2 Order Book
File: `services/market_data/order_book.py`
`fetch_snapshot()` (REST), `reconcile()` (§6.1 steps 4-6), and `OrderBook` (local bid/ask state with contiguity enforcement).

### 8.3 MarketEvent and subtypes
Base model. Common fields: `event_type`, `symbol`, `exchange`, `event_time`, `received_time`. All child models inherit these — see Backend Schema v2.0 for full field definitions, composite uniqueness keys, and inheritance structure.

---

## 9. Data Flow
1. App starts → 2. Config loaded → 3. Adapter initializes → 4. WS connects → 5. Subscriptions sent → 6. Exchange streams JSON → 7. JSON parsed → 8. Message type identified → 9. Dedup check (§7) → 10. Pydantic model created → 11. Validation → 12. Event forwarded (App Flow §3) → 13. Repeat.

**Reconnect path (distinct from cold start for the book stream):** Disconnect detected → per-stream backoff (§6.3) → reconnect → **if book stream:** reconciliation procedure (§6.1) before resuming step 9; **if trade/ticker/candle stream:** resubscribe and resume directly at step 9.

---

## 10. Error Handling
| Error | Action |
|---|---|
| Connection failure (any stream) | Reconnect with exponential backoff, independently per stream. |
| Invalid JSON | Discard message, log with payload (see §11 on what's safe to log). |
| Unsupported event type | Log at debug level, ignore, continue processing. |
| Timeout | Treated as connection failure — reconnect. |
| Unexpected exception | Log with full traceback, restart the affected stream's connection safely (not the whole process). |
| Non-contiguous order book delta | Trigger full reconciliation (§6.1), not skip. |
| Duplicate event detected | Drop silently at debug-log level (expected/normal under reconnect, not an error). |

---

## 11. Logging Strategy
Log: connection established/closed (per stream), reconnection attempts + backoff duration, subscription confirmations, invalid messages (payload minus sensitive fields), parsing failures, dedup drops (debug level), reconciliation start/end + outcome, unexpected exceptions with traceback.

**Explicit rule:** never log raw WS auth headers, signatures, or API secrets, even at debug level. Enforced in code via a Structlog processor (`scrub_sensitive_data` in `core/logging_config.py`), not left to individual call sites.

---

## 12. Testing Strategy

### Unit Tests
- Model validation: reject price ≤ 0, quantity ≤ 0, invalid timestamp
- Reject `OrderBookDelta` where `first_update_id > final_update_id`
- Dedup: second occurrence of identical `trade_id` is dropped; bounded cache evicts oldest
- `OrderBook`: bridging delta accepted, gaps rejected, quantity-0 removes level
- JSON parsing: malformed payload doesn't raise unhandled exception

### Integration Tests
- Successful WS connection + subscription
- Full snapshot + delta stream reconciliation produces a correct in-memory book
- **Simulated disconnect mid-delta-stream → reconnect → reconciliation completes → book state is provably consistent** (the single most important test in this module)
- Independent stream failure: book stream disconnects, trade stream unaffected and continues forwarding

### Failure Tests
- Connection loss → reconnect → backoff timing matches config
- Invalid JSON mid-stream → client continues processing subsequent valid messages
- Non-contiguous delta → triggers reconciliation, not silent gap

---

## 13. Performance Requirements
- p95 end-to-end latency < 200ms (PRD §6)
- Order book reconciliation completes within 5s of reconnect
- No duplicate events forwarded downstream
- Memory-bounded dedup cache (not unbounded growth over long-running sessions)

---

## 14. Security Considerations
- API keys loaded from environment variables only (`config/exchange.yaml` references env var names, never literal values).
- Never log raw auth headers/signatures (§11).
- Validate all incoming messages before use.
- Reject malformed data rather than attempting to coerce it.

---

## 15. Risks
| Risk | Mitigation |
|---|---|
| Network failure | Per-stream automatic reconnect with backoff |
| Exchange downtime | Retry with exponential backoff, capped |
| Invalid messages | Pydantic validation, reject + log |
| High data volume | Bounded dedup cache, batched DB writes |
| Order book corruption on reconnect | Mandatory reconciliation procedure (§6.1) |
| Silent duplicate events | Explicit dedup keys (§7) |

---

## 16. Future Enhancements
Multi-exchange support · historical replay mode · event compression · advanced monitoring · metrics dashboard · Kafka-based event streaming.

---
*End of Document*
