# IBKR Async Connection Framework

## Architecture Overview

The IBKR Async Connection Framework provides a robust, asynchronous interface to the Interactive Brokers API. The system manages connections with heartbeat monitoring, automatic reconnection, comprehensive error handling, and asynchronous event processing.

## Key Components

### IBKRConnection (`connection.py`)

The core connection class that interfaces with IBKR's TWS or Gateway:

- **Inheritance**: Extends IBKR's `EWrapper` and `EClient` classes
- **Connection Management**: 
  - Async connection with proper error handling
  - State tracking (`connecting`, `connected`, `disconnected`, `reconnecting`)
  - Automatic reconnection with exponential backoff
- **Event Notification**: 
  - Callback registration for connection events
  - Connection state change notifications
- **Heartbeat Integration**: 
  - Uses HeartbeatMonitor for connection health monitoring
  - Automatic heartbeat checks and timeout detection
- **Error Handling**:
  - Processes IBKR API errors through ErrorHandler
  - Special handling for connection-related error codes

```python
# Basic usage
config = Config(host="127.0.0.1", port=7497, client_id=1)
connection = IBKRConnection(config)
await connection.connect_async()
```

### IBGateway (`gateway.py`)

Enhanced connection class specifically for IB Gateway:

- **Extended Configuration**: 
  - Trading mode support (paper/live)
  - Gateway process management
  - Account-specific settings
- **Market Data Management**:
  - Structured market data storage
  - Callback-based updates
  - Symbol subscription management
- **Order and Position Tracking**:
  - Order submission and management
  - Position and portfolio tracking
  - Account value monitoring
- **Execution Reporting**:
  - Commission reporting
  - Execution details
  - Enhanced error handling

```python
# Basic usage
config = IBGatewayConfig(
    host="127.0.0.1", 
    port=4002,  # Paper trading
    client_id=1,
    account_id="U123456",
    trading_mode="paper"
)
gateway = IBGateway(config)
await gateway.connect_gateway()

# Subscribe to market data
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"
req_id = gateway.subscribe_market_data(contract)
```

### HeartbeatMonitor (`heartbeat.py`)

Monitors connection health through periodic heartbeat checks:

- **Dual-mode Operation**: 
  - Asyncio-based monitoring for async environments
  - Thread-based monitoring for synchronous environments
- **Timeout Detection**:
  - Customizable timeouts and check intervals
  - Callback notification on heartbeat loss
- **Thread Safety**: Properly handles concurrency issues

```python
# Basic usage
monitor = HeartbeatMonitor(
    heartbeat_timeout=10.0,
    heartbeat_interval=5.0,
    on_timeout=lambda: print("Heartbeat timeout")
)
monitor.start()
monitor.received_heartbeat()  # Call when heartbeat received
```

### IBKREventLoop (`event_loop.py`)

Manages the event loop for processing IBKR API messages:

- **Thread Management**: 
  - Runs in a dedicated thread
  - Thread-safe message processing
- **Task Scheduling**:
  - Async task scheduling and management
  - Cancellation support
- **Message Processing**:
  - Registered processor execution in thread pool
  - Error handling for processors
- **Graceful Shutdown**:
  - Signal handling (SIGINT, SIGTERM)
  - Task cleanup on shutdown

```python
# Basic usage
event_loop = IBKREventLoop(max_workers=10)
event_loop.start()
event_loop.add_message_processor(connection.run)
event_loop.schedule_task(my_coroutine())
```

### ErrorHandler (`error_handler.py`)

Processes and categorizes errors from the IBKR API:

- **Error Categorization**:
  - Pre-defined error categories (connection, order, market data, etc.)
  - Category-based callback registration
- **Error History**:
  - Maintains recent error history
  - Timestamp tracking
- **Callback System**:
  - Multiple callbacks per category
  - Error-specific handling

```python
# Basic usage
error_handler = ErrorHandler()
error_handler.register_callback(
    lambda error: print(f"Connection error: {error}"),
    category="connection"
)
```

### Config (`config.py`)

