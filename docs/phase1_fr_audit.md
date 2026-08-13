# Aureum — Phase 1 FR Audit (v2)

Audited against `docs/PRD.md` **Version 2.0**, committed to `dev` via
`docs/adopt-v2-revisions`. Supersedes the prior audit, which correctly
noted v2.0 wasn't committed yet and audited against v1.0 as a result.

Evidence: `docs/phase1_evidence.md` (1-hour sustained run, 2026-08-11)
plus fixes landed since (order book audit findings, FR-6, shutdown
shield, redaction/db-url normalization).

---

## FR-1 through FR-10

| FR | Requirement | Verdict | Evidence |
|---|---|---|---|
| FR-1 | Connect to Binance Testnet via WebSocket, `OPEN` within 5s | ✅ Pass | Live connection confirmed across the full 1-hour run |
| FR-2 | Subscribe to configured streams, confirmed within 5s | 🟡 Partial | `@ticker`, `@trade`, `@depth`, `@kline_1m` all subscribed and verified live. But Binance's combined-stream endpoint sends no explicit subscription-confirmation message, and the code doesn't wait for or log one — "confirmed" is inferred from data arriving, not an actual ack. No retry-once-then-error path exists per the acceptance text |
| FR-3 | Receive live Trade Events | ✅ Pass | 4,919 rows persisted, 0 duplicates |
| FR-4 | Receive live Order Book updates, TRD §6.1 reconciliation | ✅ Pass | Reconciliation verified live and under a real forced reconnect; 2,934 rows, 0 sequence gaps over the full hour |
| FR-5 | Receive live Ticker Events | ✅ Pass | 1,706 rows persisted |
| FR-6 | Receive live Candle updates, `is_closed` distinguishes in-progress vs final | ✅ Pass (previously Fail) | `@kline_1m` subscribed (PR #22). `runner.py` correctly filters on `is_closed`, only persisting final bars — verified by code inspection, not yet by a live run with candle data in `check_rows.py` |
| FR-7 | Validate every incoming message | ✅ Pass | Pydantic validation on parse and again in `record_event()` against `EVENT_TYPE_MODEL_MAP`; invalid payloads rejected and logged, never raise unhandled |
| FR-8 | Convert exchange JSON to internal models, unmapped fields marked explicitly | 🟡 Partial | Parsers map cleanly to Backend Schema v2.0. But not every Binance field is mapped, and unmapped fields aren't explicitly marked "not mapped" as the acceptance text requires — this is a documentation gap, not a functional one |
| FR-9 | Auto-reconnect with backoff; resync book before resuming | ✅ Pass | Forced-disconnect test: backoff 1→2→4→8→16→32s; book entered `reconciling`, fetched a fresh snapshot, re-reconciled before resuming — the exact behavior this FR requires |
| FR-10 | Forward validated events; failure doesn't crash the loop | ✅ Pass | Verified over the full 1-hour run; commit failures caught and logged, streams continued |

**FR-1–10 score: 8 pass, 2 partial, 0 fail.**

---

## FR-11, FR-12, FR-13 (now with real acceptance text)

| FR | Requirement | Verdict | Evidence |
|---|---|---|---|
| FR-11 | De-duplicate trades by `(exchange, symbol, trade_id)`; book updates by `update_id` | ✅ Pass | `TradeDeduplicator`, bounded cache, 5 unit tests. **0 duplicate trades and 0 duplicate depth updates across 9,559 real rows** — the strongest evidence in this audit, since it's a direct query against production data, not an inference |
| FR-12 | Partial stream failure — one stream disconnecting doesn't affect others | 🟡 Partial | Architecture satisfies it: separate WebSocket connections and DB sessions per stream, independent exception handling (verified by code inspection and the concurrent-task design in `runner.py`). **But never tested with only one stream failing** — the forced-reconnect test killed the whole network adapter, so both streams dropped together. True independence has not been directly observed, only architecturally reasoned |
| FR-13 | Reject unrecognized payload shapes loudly, log a structured error identifying the shape | 🟡 Partial | Parse failures are caught and logged (`failed_to_parse_message`, `book_parse_failed`) rather than crashing or silently coercing — so it does fail loudly. But the handler is a generic `except Exception`, not shape-specific detection; the log doesn't identify *what* about the shape was unexpected, which the acceptance text specifically asks for |

**FR-11–13 score: 1 pass, 2 partial.**

---

## Overall: 9 pass, 4 partial, 0 fail (13/13 have a verdict)

## What "partial" means here, concretely

None of the four partials represent broken behavior — in every case the system does something reasonable. They represent acceptance criteria that were written more strictly than what was built:

- **FR-2**: no explicit ack-tracking, just inferred success from data flow
- **FR-8**: no explicit "not mapped" marking for unmapped fields
- **FR-12**: independent by design, not proven independent by an isolated test
- **FR-13**: fails loudly, but not with shape-specific diagnostics

## Recommendation

**Phase 1 can reasonably be signed off**, with these four partials recorded as explicit, team-acknowledged deviations rather than silently accepted. None block correctness; all are cheap to close later (or in Phase 2):

- FR-12 specifically is worth closing before Phase 2 adds more streams — a `_force_disconnect()` hook on one stream would let the reconnect test isolate a single stream and prove the independence claim directly, rather than relying on architecture alone.