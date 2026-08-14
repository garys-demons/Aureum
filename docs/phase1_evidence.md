\# Aureum — Phase 1 Exit Evidence



\*\*Phase 1: Data Spine.\*\* Exit criteria per PRD v2.0 §11.

Evidence collected 2026-08-11 unless noted.



\---



\## Criterion 1 — Tables exist, data persists to Postgres



`audit\_log` and `alembic\_version` present in the shared Timescale instance

(Alembic migration `72ee7f2c863c`, PR #14).



Verified: 9,559 rows persisted during the sustained run below.



\## Criterion 2 — Live order book (FR-4)



Depth stream subscribed on a dedicated WebSocket connection; TRD §6.1

reconciliation procedure runs on connect and on every reconnect.



Verified live: `book\_reconciled` with `depth=(439, 672)`, best bid/ask

65239.16 / 65239.17, spread 0.01. 2,934 `depth\_update` rows persisted.



\## Criterion 3 — Per-stream independence (FR-12)



Market data (trade/ticker) and order book run as separate asyncio tasks,

each with its own WebSocket connection and DB session. Verified by

independent flush timestamps in `batch\_committed` logs.



\## Criterion 4 — Order book consistent across a forced reconnect



\*\*Method:\*\* network adapter disabled mid-run via

`netsh interface set interface "Wi-Fi" admin=disable`, \~60s downtime.



\*\*Observed:\*\*

\- Both streams detected disconnect (`no close frame received or sent`)

\- Backoff sequence 1 → 2 → 4 → 8 → 16 → 32s, matching TRD §6.3

\- On reconnect: state went to `reconciling`, NOT straight to live

\- Fresh REST snapshot fetched (`last\_update\_id=3009190`)

\- `reconciliation\_successful`, then `order\_book\_live` at 3009194

\- Normal forwarding resumed, no sequence-gap errors afterward



This is the criterion the reconciliation procedure exists for: the book

did not resume applying deltas to stale state.



\## Criterion 5 — Zero duplicate events



Query per Backend Schema v2.0 dedup keys — `(exchange, symbol, trade\_id)`

for trades, `(exchange, symbol, final\_update\_id)` for depth updates.



\*\*Result:\*\* 0 duplicate trades, 0 duplicate depth updates, across 9,559 rows.



\## Criterion 6 — Continuous 1-hour run, zero unhandled crashes



\*\*Run:\*\* 2026-08-11, \~18:28–19:28 UTC.



| Metric | Value |

|---|---|

| Total rows | 9,559 |

| trade | 4,919 |

| depth\_update | 2,934 |

| ticker | 1,706 |

| Duplicate events | 0 |

| Sequence gaps in persisted depth updates | \*\*0\*\* |

| Unhandled crashes | 0 |



Zero sequence gaps across the full hour means every depth update received

while connected was applied contiguously and persisted.



\## Criterion 7 — All 13 FRs pass acceptance criteria



\*\*Status: outstanding.\*\* See `docs/phase1\_fr\_audit.md`.



\---



\## Accepted deviations



\*\*Latency.\*\* PRD §6 targets p95 < 200ms end-to-end. Measured 2–4s during

the sustained run. Root cause is network distance: the Timescale free tier

is US-only (us-east-1) and the team is in India. This is not a code defect —

per-event committing previously caused a \*compounding\* backlog (55s and

climbing), which was fixed by batching; what remains is fixed round-trip

distance. \*\*Accepted for Phase 1\*\* (the goal is pipeline correctness, not

speed) and \*\*must be revisited before Phase 9\*\* (paper trading), where

latency affects results. Options then: paid tier in ap-south-1, local

Postgres, or co-located deployment.



\## Known issues at Phase 1 exit



\- Shutdown flush on the `market\_data` stream fails on manual Ctrl+C

&#x20; (`ResourceClosedError`) — loop teardown closes the DB connection

&#x20; mid-commit. Affects only the final batch; rows recovered to a fallback

&#x20; JSONL file. Proper fix is a SIGINT handler doing orderly shutdown.

\- Fallback file occasionally written twice for the same batch.

\- Sub-second latency figures are not fully trustworthy (occasional negative

&#x20; lag from residual clock offset vs Binance `event\_time`).



Full list in `docs/risk\_register.md`.

