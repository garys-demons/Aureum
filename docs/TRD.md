# Technical Requirements Document (TRD)

## Project
Project Compass – Live Market Data Collection Module

Version: 1.0

Author: Hansika Saini

Sprint: Phase 1 – Data Collection

Status: Draft

---

# 1. Purpose

The Live Market Data Collection Module is responsible for establishing and maintaining a persistent WebSocket connection with the Binance Spot Testnet exchange. The module continuously receives real-time market events, validates incoming messages, converts exchange-specific JSON payloads into standardized internal event models, and forwards these validated events to downstream services.

This module serves as the primary entry point for all real-time market information within the Project Compass platform.

---

# 2. System Overview

The module is responsible for the following:

- Establishing a secure WebSocket connection
- Maintaining persistent communication with Binance Testnet
- Receiving market events in real time
- Parsing JSON messages
- Validating message structure
- Creating standardized event objects
- Forwarding validated events to the remaining system
- Recovering automatically from temporary connection failures

---

# 3. Technology Stack

| Component | Technology |
|------------|------------|
| Programming Language | Python 3.12+ |
| Communication Protocol | WebSocket |
| Exchange | Binance Spot Testnet |
| Data Format | JSON |
| Validation | Pydantic |
| Testing | Pytest |
| Logging | Structlog (Project Standard) |

---

# 4. Architecture

                Binance Spot Testnet
                        │
                WebSocket Connection
                        │
                        ▼
               Binance Adapter (binance.py)
                        │
                 Receive JSON Messages
                        │
                        ▼
                JSON Parsing & Validation
                        │
                        ▼
              Pydantic Event Models
                        │
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
 TradeEvent       OrderBookEvent     CandleEvent
                        │
                        ▼
               Downstream Services

---

# 5. Module Responsibilities

The module performs the following responsibilities:

1. Open a WebSocket connection.
2. Subscribe to market data streams.
3. Receive live JSON messages.
4. Detect message type.
5. Validate incoming data.
6. Convert messages into internal models.
7. Forward validated events.
8. Handle connection failures.
9. Reconnect automatically.

---

# 6. Components

## 6.1 Binance Adapter

File:
services/market_data/adapters/binance.py

Responsibilities

- Open WebSocket connection
- Subscribe to streams
- Receive live events
- Parse JSON
- Handle reconnects
- Manage backoff
- Forward validated events

---

## 6.2 MarketEvent

Purpose

Base model representing a generic market event.

Responsibilities

- Store common fields
- Timestamp every event
- Provide common interface for all event types

---

## 6.3 TradeEvent

Purpose

Represents a completed market trade.

Responsibilities

- Store symbol
- Store trade price
- Store traded quantity
- Store trade timestamp

---

## 6.4 OrderBookSnapshot

Purpose

Represents the complete Level-2 order book at a specific point in time.

Responsibilities

- Store all bid levels
- Store all ask levels
- Maintain order book state

---

## 6.5 OrderBookDelta

Purpose

Represents incremental updates to the order book.

Responsibilities

- Store only modified bid levels
- Store only modified ask levels
- Reduce bandwidth usage
- Update local order book efficiently

---

## 6.6 Candle

Purpose

Represents an OHLCV candle.

Responsibilities

- Open Price
- High Price
- Low Price
- Close Price
- Volume
- Start Time
- End Time

---

## 6.7 TickerEvent

Purpose

Represents the latest market summary.

Responsibilities

- Last Price
- 24 Hour High
- 24 Hour Low
- Volume
- Price Change

---

# 7. Data Flow

Step 1

Application starts.

↓

Step 2

Configuration files are loaded.

↓

Step 3

Binance Adapter initializes.

↓

Step 4

WebSocket connection is established.

↓

Step 5

Subscription requests are sent.

↓

Step 6

Exchange begins streaming JSON messages.

↓

Step 7

Incoming JSON is parsed.

↓

Step 8

Message type is identified.

↓

Step 9

Corresponding Pydantic model is created.

↓

Step 10

Validation succeeds.

↓

Step 11

Validated event is forwarded.

↓

Step 12

Process repeats continuously.

---

# 8. WebSocket Lifecycle

CONNECT

↓

Handshake Successful

↓

Subscribe to Streams

↓

Receive Events

↓

Validate Events

↓

Forward Events

↓

Connection Lost?

↓

No → Continue Streaming

Yes → Retry Connection

↓

Reconnect

↓

Resume Streaming

---

# 9. Error Handling

The module handles the following errors:

### Connection Failure

Action

Attempt automatic reconnection using exponential backoff.

---

### Invalid JSON

Action

Discard message and log validation error.

---

### Unsupported Event Type

Action

Ignore unsupported event and continue processing.

---

### Timeout

Action

Reconnect after timeout period.

---

### Unexpected Exception

Action

Log exception and restart WebSocket connection safely.

---

# 10. Logging Strategy

The module shall log:

- Connection established
- Connection closed
- Reconnection attempts
- Subscription success
- Invalid messages
- Parsing failures
- Unexpected exceptions

Logging follows the project-wide Structlog configuration.

---

# 11. Testing Strategy

The following tests will be implemented:

Unit Tests

- Model validation
- JSON parsing
- Event creation

Integration Tests

- Successful WebSocket connection
- Stream subscription
- Live event reception

Failure Tests

- Connection loss
- Invalid JSON
- Reconnect logic

---

# 12. Performance Requirements

The module should:

- Maintain continuous WebSocket connection
- Process incoming messages with minimal latency
- Recover quickly from temporary failures
- Avoid duplicate event processing

---

# 13. Security Considerations

- Use Binance Testnet credentials securely.
- Do not expose API keys.
- Validate all incoming messages.
- Reject malformed data.

---

# 14. Risks

| Risk | Mitigation |
|------|------------|
| Network Failure | Automatic reconnect |
| Exchange Downtime | Retry with exponential backoff |
| Invalid Messages | Validation using Pydantic |
| High Data Volume | Efficient event processing |

---

# 15. Future Enhancements

- Multi-exchange support
- Historical replay mode
- Event compression
- Advanced monitoring
- Metrics dashboard
- Kafka-based event streaming

---

# End of Document