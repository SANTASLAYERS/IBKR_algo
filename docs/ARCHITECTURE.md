# Multi-Ticker IB Trading Framework Architecture

This document provides an overview of the system architecture, component relationships, and design patterns used in the Multi-Ticker IB Trading Framework.

## System Overview

The system is designed as an asynchronous trading framework that connects to Interactive Brokers (IB) for market data and order execution. It follows async-first principles with robust connection handling, and is structured to support multiple equity tickers.

![Architecture Overview](https://mermaid.ink/img/pako:eNqNkk9rwzAMxb-K0WkdpD8g9DKWHQYrbTmUEty4aQ1JnGA7pZTQbF38-eJ0W9cy2HJQsJ70nqUj8gI2aYZiJHLCIY28cHyUXbDNLYYCXR1lJxiTHQ05WGxRbHSBCrj5P5xT_LCbSqAEuNa9QKqZGzuRYrlRUTkbz8H0RgmtS-TMi2LbcA_tg4iBk2_g2t2D7r-Ue3NuYKQ9DKlO6lzQlKx3YjQmyyLuYUmZuSOX_oYjuXsXtGptM7rWiZR5MtjdOLTQxqSxUMOVmTiQ0fNkS7bBaYwjjWOjgx8Seb_2UbVcU9QGjMwR5lgWuZJ9y2h3QnLTOXKGOJLBFSVJvPbetGH8HuNAw4NHRaSXA3r-3P68P91rKkU6GD7sKkgwWUOiWCeJPMbeBmOSJqLKhv7Z9TZfhDXCuJvvjDTfuYxnX5rvGQ-L-QI7V8O_NdNtJYrX2vYKWiifxIh9e3Ml3p4vP4_vn4qyeXdQWPEFP3hMWQ)

## Core Components

### 1. Connection Layer
The connection layer handles all interactions with the Interactive Brokers API.

#### IBKRConnection (src/connection.py)
- Base connection class extending IB's EWrapper and EClient
- Handles message processing and connection lifecycle
- Implements connection recovery and retry logic
- Manages API request IDs
- Key responsibilities:
  - Establishing and maintaining connection to IB Gateway/TWS
  - Processing callbacks from IB API
  - Handling reconnection after failures

#### HeartbeatMonitor (src/heartbeat.py)
- Monitors connection health via periodic checks
- Detects connection timeouts and triggers reconnection
- Uses asyncio tasks for timer management
- Key methods:
  - `start_monitoring()`: Begins heartbeat checks
  - `stop_monitoring()`: Halts heartbeat checks
  - `heartbeat_received()`: Resets timeout timer

#### IBGateway (src/gateway.py)
- Enhanced connection specifically for IB Gateway
- Extends base connection with trading capabilities:
  - Market data subscription
  - Order submission and management
  - Account information retrieval
  - Position tracking

### 2. Event Processing

#### IBKREventLoop (src/event_loop.py)
- Manages the async event loop for message processing
- Handles scheduled tasks and message queue
- Provides thread-safe event processing
- Key methods:
  - `start()`: Begins event processing in background thread
  - `stop()`: Halts event processing
  - `add_message_processor()`: Registers message handlers
  - `schedule_task()`: Adds tasks to the event loop

#### ErrorHandler (src/error_handler.py)
- Centralizes error processing and callbacks
- Categorizes IB API errors by type
- Routes errors to appropriate handlers
- Provides error logging and reporting

### 3. API Client
A separate component for interacting with the Options Flow Monitor API.

#### ApiClient (api_client/client.py)
- Base HTTP client with sync/async capabilities
- Handles authentication, request preparation, and response processing
- Implements error handling and retries
- Supports both direct initialization and environment-based configuration

#### Endpoint Classes (api_client/endpoints.py)
- Separate classes for specific API endpoints:
  - StatusEndpoint: System status information
  - TradesEndpoint: Options trades data
  - PredictionEndpoint: ML prediction data
  - And others

### 4. Command-Line Interface

#### Gateway CLI (gateway_cli.py)
- Command-line interface for IB Gateway operations
- Provides commands for:
  - Checking gateway connection
  - Starting IB Gateway process
  - Market data subscription
  - Position and account information retrieval

## Design Patterns

The framework employs several design patterns:

1. **Inheritance**: Extends IB's client classes with enhanced functionality
2. **Composition**: For non-inheritance relationships between components
3. **Factory Methods**: For request IDs and connection parameters
4. **Observer Pattern**: Via callback registrations for events
5. **Dependency Injection**: Via configuration objects
6. **Command Pattern**: In the CLI interface
7. **Singleton**: For certain global services

## Data Flow

1. IB Gateway/TWS sends market data and event notifications
2. `IBKRConnection` or `IBGateway` receives messages via callbacks
3. Messages are processed by the `IBKREventLoop`
4. Application code receives processed data via registered callbacks
5. Trading decisions may be influenced by predictions from the API client
6. Orders are sent back to IB via the Gateway interface

## Configuration

The system is configurable through:
- Configuration files (INI format)
- Command-line arguments
- Environment variables
- Programmatic configuration via `Config` class

## Testing Strategy

The codebase includes:
- Unit tests for individual components
- Integration tests for component interactions
- Mock objects for IB API simulation
- Connectivity tests for live IB Gateway

## Future Development

See [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for planned enhancements to the system architecture.