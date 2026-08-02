# Application Flow Document

## Project

Project Compass – Live Market Data Collection Module

Version: 1.0

Author: Hansika Saini

Sprint: Phase 1 – Data Collection

Status: Draft

---

# 1. Purpose

This document describes the complete execution flow of the Live Market Data Collection Module. It explains how the application establishes a connection with the Binance Spot Testnet exchange, receives real-time market data, validates incoming messages, converts them into standardized internal models, and forwards them to downstream services.

---

# 2. High-Level Application Flow

Application Start
        │
        ▼
Load Configuration Files
        │
        ▼
Initialize Market Data Module
        │
        ▼
Create Binance Adapter
        │
        ▼
Connect to Binance WebSocket
        │
        ▼
Connection Successful?
      /      \
    Yes       No
     │         │
     │    Retry Connection
     │         │
     └─────────┘
        │
        ▼
Subscribe to Required Streams
        │
        ▼
Receive Live JSON Messages
        │
        ▼
Determine Event Type
        │
        ▼
Validate Incoming Data
        │
        ▼
Create Pydantic Event Model
        │
        ▼
Forward Validated Event
        │
        ▼
Wait For Next Message
        │
        ▼
Repeat Until Application Stops

---

# 3. Detailed Flow

## Step 1 – Application Startup

The application starts and initializes all required project components. The market data service is prepared for execution.

Output

Market Data Module initialized.

---

## Step 2 – Load Configuration

The application loads configuration files containing exchange settings, WebSocket endpoints, symbols, and runtime parameters.

Examples

- Exchange configuration
- Trading symbols
- WebSocket URL
- Retry settings

Output

Configuration successfully loaded.

---

## Step 3 – Initialize Binance Adapter

The Binance Adapter is created.

Its responsibilities include:

- Managing the WebSocket connection
- Receiving live market data
- Handling reconnection
- Parsing exchange messages

Output

Adapter ready.

---

## Step 4 – Establish WebSocket Connection

The adapter attempts to establish a persistent WebSocket connection with Binance Spot Testnet.

Possible Outcomes

Success

Proceed to subscription.

Failure

Retry connection using exponential backoff.

Output

Connected to exchange.

---

## Step 5 – Subscribe to Market Streams

Once connected, the adapter subscribes to all required live market streams.

Subscribed Streams

- Trade Stream
- Order Book Stream
- Ticker Stream
- Candle Stream

Output

Subscriptions successful.

---

## Step 6 – Receive Live Messages

The exchange continuously sends market updates.

Incoming messages are received in JSON format.

Examples

- Trade execution
- Price updates
- Order book updates
- Candle updates

Output

Raw JSON message received.

---

## Step 7 – Identify Event Type

Each incoming message is inspected to determine its event type.

Supported Events

- TradeEvent
- OrderBookSnapshot
- OrderBookDelta
- Candle
- TickerEvent

Output

Event successfully identified.

---

## Step 8 – Validate Incoming Data

The received JSON message is validated using Pydantic models.

Validation checks include:

- Required fields
- Correct data types
- Missing values
- Invalid values

If validation fails:

- Log error
- Ignore invalid message
- Continue processing

Output

Validated event.

---

## Step 9 – Convert Into Internal Models

Validated JSON is converted into standardized internal event objects.

Examples

Raw Exchange JSON

↓

TradeEvent

TickerEvent

OrderBookDelta

Candle

Output

Internal event object created.

---

## Step 10 – Forward Event

Validated event objects are forwarded to downstream services.

Consumers include:

- Strategy Engine
- Trading Module
- Dashboard
- AI Reasoning Module
- Data Storage

Output

Event successfully delivered.

---

## Step 11 – Continuous Streaming

The application continues receiving market events until shutdown.

The following cycle repeats continuously:

Receive

↓

Validate

↓

Convert

↓

Forward

↓

Receive Next Event

---

## Step 12 – Connection Loss

If the WebSocket connection is interrupted:

The application

- Detects disconnection
- Logs the failure
- Waits according to retry policy
- Attempts reconnection
- Restores subscriptions
- Resumes streaming

No manual intervention is required.

---

## Step 13 – Application Shutdown

When the application is stopped:

- Close WebSocket connection
- Release resources
- Flush logs
- Exit gracefully

---

# 4. Sequence Flow

Application

↓

Configuration

↓

Binance Adapter

↓

WebSocket Connection

↓

Subscribe Streams

↓

Receive JSON

↓

Validate

↓

Create Event Models

↓

Forward Events

↓

Repeat

↓

Shutdown

---

# 5. Decision Points

### Connection Successful?

Yes

↓

Continue

No

↓

Retry Connection

---

### Valid JSON?

Yes

↓

Create Event

No

↓

Discard Message

---

### Supported Event?

Yes

↓

Process Event

No

↓

Ignore Event

---

# 6. Error Recovery Flow

Connection Lost

↓

Log Error

↓

Wait

↓

Reconnect

↓

Restore Streams

↓

Resume Collection

---

# 7. End State

The application remains in a continuous event-processing loop until manually stopped. During execution, all incoming market data is validated, standardized, and forwarded to downstream modules while maintaining a reliable WebSocket connection.

---

# End of Document