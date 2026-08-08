# Aureum — Risk Register

Running log of risks, gaps, and issues found during review. Owned by Review & Risk (Samarth).

**Severity:** Low = worth knowing · Medium = should fix soon · High = fix before proceeding
**Status:** Open · Fixed · Accepted (known, deliberately not fixing now) · PR pending

| Date | Found in | Issue | Severity | Status |
|------|----------|-------|----------|--------|
| 2026-08-06 | Aryan PR #2 | `aiosqlite` used in tests but not declared in `pyproject.toml` — tests fail on clean install | Medium | Fixed |
| 2026-08-06 | Aryan PR #2 | `SENSITIVE_KEYS` is a fixed exact-match set — a secret logged under an unlisted key name won't be redacted | Low | Open |
| 2026-08-06 | Aryan PR #2 | `SENSITIVE_KEYS` redaction never tested against real secret values (only empty strings so far) | Low | Open |
| 2026-08-06 | `scripts/setup.sh` | Uses `python` (Windows-specific); breaks on Mac/Linux where `python3` is standard | Low | Open |
| 2026-08-07 | Live connect test | `received_time` appeared ~1600ms earlier than `event_time` — local clock skew vs Binance. Resolved by syncing system clock | Medium | Fixed |
| 2026-08-07 | Security (forward-looking) | Testnet API keys not yet created — when added, must have withdrawal permissions disabled | Medium | Open |
| 2026-08-07 | DB / persistence | Shared Timescale DB had zero tables — `models.py` defined schemas but no migration had ever run against the real database. Persistence tests passed only because they use in-memory SQLite | High | Fixed (Aryan PR #14) |
| 2026-08-07 | Integration gap | Live market data streamed to console only, never persisted — zero references to `record_event()` in `services/market_data` | High | Fixed (Aryan PR #14, `runner.py`) |
| 2026-08-07 | Gauri executor | Hardcoded `quantity=0.001` on every order regardless of signal, symbol, price, or balance — no position sizing | High | PR pending |
| 2026-08-07 | Gauri executor | No risk-check step — violated the Strategy → Risk → Execution architectural invariant | High | PR pending |
| 2026-08-07 | Gauri executor | Module-level `Client()` created at import time — hit network on import, made tests require patching | Medium | PR pending |
| 2026-08-07 | Gauri executor | `python-binance` imported but not declared in `pyproject.toml` — same class of bug as `aiosqlite` | Medium | Fixed |
| 2026-08-07 | Gauri executor | `python-binance` pulls deprecated websockets APIs, conflicting with Hansika's modern `websockets` usage. Consider httpx REST for order placement instead | Medium | Open |
| 2026-08-08 | `core/persistence/db.py` | Three undocumented `.env` fixes needed to make the Timescale connection string work: `postgres`→`postgresql`, add `+asyncpg`, strip `?sslmode=require`. Each fails with a different cryptic error. Should be normalized in `db.py` or documented in `.env.example` | Medium | Open |
| 2026-08-08 | `runner.py` | Per-event session + commit + refresh caused a compounding backlog — lag grew ~3s per event, reaching 55s within minutes. Fixed with batched commits | High | PR pending (`fix/batch-persistence-writes`) |
| 2026-08-08 | `runner.py` | Shutdown flush fails with `PendingRollbackError` if a prior flush left the session broken — final batch of events is lost. Graceful shutdown (App Flow §4) not fully guaranteed | Medium | Open |
| 2026-08-08 | `runner.py` | No tests at all — this is the seam that was silently broken for days | Medium | Open |
| 2026-08-08 | Infrastructure / DB | Timescale free tier is US-only (us-east-1). From India, writes take 8-19s, giving ~20s end-to-end lag vs PRD target of p95 <200ms. NOT a code defect — batching fixed the compounding part; this is network distance. Accepted for Phase 1 (goal is correctness, not speed). MUST revisit before Phase 9 (paper trading). Options: paid tier in ap-south-1, local Postgres, or co-located deployment | High | Accepted — deferred to Phase 9 |
| 2026-08-08 | Infrastructure / DB | Currently on a 22-day trial with $1,000 credit, not the free tier. Need a plan for what happens at expiry | Medium | Open |
| 2026-08-08 | `services/market_data` | `order_book.py` is dead code — no `@depth` subscription, no REST snapshot fetch, no reconciliation call anywhere in `binance.py` or `runner.py`. Reconciliation has never run against real data, only fixtures. Blocks FR-4, FR-12, and the PRD §11 forced-reconnect criterion | High | Open — Hansika |

---

## Phase 1 Exit Criteria — Status

| Criterion | Status |
|---|---|
| Tables exist in shared DB | ✅ Verified |
| Live data persists to Postgres | ✅ Verified (209 rows) |
| Continuous run ≥1hr, zero unhandled crashes | ❌ Not attempted |
| Order book consistent across forced reconnect | ❌ Blocked — order book not wired |
| Zero duplicate events during sustained run | ❌ Not verified against real data |
| All 13 FRs pass acceptance criteria | ❌ Not audited |
| p95 latency < 200ms | ⚠️ Accepted deviation — see infrastructure entry |