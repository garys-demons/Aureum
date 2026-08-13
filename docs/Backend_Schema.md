# Backend Schema Document

## Aureum – Live Market Data Collection Module
**Version:** 2.0 (revised post-audit)
**Author:** Hansika Saini
**Sprint:** Phase 1 – Data Collection
**Status:** Approved for implementation

---

## 1. Purpose
Defines the standardized internal data models used by the Live Market Data Collection Module. Incoming exchange messages are transformed into these models after validation. Standardizing the schema ensures downstream services consume market data consistently regardless of source exchange.

---

## 2. Schema Overview
Primary models: `MarketEvent` (base), `TradeEvent`, `OrderBookSnapshot`, `OrderBookDelta`, `Candle`, `TickerEvent` — all inherit from `MarketEvent`, enforced at the model level, not just implied by the architecture diagram.

**Shared type:** `PriceLevel` — replaces raw `List[List[float]]` for bid/ask data with a self-documenting structure.

---

## 3. MarketEvent (base — all child models inherit these fields)

| Field | Type | Description |
|---|---|---|
| `event_type` | String | Type of market event |
| `exchange` | String | Source exchange (e.g. `"binance"`) — **inherited by all children** |
| `symbol` | String | Trading pair |
| `event_time` | Integer | Exchange timestamp (ms) |
| `received_time` | Integer | Local receive timestamp (ms) — **present on every child model via inheritance** |

---

## 4. PriceLevel

| Field | Type | Description |
|---|---|---|
| `price` | Float (≥ 0) | Price at this level |
| `quantity` | Float (≥ 0) | Quantity at this price. **0 means the level is removed**, not "zero quantity present" — Binance delta semantics. |

---

## 5. TradeEvent (extends MarketEvent)

| Field | Type | Description |
|---|---|---|
| `trade_id` | Integer | Exchange trade identifier |
| `price` | Float (> 0) | Executed trade price |
| `quantity` | Float (> 0) | Executed quantity |
| `buyer_maker` | Boolean | Buyer is market maker |
| `trade_time` | Integer | Trade timestamp (ms) |

**Uniqueness key:** `(exchange, symbol, trade_id)` — composite, since `trade_id` alone is not guaranteed unique across exchanges or symbols. This is the dedup key referenced in TRD §7.

---

## 6. OrderBookSnapshot (extends MarketEvent)

| Field | Type | Description |
|---|---|---|
| `last_update_id` | Integer | Snapshot update id |
| `bids` | List[PriceLevel] | Bid levels |
| `asks` | List[PriceLevel] | Ask levels |
| `snapshot_time` | Integer | Snapshot timestamp (ms) |
| `source` | Enum(`"rest_full"`, `"reconciled"`) | Distinguishes a fresh REST-fetched snapshot from one reconstructed in-memory after reconciliation |

**Uniqueness key:** `(exchange, symbol, last_update_id)`.

**Implementation note:** only `rest_full` is currently produced. `OrderBook` maintains state in memory and never serialises itself back to an `OrderBookSnapshot`, so nothing emits `reconciled` yet. Reserved for when book state needs persisting or serving to the dashboard.

---

## 7. OrderBookDelta (extends MarketEvent)

| Field | Type | Description |
|---|---|---|
| `first_update_id` | Integer | First update id in this delta |
| `final_update_id` | Integer | Final update id in this delta |
| `bids` | List[PriceLevel] | Updated bid levels |
| `asks` | List[PriceLevel] | Updated ask levels |

**Uniqueness key:** `(exchange, symbol, final_update_id)`.

**Validation rule:** `first_update_id <= final_update_id` — enforced by a Pydantic `model_validator`, rejecting construction outright.

---

## 8. Candle (extends MarketEvent)

| Field | Type | Description |
|---|---|---|
| `interval` | String | `1m`, `5m`, `1h`, etc. |
| `open_time` | Integer | Open timestamp (ms) |
| `close_time` | Integer | Close timestamp (ms) |
| `open` / `high` / `low` / `close` | Float (> 0) | OHLC prices |
| `volume` | Float (≥ 0) | Volume |
| `is_closed` | Boolean | Whether this bar is final (`true`) or still in progress (`false`) |

**Uniqueness key:** `(exchange, symbol, interval, open_time, is_closed)` — the `is_closed` component allows the in-progress and final versions of the same bar to coexist without key collision.

---

## 9. TickerEvent (extends MarketEvent)

| Field | Type | Description |
|---|---|---|
| `last_price` | Float (> 0) | Latest traded price |
| `price_change` | Float | Absolute change |
| `price_change_percent` | Float | Percentage change |
| `high_price` | Float (> 0) | 24h high |
| `low_price` | Float (> 0) | 24h low |
| `volume` | Float (≥ 0) | 24h volume |

**Uniqueness key:** none required — latest value per `(exchange, symbol)` always wins.

---

## 10. Data Validation Rules
- `symbol` must not be empty.
- `price`, `quantity` must be greater than zero (where applicable).
- Timestamps must be valid Unix ms integers.
- `PriceLevel.price` and `PriceLevel.quantity` must both be ≥ 0 (quantity may legitimately be 0 to represent a removed level).
- `OrderBookDelta.first_update_id <= final_update_id` (§7).
- All child models carry `exchange` and `received_time` via inheritance from `MarketEvent` (§3).

---

## 11. Storage Mapping

Phase 1 persists all events to a single `audit_log` table (`core/persistence/models.py`), keyed by category and event type rather than one table per event type:

| Column | Notes |
|---|---|
| `id` | UUID |
| `category` | `event` / `decision` / `execution` / `anomaly` |
| `event_type` | `trade`, `ticker`, `depth_update`, `kline`, etc. |
| `source` | Originating module, e.g. `market_data` |
| `payload` | Full serialized event as JSON |
| `occurred_at` | Exchange-side event time |
| `recorded_at` | Local write time |

Payloads are validated against the corresponding Pydantic model before writing (`EVENT_TYPE_MODEL_MAP` in `repository.py`). Splitting into per-type tables (`market_events`, `candles`, `order_book_snapshots`) is deferred to a later phase.

---

## 12. Future Extensions
Multi-exchange support (the `exchange` field is already in place) · futures market data · options data · historical replay mode · additional event types · per-event-type tables.

---
*End of Document*
