# Backend Schema Document

## Project

Project Compass – Live Market Data Collection Module

Version: 1.0

Author: Hansika Saini

Sprint: Phase 1 – Data Collection

Status: Draft

---

# 1. Purpose

The Backend Schema defines the standardized internal data models used by the Live Market Data Collection Module. Incoming exchange messages are transformed into these models after validation. Standardizing the schema ensures that all downstream services consume market data in a consistent format regardless of the source exchange.

---

# 2. Schema Overview

The module defines the following primary models:

- MarketEvent
- TradeEvent
- OrderBookSnapshot
- OrderBookDelta
- Candle
- TickerEvent

Relationship

MarketEvent
│
├── TradeEvent
├── OrderBookSnapshot
├── OrderBookDelta
├── Candle
└── TickerEvent

---

# 3. MarketEvent

## Purpose

MarketEvent is the base model for all market-related events. It contains fields that are common across all event types.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| event_type | String | Type of market event |
| symbol | String | Trading pair (e.g., BTCUSDT) |
| exchange | String | Source exchange |
| event_time | Integer | Exchange event timestamp (Unix milliseconds) |
| received_time | Integer | Local timestamp when event was received |

---

# 4. TradeEvent

## Purpose

Represents a completed trade executed on the exchange.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| trade_id | Integer | Exchange trade identifier |
| symbol | String | Trading pair |
| price | Float | Executed trade price |
| quantity | Float | Quantity traded |
| buyer_maker | Boolean | Indicates whether buyer is the market maker |
| trade_time | Integer | Trade execution timestamp |

---

# 5. OrderBookSnapshot

## Purpose

Represents the complete Level-2 order book at a specific point in time. This model is generally created using a REST snapshot before applying live updates.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| symbol | String | Trading pair |
| last_update_id | Integer | Snapshot update identifier |
| bids | List[List[Float]] | Bid price levels with quantities |
| asks | List[List[Float]] | Ask price levels with quantities |
| snapshot_time | Integer | Snapshot timestamp |

Example

Bid

Price → Quantity

118250.50 → 2.4 BTC

Ask

118251.00 → 1.8 BTC

---

# 6. OrderBookDelta

## Purpose

Represents incremental updates to the order book received through the WebSocket stream.

Instead of sending the complete order book repeatedly, the exchange sends only the levels that changed.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| symbol | String | Trading pair |
| first_update_id | Integer | First update ID |
| final_update_id | Integer | Last update ID |
| bids | List[List[Float]] | Updated bid levels |
| asks | List[List[Float]] | Updated ask levels |
| event_time | Integer | Exchange event timestamp |

Example

Previous Order Book

Bid

118250 → 2 BTC

Incoming Delta

118250 → 3 BTC

Only this single change is transmitted.

---

# 7. Candle

## Purpose

Represents an OHLCV candle for a fixed time interval.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| symbol | String | Trading pair |
| interval | String | Candle interval (1m, 5m, 1h, etc.) |
| open_time | Integer | Candle start timestamp |
| close_time | Integer | Candle close timestamp |
| open | Float | Opening price |
| high | Float | Highest price |
| low | Float | Lowest price |
| close | Float | Closing price |
| volume | Float | Trading volume |
| is_closed | Boolean | Indicates whether candle is complete |

---

# 8. TickerEvent

## Purpose

Represents a real-time summary of market statistics for a trading pair.

### Fields

| Field | Type | Description |
|---------|---------|-------------------------------|
| symbol | String | Trading pair |
| last_price | Float | Latest traded price |
| price_change | Float | Absolute price change |
| price_change_percent | Float | Percentage price change |
| high_price | Float | Highest price in last 24 hours |
| low_price | Float | Lowest price in last 24 hours |
| volume | Float | Trading volume |
| event_time | Integer | Exchange event timestamp |

---

# 9. Data Validation Rules

The following validation rules shall be enforced.

## Symbol

- Must not be empty.
- Must follow exchange naming convention.

---

## Price

- Must be greater than zero.
- Floating point value.

---

## Quantity

- Must be greater than zero.

---

## Timestamp

- Must be a valid Unix timestamp in milliseconds.

---

## Bid and Ask Levels

- Price must be positive.
- Quantity must be non-negative.

---

# 10. Model Relationships

MarketEvent

↓

TradeEvent

↓

Represents completed trades

--------------------------------

MarketEvent

↓

OrderBookSnapshot

↓

Represents initial order book

--------------------------------

MarketEvent

↓

OrderBookDelta

↓

Represents incremental updates

--------------------------------

MarketEvent

↓

TickerEvent

↓

Represents market summary

--------------------------------

MarketEvent

↓

Candle

↓

Represents OHLCV market data

---

# 11. Serialization Format

Incoming exchange messages are received in JSON format.

Example

{
    "symbol": "BTCUSDT",
    "price": 118250.50,
    "quantity": 0.42
}

↓

Validated using Pydantic

↓

Converted into internal event models

↓

Forwarded to downstream services

---

# 12. Future Extensions

The schema has been designed to support future enhancements including:

- Multi-exchange integration
- Additional market event types
- Futures market data
- Options market data
- Depth levels beyond Level-2
- Exchange-independent standardized schemas

---

# End of Document