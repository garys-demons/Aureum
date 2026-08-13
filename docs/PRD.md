# Product Requirements Document (PRD)

## Project
Aureum – Live Market Data Collection Module

**Version:** 2.0 (revised post-audit)
**Author:** Hansika Saini
**Sprint:** Phase 1 – Data Collection
**Status:** Approved for implementation

---

## 1. Introduction

### Purpose
The Live Market Data Collection Module continuously collects real-time cryptocurrency market data from the Binance Testnet exchange, standardizes it, validates it, and forwards it to downstream services (strategy engine, execution, analytics, AI reasoning, dashboard).

### Problem Statement
Cryptocurrency prices change within milliseconds. Historical datasets can't support live trading decisions. The system needs a component that maintains a persistent exchange connection and continuously delivers current market state.

---

## 2. Objectives

1. Establish a persistent WebSocket connection with Binance Testnet.
2. Receive trade, order book, ticker, and candle events with bounded latency (see §6).
3. Validate every incoming message before it enters the system.
4. Convert exchange-specific messages into standardized internal models.
5. Recover from disconnects **without corrupting order-book state** and **without silently duplicating or dropping events**.
6. Provide reliable, de-duplicated data to downstream modules.

---

## 3. Scope

**In scope:** WebSocket connection management, live event collection, validation, standardization, forwarding, reconnection, order-book reconciliation after reconnect, deduplication.

**Out of scope:** trading strategy, order execution, risk management, portfolio management, AI prediction, user interface.

---

## 4. Functional Requirements

Each requirement includes an explicit, testable acceptance criterion.

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-1 | Connect to Binance Testnet via WebSocket | Connection reaches `OPEN` state within 5s of attempt under normal network conditions; failure logged with reason if not. |
| FR-2 | Subscribe to configured market data streams | For every symbol in `config/exchange.yaml`, a subscription confirmation is received and logged within 5s of connection open; unconfirmed subscriptions are retried once, then logged as an error. |
| FR-3 | Receive live Trade Events | Every `trade`-type message received is parsed into a `TradeEvent` or explicitly rejected+logged; no message is silently dropped. |
| FR-4 | Receive live Order Book updates | Snapshot fetched via REST on connect/reconnect; deltas applied only when `first_update_id` is contiguous with local state (see TRD §6.1); non-contiguous deltas trigger a resync, not silent application. |
| FR-5 | Receive live Ticker Events | Parsed into `TickerEvent`; malformed tickers rejected+logged, not silently dropped. |
| FR-6 | Receive live Candle updates | Parsed into `Candle`; `is_closed` field must correctly distinguish in-progress vs. final bars per interval. |
| FR-7 | Validate every incoming message | Any message failing Pydantic validation is logged with the raw payload (minus any auth-adjacent fields) and discarded; validation failure never raises an unhandled exception. |
| FR-8 | Convert exchange JSON into internal event models | 1:1 mapping documented in Backend Schema v2.0; no field silently dropped without being explicitly marked "not mapped." |
| FR-9 | Automatically reconnect on disconnect | Reconnect attempted with exponential backoff (1s initial, 2x multiplier, 60s cap — see `config/exchange.yaml`); after reconnect, order book state is resynced per FR-4 before deltas resume processing. |
| FR-10 | Forward validated events to downstream services | Events forwarded via the documented forwarding contract (App Flow v2.0 §3); forwarding failure is logged and does not crash the ingestion loop. |
| FR-11 *(new)* | De-duplicate events | Duplicate `(exchange, symbol, trade_id)` trade events, and duplicate order-book updates by `update_id`, are detected and dropped before forwarding. |
| FR-12 *(new)* | Handle partial stream failure | If one stream (e.g. order book) disconnects while others (e.g. trades) remain connected, only the affected stream is resynced; unaffected streams continue uninterrupted. |
| FR-13 *(new)* | Reject unrecognized/incompatible payload shapes loudly | If Binance changes a payload shape such that expected fields are missing, the module logs a structured error identifying the unexpected shape rather than silently coercing or dropping fields. |

---

## 5. Non-Functional Requirements

| Requirement | Target |
|---|---|
| **Latency** | End-to-end (exchange `event_time` → forwarded to downstream) under 200ms at p95 under normal load on Testnet. |
| **Reliability** | Reconnects within backoff schedule (max 60s between attempts); order book resync completes within 5s of reconnect. |
| **Scalability** | Adding a second exchange requires only a new `ExchangeAdapter` implementation — no changes to `core/` or downstream consumers. |
| **Maintainability** | `services/market_data` contains no import from `core/strategy` or `core/risk` (enforced by code review / lint rule). |
| **Extensibility** | New event types added as new Pydantic models without modifying existing ones. |
| **Data Integrity** | No duplicate events forwarded (FR-11); no order-book corruption across reconnects (FR-4, FR-9). |

---

## 6. Latency & Performance Targets
- p95 end-to-end latency: **< 200ms**
- Order book resync after reconnect: **< 5s**
- Reconnect attempt cadence: **1s → 60s exponential backoff, 2x multiplier**

---

## 7. Stakeholders

| Stakeholder | Responsibility | Owner |
|---|---|---|
| Market Data Module | Collect, validate, forward live data | Hansika |
| Vault / Logging | Structured logging, persistence, anomaly detection | Aryan |
| Bot / Execution | Consume signals, place orders | Gauri |
| AI Reasoning + Review & Risk | Strategy interface, PR review, risk register | Samarth |

---

## 8. Dependencies
Binance Spot Testnet · WebSocket API · Internet connectivity · Python 3.12+ · Pydantic · Aureum core infra (`config/exchange.yaml`, shared DB).

## 9. Assumptions
- Binance Testnet remains accessible during Phase 1.
- Incoming messages follow Binance's documented WS spec (deviations are treated as errors per FR-13, not silently handled).
- Downstream modules consume events via the contract defined in App Flow v2.0 §3.

## 10. Constraints
- Market data availability is bound by exchange uptime.
- Testnet liquidity/behavior differs from production — order book depth and trade frequency may be thin, which is acceptable for Phase 1 validation purposes.

## 11. Success Criteria
- Continuous live data reception for a sustained test window (≥ 1 hour) with zero unhandled crashes.
- Order book remains internally consistent across at least one forced reconnect during testing (verified against a REST snapshot comparison).
- Zero duplicate events observed downstream during a sustained test window.
- All FRs (§4) pass their stated acceptance criteria.

## 12. Deliverables
- `BinanceAdapter` (WebSocket client with reconnect + resync)
- `MarketEvent`, `TradeEvent`, `OrderBookSnapshot`, `OrderBookDelta`, `Candle`, `TickerEvent` (Backend Schema v2.0)
- Deduplication layer
- Order-book reconciliation logic
- Unit + integration + failure test suite (Testing Strategy, TRD v2.0 §12)
- This documentation set

## 13. Future Enhancements
Multi-exchange support · historical replay mode · message compression · advanced monitoring · real-time metrics dashboard · Kafka-based streaming.

---
*End of Document*
