# IBKR Connection and API Client Tests Documentation

## Test Suite Overview

The test suite provides comprehensive coverage for the IBKR connection system, Multi-Ticker Options Flow Monitor API client, and the Order and Position Management System, verifying normal operation, edge cases, and error handling for all components.

### Test Files Structure

#### IBKR Connection Tests
- **`test_heartbeat.py`**: Tests for the HeartbeatMonitor class
- **`test_event_loop.py`**: Tests for the IBKREventLoop class
- **`test_connection.py`**: Tests for the IBKRConnection class
- **`test_gateway.py`**: Tests for the IBGateway class
- **`test_live_connection.py`**: Tests for live connection to IBKR Gateway
- **`test_gateway_connectivity.py`**: Gateway connectivity test script
- **`test_reconnection.py`**: Reconnection capability test script

#### API Client Tests
- **`test_api_client.py`**: Tests for the ApiClient base class
- **`test_api_endpoints.py`**: Tests for all API endpoint classes
- **`test_api_fixed.py`**: Fixed API test scenarios
- **`test_api_live.py`**: Live API connectivity testing

#### Order and Position Management Tests
- **`event_system/test_events.py`**: Tests for the event system foundation
- **`event_system/test_position.py`**: Tests for position management functionality
- **`order_system/test_order.py`**: Tests for order management functionality
- See [ORDER_POSITION_TESTS.md](ORDER_POSITION_TESTS.md) for detailed documentation

#### Shared Test Components
- **`mocks.py`**: Mock objects used across tests
- **`conftest.py`**: Shared pytest fixtures
- **`unittest_heartbeat.py`**: Unit test for heartbeat
- **`unittest_runner.py`**: Unit test runner

#### /minute_data
- **`test_models.py`**: Tests for minute bar data models
- **`test_minute_fetching.py`**: Tests for historical minute data fetching
- **`test_callbacks.py`**: Tests for minute data callback handling
- **`test_caching.py`**: Tests for minute data caching
- **`test_minute_cli.py`**: Tests for minute data CLI commands

See [GATEWAY_TESTING.md](GATEWAY_TESTING.md) for guidelines on testing with IB Gateway.

## Running Tests

The test suite includes both mocked tests (for unit testing) and live tests that connect to the actual IB Gateway. For the most reliable and realistic testing, **we recommend testing against the real IB Gateway** whenever possible, especially for integration and end-to-end tests.

### Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-cov
   ```

2. Ensure your current directory is the project root

### Basic Commands

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src tests/

# Run specific test files
pytest tests/test_heartbeat.py
pytest tests/test_connection.py

# Run with verbose output
pytest -v
```

### Component-Specific Tests

```bash
# Run all IBKR connection tests
pytest tests/test_heartbeat.py tests/test_event_loop.py tests/test_connection.py tests/test_gateway.py

# Run with coverage
pytest --cov=src tests/test_heartbeat.py tests/test_event_loop.py tests/test_connection.py tests/test_gateway.py

# Run all API client tests
pytest tests/test_api_client.py tests/test_api_endpoints.py

# Run with coverage
pytest --cov=api_client tests/test_api_client.py tests/test_api_endpoints.py

# Run all order and position management tests
pytest tests/event_system/ tests/order_system/

# Run with coverage
pytest --cov=src.event --cov=src.position --cov=src.order tests/event_system/ tests/order_system/
```

### Live Testing

```bash
# IBKR Gateway Live Testing
python tests/test_live_connection.py --host 172.28.64.1 --port 4002 --client-id 1

# Gateway Connectivity Test
python tests/test_gateway_connectivity.py --host 172.28.64.1 --port 4002

# Reconnection Test
python tests/test_reconnection.py --host 172.28.64.1 --port 4002

# API Client Live Testing (requires environment variables)
export API_KEY="your-api-key"
export API_BASE_URL="https://your-server-address/api/v1"
python tests/test_api_live.py
```

## Test Components

### Test Coverage

#### IBKR Connection Tests
- Heartbeat monitoring (initialization, detection, timeouts)
- Event loop (message processing, task scheduling)
- Connection lifecycle (establishment, termination, reconnection)
- Gateway features (market data, orders, positions)
- Error handling and categorization

#### API Client Tests
- Client initialization and configuration
- Request execution and response handling
- Authentication and error management
- Endpoint-specific functionality
- Parameter validation and formatting

#### Order and Position Management Tests
- Event system (subscription, emission, inheritance)
- Position lifecycle (planning, opening, adjusting, closing)
- Position risk management (stop loss, take profit, trailing stops) 
- Order lifecycle (creation, submission, fills, cancellation)
- Order groups (bracket orders, OCO orders)
- Integration between event, position, and order components

### Test Fixtures

The tests use fixtures defined in `conftest.py` to set up mock objects and testing environments:

- Mock objects: Configuration, API clients, error handlers
- Pre-configured components: Heartbeat monitors, event loops, gateways
- Testing utilities: Async contexts, HTTP mocks

### Understanding Mocks

The tests use mock objects located in `tests/mocks.py`:
- `MockIBKRAPI`: Mocks the IBKR API client
- `MockConfig`: Mocks the configuration
- `MockErrorHandler`: Mocks the error handler
- `AsyncMock`: Utility for mocking async functions

## Common Issues

1. **ImportError**: If you get import errors, make sure your Python environment can find the project modules
2. **Event loop issues**: If you encounter asyncio errors, check that you're using pytest-asyncio
3. **Test freezes**: If tests hang, check that asyncio tasks and threads are properly cleaned up

## Best Practices for Extending Tests

When adding new functionality to the codebase:
1. Test normal operation, edge cases, and error handling
2. Use mocks to avoid dependencies on external systems
3. Clean up resources to prevent test contamination
4. Keep tests independent from each other
5. Mock HTTP responses for API client tests
6. Test both synchronous and asynchronous interfaces