Configuration management for the connection system:

- **Dataclass-based**: Clean interface with type hints
- **File Management**:
  - Load/save from/to INI files
  - Command-line argument support
- **Default Values**: Sensible defaults for most settings
- **Custom Settings**: Support for custom extension settings

```python
# Basic usage
config = Config.from_file("config.ini")
config.host = "127.0.0.1"
config.to_file("new_config.ini")
```

### Logger (`logger.py`)

Thread-safe logging infrastructure:

- **Thread Safety**: Proper locking for concurrent access
- **Multiple Destinations**:
  - Console and file output
  - Rotating file handlers
- **Contextual Logging**:
  - LoggerAdapter for context information
  - Structured logging support
- **Configuration**:
  - Level control from config
  - Format customization

```python
# Basic usage
logger = get_logger(__name__)
logger.info("Connected to IBKR")

# Contextual logging
contextual_logger = get_contextual_logger(__name__, account_id="U123456")
contextual_logger.info("Order placed")  # Adds [account_id=U123456] to message
```

## Data Flow

1. **Connection Establishment**:
   - Application creates Config and ErrorHandler
   - IBKRConnection or IBGateway connects to IBKR
   - HeartbeatMonitor starts monitoring
   - IBKREventLoop processes messages

2. **Message Processing**:
   - IBKR sends market data, order updates, etc.
   - IBKRConnection receives via EWrapper interface
   - IBKREventLoop processes messages in thread pool
   - Application receives data through callbacks

3. **Error Handling**:
   - Errors received via EWrapper interface
   - ErrorHandler categorizes and logs errors
   - Registered callbacks notified based on category
   - Connection recovery initiated if needed

4. **Heartbeat Monitoring**:
   - HeartbeatMonitor checks connection health
   - On timeout, IBKRConnection notified
   - Reconnection process initiated
   - Callbacks notified of disconnection/reconnection

5. **Gateway-specific Flow**:
   - Gateway process can be started/stopped programmatically
   - Market data subscriptions managed with callbacks
   - Order and position tracking with structured storage
   - Account updates processed and organized

## Command-line Interface

The framework includes a command-line interface (`gateway_cli.py`) for common gateway operations:

```bash
# Check Gateway connection
python gateway_cli.py --check

# Start Gateway
python gateway_cli.py --start --gateway-path /path/to/ibgateway

# Show positions
python gateway_cli.py --positions
```

## Design Patterns

The framework employs several design patterns:

1. **Adapter Pattern**: IBKRConnection adapting IBKR API to async interface
2. **Observer Pattern**: Callback systems for events and errors
3. **Factory Pattern**: Logger creation and management
4. **Composition**: Components composed rather than inheritance hierarchy
5. **Strategy Pattern**: Flexible monitoring and error handling strategies
6. **Decorator Pattern**: Extended functionality through IBGateway class

## Best Practices for Extension

When extending the framework:

1. **Respect Async Design**: Always use async-compatible approaches
2. **Use Dependency Injection**: Pass components rather than creating them
3. **Register Callbacks**: Use the callback system rather than subclassing
4. **Handle Errors**: Always handle potential errors, especially in callbacks
5. **Clean Up Resources**: Properly stop/disconnect when finishing
6. **Consider Trading Modes**: Paper vs. live trading have different connection details
7. **Avoid Lambda with Super()**: When using `super()` in async contexts, avoid lambdas - use explicit class references instead

```python
# INCORRECT: Using super() in a lambda
await loop.run_in_executor(None, lambda: super().connect(host, port, client_id))

# CORRECT: Using explicit class reference
self_copy = self
await loop.run_in_executor(None, lambda: EClient.connect(self_copy, host, port, client_id))
```

## Error Recovery Flow

1. Connection lost (detected via heartbeat timeout or explicit error)
2. Connection state changes to "reconnecting"
3. Disconnect called to clean up resources
4. Reconnection attempted with exponential backoff
5. If successful, heartbeat monitoring resumes
6. If unsuccessful after max attempts, application notified