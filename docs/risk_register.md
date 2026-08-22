# Aureum — Risk Register

Running log of risks, gaps, and issues found during review. Owned by Review & Risk (Samarth).

**Severity:** Low = worth knowing · Medium = should fix soon · High = fix before proceeding
**Status:** Open · Fixed · Accepted (known, deliberately not fixing now) · PR pending

| Date | Found in | Issue | Severity | Status |
|------|----------|-------|----------|--------|
| 2026-08-06 | Aryan PR #2 | `aiosqlite` used in tests but not declared in `pyproject.toml` | Medium | Fixed |
| 2026-08-06 | Aryan PR #2 | `SENSITIVE_KEYS` was a fixed exact-match set — secrets under unlisted key names weren't redacted | Low | **Fixed (PR #21)** — normalized substring matching, catches `apiKey`, `my_api_secret`, `AUTH-TOKEN-2`, etc. |
| 2026-08-06 | Aryan PR #2 | Redaction never tested against realistic secret values | Low | **Fixed (PR #21)** |
| 2026-08-06 | `scripts/setup.sh` | Used `python` (Windows-specific) | Low | **Fixed (PR #21)** — now `python3` |
| 2026-08-07 | Live connect test | `received_time` earlier than `event_time` — clock skew | Medium | Fixed — system clock synced |
| 2026-08-07 | Security (forward-looking) | Testnet API keys not yet created — withdrawal permissions must be disabled when added | Medium | Open |
| 2026-08-07 | DB / persistence | Shared DB had zero tables | High | Fixed (PR #14) |
| 2026-08-07 | Integration gap | Live data streamed to console only, never persisted | High | Fixed (PR #14) |
| 2026-08-07 | Gauri executor | Hardcoded `quantity=0.001` on every order | High | Fixed (PR #16) |
| 2026-08-07 | Gauri executor | No risk-check step — violated Strategy → Risk → Execution | High | Fixed (PR #16) — no-op seam in place, real logic is Phase 6 |
| 2026-08-07 | Gauri executor | Module-level `Client()` at import time | Medium | Fixed (PR #16) |
| 2026-08-07 | Gauri executor | `python-binance` not declared in `pyproject.toml` | Medium | Fixed |
| 2026-08-07 | Gauri executor | `python-binance` pulls deprecated websockets APIs, conflicts with Hansika's usage | Medium | Open — cosmetic warnings only, no functional issue observed |
| 2026-08-08 | `core/persistence/db.py` | Three undocumented `.env` fixes needed for the Timescale URL to work | Medium | **Fixed (PR #21)** — `db.py` now auto-normalizes `DATABASE_URL` |
| 2026-08-08 | `runner.py` | Per-event commit caused compounding backlog (55s and climbing) | High | Fixed (`fix/batch-persistence-writes`) — batched commits |
| 2026-08-08 | `runner.py` | Shutdown flush failed with `PendingRollbackError`, losing the final batch | Medium | **Partially fixed (`fix/shutdown-shield`)** — order_book stream shuts down cleanly; market_data stream still hits `ResourceClosedError` on manual Ctrl+C because loop teardown closes the DB connection mid-commit. Fallback file catches the data either way. Proper fix needs a SIGINT handler doing orderly shutdown before loop teardown |
| 2026-08-08 | `runner.py` | No tests at all | Medium | Fixed — `test_runner.py`, `test_runner_fallback.py` |
| 2026-08-08 | Infrastructure / DB | Timescale free tier is US-only — ~20s round-trip lag from India | High | **Accepted for Phase 1.** Measured 2-4s during the 1-hour sustained run after batching (not 20s+ — that was pre-batching). Still over the 200ms target; deferred to Phase 9 |
| 2026-08-08 | Infrastructure / DB | On a 22-day trial, not free tier — need a plan for expiry | Medium | Open |
| 2026-08-08 | `services/market_data` | `order_book.py` was dead code — no depth subscription, no reconciliation call | High | **Fixed** — `stream_order_book()` implemented, verified live (reconciliation, forced reconnect, 0 sequence gaps over 1hr), audited, 4 further issues found and fixed in `fix/order-book-audit-findings` (see below) |
| 2026-08-09 | `order_book.py` audit | `apply()` checked `is_live`, not set until a full reconciled batch is applied — deltas 2..n in the batch were validated against the wrong rule, a gap inside a batch could slip through | High | Fixed — tracks `_any_applied` separately, regression test added |
| 2026-08-09 | `order_book.py` audit | Unused import (`parse_order_book_delta`) | Low | Fixed |
| 2026-08-09 | `order_book.py` audit | `reconcile()` assumed buffer order == sequence order, unstated | Low | Fixed — defensive sort added |
| 2026-08-09 | `models.py` audit | `SnapshotSource.RECONCILED` specified but never emitted | Low | Documented — `OrderBook` never serializes back to a snapshot; reserved for future use |
| 2026-08-11 | Latency measurement | Occasional negative lag on `depth_update` rows — residual clock offset | Low | Open |
| 2026-08-11 | Docs | **v2.0 doc revisions (reconciliation procedure, FR-11/12/13, composite dedup keys) were drafted after the documentation audit but never committed** — repo stayed on v1.0 while the team built against v2.0 requirements from memory | High | **Fixed** — v2.0 adopted (`docs/adopt-v2-revisions`, merged) |
| 2026-08-12 | `services/market_data` | FR-6: kline stream never subscribed — same dead-code pattern order_book had | High | Fixed (PR #22, Aryan) |
| 2026-08-13 | Process | PR #21's commit message ("risk register cleanup") didn't actually touch `risk_register.md` — real fixes existed in code but weren't reflected here for two days | Low | Fixed — this update |
| 2026-08-15 | Process | `git push` silently failed after committing the order-book restore fix, leaving `dev` broken for hours. Hansika, Aryan, and Samarth each independently ran diagnostics before discovering the root cause: the push simply hadn't gone through (confirmed via `git branch -vv` showing "ahead 1"). No error was visible in the original session's output | Medium | Fixed — pushed successfully; process gap remains. Team should verify every push with `git log origin/<branch> --oneline -3` before telling anyone something's fixed, rather than trusting silent success |
| 2026-08-17 | Gauri feature engine | `rolling_volatility()` and `rsi()` don't document which output index corresponds to which input timestamp — a downstream consumer naively aligning `output[0]` with `input[0]` would introduce look-ahead bias, since `output[0]` is actually computed using data through index `window-1`. Not a math bug, an unstated alignment contract | Medium | Open |
| 2026-08-17 | Hansika historical.py | `_parse_raw_kline` hardcodes `is_closed=True` for every historical candle with no check against current time — if fetched close to "now," the in-progress candle could be mislabeled as final, poisoning feature computations downstream | Medium | Open |
| 2026-08-17 | Hansika historical.py | `find_candle_gaps` can't distinguish a duplicate open_time from a real gap | Low | Open |
| 2026-08-17 | Aryan research/storage.py | Race condition in save_dataset — _next_version() read and the version directory creation aren't atomic, so two concurrent saves for the same dataset could silently overwrite each other. Fix: mkdir(exist_ok=False) | Medium | Open |
| 2026-08-17 | Aryan research/storage.py | load_dataset(version="latest") isn't pinned — re-running the same code later can silently load different underlying data if a new version was saved in between, undermining reproducibility. Worth requiring explicit version pins in feature-computation code | Low | Open |
| 2026-08-19 | Hansika backtest engine | Engine's `_update_order_book()` calls `OrderBook.apply_delta()` with no contiguity check, despite `order_book_state.py`'s own docstring stating `apply_delta()` trusts the caller to have already verified it. A sequence gap in historical data would silently corrupt book state for the rest of a backtest run, with strategy decisions based on wrong data and no error surfaced | High | Open |
| 2026-08-19 | Process | Paper-exchange revert (70476fb) and its conflict-resolution merge (1e8b3ea, PR #39) accidentally deleted unrelated Phase 3 files (feature engine, historical downloader, 37 tests). Only partially restored — risk register came back, the rest didn't. Went undetected because test count dropped (189→152) with zero failures, not caught until a manual git log review | High | Fixed — files restored from 975646c, verified 203 passing. Process gap: reverts/conflict-resolution merges should be diffed against the pre-incident commit before merging, not just checked for passing tests |
| 2026-08-22 | BaselineMarketMaker (Phase 5) | Baseline strategy consistently lost money across all 3 independent evaluation windows (4-7% win rate). Root cause traced through two ruled-out hypotheses (signal accumulation in run_baseline_evaluation.py's loop, statefulness in candle_fill_model.py) to the actual cause: base_half_spread (0.0005) too tight relative to ADA's real intra-candle volatility, causing frequent same-candle round trips where fees + adverse movement exceeded captured spread | High | Fixed — retuned to base_half_spread=0.001, verified profitable across all 3 windows (20-46 fills each, positive return in every window). Official phase5_baseline result: +0.16% return, 89.36% win rate, 46 trades |

---

## Phase 1 Exit Criteria — Status (updated 2026-08-13)

| Criterion | Status |
|---|---|
| Tables exist in shared DB | ✅ Verified |
| Live data persists to Postgres | ✅ Verified (9,559 rows, 1hr run) |
| Continuous run ≥1hr, zero unhandled crashes | ✅ Verified |
| Order book consistent across forced reconnect | ✅ Verified live — backoff, reconciliation, 0 gaps |
| Zero duplicate events during sustained run | ✅ Verified — 0 duplicates across 9,559 rows |
| All 13 FRs pass acceptance criteria | ◐ 8 pass, FR-6 now fixed pending re-audit, FR-2/8/12/13 partial, FR-11 needs re-check against committed v2.0 text |
| p95 latency < 200ms | ⚠️ Accepted deviation — 2-4s measured, deferred to Phase 9 |

## Phase 2 Exit — Status (2026-08-15)

| Criterion | Status |
|---|---|
| Replay harness proves book stays synchronized | ✅ Verified — `test_replay.py`, including reconnect-boundary case, against a real captured fixture |
| Microstructure metrics implemented + tested | ✅ Verified — microprice, depth-weighted price, imbalance, hand-calculated test values |
| FR-12 (partial stream failure) closed properly | ✅ Verified — `test_fr12_isolation.py`, direct test rather than architectural inference |
| Live pipeline runs clean end to end | ✅ Verified — 9,952 rows, all 5 event types persisted, clean shutdown |
| Tests passing | ✅ 109/109 |