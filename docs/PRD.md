Product Requirements Document (PRD)
Project

Project Compass – Live Market Data Collection Module

Version: 1.0

Author: Hansika Saini

Sprint: Phase 1 – Data Collection

Status: Draft

1. Introduction
Purpose

The Live Market Data Collection Module is responsible for continuously collecting real-time cryptocurrency market data from the Binance Testnet exchange. This module serves as the primary source of live market information for the Aureum trading platform. The collected data will be standardized, validated, and forwarded to downstream services including strategy engines, execution modules, analytics, and AI reasoning components.

The objective of this module is to provide accurate, low-latency, and reliable market data required for automated trading and market analysis.

2. Problem Statement

Cryptocurrency markets operate continuously, and prices change within milliseconds. Historical datasets are useful for analysis and backtesting but cannot support live trading decisions. Without a real-time market data pipeline, the trading system would operate on stale information, resulting in delayed execution and inaccurate decision-making.

The application therefore requires a dedicated component capable of maintaining a persistent connection with the exchange and continuously receiving market updates as they occur.

3. Objectives

The primary objectives of this module are:

Establish a persistent WebSocket connection with Binance Testnet.
Receive real-time market events with minimal latency.
Collect trade events, ticker updates, candle updates, and order book changes.
Validate incoming market data before internal processing.
Convert exchange-specific messages into standardized internal models.
Ensure continuous streaming through automatic reconnection mechanisms.
Provide reliable data for downstream modules.
4. Scope

This module includes:

WebSocket connection management
Live market event collection
Market event validation
Event standardization
Event forwarding
Connection monitoring
Automatic reconnection

This module does not include:

Trading strategy
Order execution
Risk management
Portfolio management
AI prediction
User interface
5. Functional Requirements

The system shall:

FR-1

Connect to Binance Testnet using WebSocket.

FR-2

Subscribe to supported market data streams.

FR-3

Receive live Trade Events.

FR-4

Receive live Order Book updates.

FR-5

Receive live Ticker Events.

FR-6

Receive live Candle updates.

FR-7

Validate every incoming message.

FR-8

Convert exchange JSON into internal event models.

FR-9

Automatically reconnect when the WebSocket connection is interrupted.

FR-10

Forward validated events to downstream services.

6. Non-Functional Requirements

The module should satisfy the following quality requirements.

Reliability

The connection should recover automatically from temporary network failures.

Performance

The module should process incoming events with minimal latency.

Scalability

The architecture should allow support for additional exchanges in the future.

Maintainability

The code should follow a modular structure with clear separation of responsibilities.

Extensibility

New event types should be added without major architectural changes.

Data Integrity

Only validated and correctly formatted events should enter the system.

7. Stakeholders
Stakeholder	Responsibility
Market Data Module	Collect live market data
Trading Module	Consume live events
Strategy Engine	Generate signals
AI Reasoning Module	Perform market analysis
Dashboard	Display live market information
8. Dependencies

The module depends on:

Binance Spot Testnet
WebSocket API
Internet Connectivity
Python Runtime
Pydantic Validation Library
Project Compass Core Infrastructure
9. Assumptions

The following assumptions are made during implementation:

Binance Testnet remains accessible.
Internet connectivity is available.
Incoming market messages follow Binance WebSocket specifications.
Downstream modules are capable of consuming standardized events.
10. Constraints
Market data is dependent on exchange availability.
Network interruptions may occur.
Testnet liquidity differs from production markets.
Exchange API changes may require updates.
11. Success Criteria

The implementation will be considered successful when:

Live market data is received continuously.
Trade events are successfully processed.
Order book updates are received correctly.
Candle updates are validated successfully.
Ticker updates are standardized.
Automatic reconnection functions correctly.
No malformed events are propagated downstream.
12. Deliverables

The module will deliver:

WebSocket Client
TradeEvent Model
MarketEvent Model
OrderBookSnapshot Model
OrderBookDelta Model
Candle Model
TickerEvent Model
Unit Tests
Documentation
13. Future Enhancements

Future versions may include:

Multi-exchange support
Historical replay mode
Message compression
Advanced monitoring
High-availability streaming
Real-time metrics dashboard
End of Document