# Implementation Plan

## Aureum – Live Market Data Collection Module
**Version:** 2.0 (revised post-audit)
**Author:** Hansika Saini
**Sprint:** Phase 1 – Data Collection
**Status:** Approved for implementation

---

## 1. Purpose
Development roadmap for the Live Market Data Collection Module — phases, milestones, deliverables, dependencies, and testing strategy for a reliable real-time market data pipeline.

---

## 2. Objectives
Same as PRD v2.0 §2 — persistent connection, bounded-latency event collection, validation, standardization, reconnection **without state corruption or duplication**, reliable downstream delivery.

---

## 3. Development Phases

> **Note on ordering:** phase order matches the team's sprint plan (schemas before WS client). The v1.0 plan had WebSocket Infrastructure before Event Models, which meant building a client before the data shapes it needs to construct existed.

**Phase 1 — Research and Planning**
Study Binance WebSocket API, market streams, JSON structures (including the depth-snapshot REST endpoint needed for order-book reconciliation — TRD §6.1). Prepare dev environment.

**Phase 2 — Event Model Development**
Develop standardized Pydantic models per Backend Schema v2.0 (includes composite keys and explicit inheritance). Write model-level unit tests **as they're built**, not deferred.

**Phase 3 — WebSocket Infrastructure**
Implement the Binance WebSocket client, persistent connection, subscription, verify live message reception against the Phase 2 models.

**Phase 4 — Data Validation & Deduplication**
Validate incoming JSON, reject malformed messages (FR-7), implement dedup layer (TRD §7), structured logging (TRD §11, including the "never log secrets" rule).

**Phase 5 — Reliability & Reconciliation**
Write the integration test for "reconnect mid-delta-stream → reconciliation → consistent book state" as an executable spec first. Then implement:
- Per-stream failure detection (not monolithic)
- Exponential backoff (per `config/exchange.yaml`)
- Order-book reconciliation procedure (TRD §6.1)
- Verify the pre-written test now passes.

**Phase 6 — Remaining Test Coverage**
Fill in remaining unit/integration/failure tests not already covered incrementally (see TRD §12).

**Phase 7 — Integration**
Integrate with persistence, dashboard, and downstream consumers via the Forwarding Contract (App Flow v2.0 §3).

---

## 4. Milestones

| Milestone | Expected Outcome | Status |
|---|---|---|
| Research Completed | Binance API, including depth-snapshot endpoint, understood | ☑ |
| Event Models Completed | All schemas implemented + unit tested | ☑ |
| WebSocket Connected | Stable live connection across streams | ☑ |
| Validation & Dedup Completed | Incoming data verified; duplicates dropped | ☑ |
| Reliability Completed | Reconnection + reconciliation implemented and verified live | ☑ |
| Remaining Tests Completed | Full test suite passing | ◐ |
| Integration Completed | End-to-end data flow to persistence | ☑ |

---

## 5. Dependencies
Binance Spot Testnet availability · stable internet · Python 3.12+ · Pydantic · Pytest/pytest-asyncio · Aureum repository · shared Timescale Cloud DB · `config/exchange.yaml`.

---

## 6. Risks
| Risk | Mitigation |
|---|---|
| Network interruption | Per-stream automatic reconnect |
| Exchange downtime | Retry with exponential backoff |
| Invalid JSON | Validation layer |
| API changes | Adapter abstraction + loud failure on unrecognized shape (FR-13) |
| High message volume | Bounded dedup cache, batched DB writes |
| **Order book corruption on reconnect** | Reconciliation procedure (TRD §6.1), verified live |
| **Silent duplicates** | Explicit dedup keys (TRD §7), verified over 9,559 real rows |

---

## 7. Success Criteria
Same as PRD v2.0 §11 — sustained 1-hour live run with zero unhandled crashes, order book consistency verified across a forced reconnect, zero duplicate events downstream, all FRs pass acceptance criteria.

---

## 8. Completion Checklist

**Legend:** `☐` Not started · `◐` In progress · `☑` Done

| Task | Status |
|---|---|
| Binance API Research (incl. depth snapshot endpoint) | ☑ |
| MarketEvent / TradeEvent / TickerEvent Models | ☑ |
| OrderBookSnapshot / OrderBookDelta Models | ☑ |
| Candle Model | ☑ |
| WebSocket Client (ticker + trade) | ☑ |
| WebSocket Client (depth / order book) | ☑ |
| WebSocket Client (kline / candles) | ☐ |
| Data Validation | ☑ |
| Deduplication Layer | ☑ |
| Reconnection + Reconciliation Logic | ☑ |
| Per-stream independence (FR-12) | ☑ |
| Unit Tests | ☑ |
| Integration Tests (automated) | ☐ |
| Failure Tests (automated) | ☐ |
| Sustained 1-hour run | ☑ |
| Forced-reconnect verification | ☑ |
| Documentation | ☑ *(this revision)* |

---

## 9. Future Enhancements
Multi-exchange support · historical replay mode · Kafka-based event streaming · advanced monitoring dashboard · performance metrics collection · additional market event types.

---
*End of Document*
