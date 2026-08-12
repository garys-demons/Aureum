# Aureum — Phase 1 FR Audit

Audited against `docs/PRD.md` **Version 1.0** — the only committed
version at time of audit. FR-11, FR-12, and FR-13 are referenced
elsewhere (code comments, risk register, `phase1_evidence.md`) but have
no written acceptance text in any committed doc. This is flagged
explicitly per FR below rather than silently assumed.

Evidence dated 2026-08-11, from `docs/phase1_evidence.md`
(`fix/shutdown-shield` branch) unless noted otherwise.

---

## FR-1 through FR-10 (PRD v1.0 §5)

| FR | Requirement (verbatim) | Status | Evidence |
|---|---|---|---|
| FR-1 | Connect to Binance Testnet using WebSocket. | ✅ Pass | Live connection confirmed across the full 1-hour sustained run |
| FR-2 | Subscribe to supported market data streams. | 🟡 Partial | `@ticker`, `@trade`, `@depth` all subscribed and verified live. `@kline` still not subscribed — see FR-6 |
| FR-3 | Receive live Trade Events. | ✅ Pass | 4,919 trade rows persisted during the sustained run, 0 duplicates |
| FR-4 | Receive live Order Book updates. | ✅ Pass | TRD §6.1 reconciliation verified live — `book_reconciled` with real depth/spread data; 2,934 `depth_update` rows persisted, 0 sequence gaps across the full hour |
| FR-5 | Receive live Ticker Events. | ✅ Pass | 1,706 ticker rows persisted during the sustained run |
| FR-6 | Receive live Candle updates. | ❌ Fail | `@kline` still never subscribed anywhere in `binance.py` — same dead-code pattern the order book had before it was fixed. `parse_candle_event()` exists but has never run against real data |
| FR-7 | Validate every incoming message. | ✅ Pass | Pydantic validation on parse + `record_event()`'s validation against `EVENT_TYPE_MODEL_MAP` before persisting |
| FR-8 | Convert exchange JSON into internal event models. | ✅ Pass | `parsers.py`, confirmed via `test_parsers.py` and live data matching expected shapes |
| FR-9 | Automatically reconnect when the WebSocket connection is interrupted. | ✅ Pass | Real forced-reconnect test performed (network adapter disabled ~60s mid-run) — backoff sequence 1→2→4→8→16→32s observed correctly, reconciliation ran on reconnect, no stale-state bugs |
| FR-10 | Forward validated events to downstream services. | ✅ Pass | `runner.py` → `record_event()`/`stage_event()` chain — 9,559 total rows persisted during the sustained run |

**Score: 8 pass, 1 fail, 1 partial.**

---

## FR-11, FR-12, FR-13

**No written acceptance text exists for these in any committed doc**,
checked directly across all six files in `docs/` on this branch —
confirmed still all Version 1.0.

| FR | What's known (informally) | Status |
|---|---|---|
| FR-11 | No reference found anywhere — code, comments, risk register, or evidence doc | ⚠️ Cannot audit — no text, no inferable meaning |
| FR-12 | Inferred from a `runner.py` code comment ("one stream failing must not take the other down") and `phase1_evidence.md` Criterion 3, which verifies market data and order book run as independent tasks with independent flush timestamps | 🟡 Behavior verified live, but against an *inferred* requirement, not a documented one |
| FR-13 | No reference found anywhere | ⚠️ Cannot audit — no text, no inferable meaning |

---

## What's blocking a fully complete audit

1. **The v2.0 docs were never actually committed**, despite `phase1_evidence.md` itself citing "PRD v2.0 §11" and "Backend Schema v2.0" as if they exist. All 5 docs remain Version 1.0.
2. Once v2.0 is committed, **this audit should be re-run against the new text in full** — not just for FR-11/12/13, since existing FR wording may also change between versions.
3. FR-6 (candle/kline) remains a real, unresolved gap — same category of bug the order book had, not yet fixed.