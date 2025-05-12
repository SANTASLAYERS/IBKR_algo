# IBKR Connection and API Client Tests Documentation

## Test Suite Overview

The test suite provides comprehensive coverage for the IBKR connection system, Multi-Ticker Options Flow Monitor API client, and the Order and Position Management System, verifying normal operation, edge cases, and error handling for all components. The suite includes both unit tests and integration tests for end-to-end validation against a live IB Gateway.

### Test Files Structure

#### IBKR Connection Tests
- **`test_heartbeat.py`**: Tests for the HeartbeatMonitor class
- **`test_event_loop.py`**: Tests for the IBKREventLoop class
- **`test_connection.py`**: Tests for the IBKRConnection class
- **`test_gateway.py`**: Tests for the IBGateway class
- **`test_live_connection.py`**: Tests for live connection to IBKR Gateway
- **`test_gateway_connectivity.py`**: Gateway connectivity test script
- **`test_reconnection.py`**: Reconnection capability test script
- **`test_subscription_manager.py`**: Tests for market data subscription management
- **`test_persistent_subscription.py`**: Tests for subscription persistence
- See `tests/GATEWAY_TESTING.md` for guidelines on testing with IB Gateway

#### API Client Tests
- **`test_api_client.py`**: Tests for the ApiClient base class
- **`test_api_endpoints.py`**: Tests for all API endpoint classes
- **`test_api_fixed.py`**: Fixed API test scenarios
- **`test_api_live.py`**: Live API connectivity testing

#### Order and Position Management Tests
- **`event_system/test_events.py`**: Tests for the event system foundation
- **`event_system/test_position.py`**: Tests for position management functionality
- **`order_system/test_order.py`**: Tests for order management functionality
- See `tests/ORDER_POSITION_TESTS.md` for detailed order and position system testing documentation

#### Rule Engine Tests
- **`rule_engine/test_rule_engine.py`**: Tests for rule engine components
  - Tests for condition evaluation (event, position, time, and composite conditions)
  - Tests for action execution (order and position actions)
  - Tests for rule registration, evaluation, and execution
  - Tests for rule engine integration with the event system
- See `tests/RULE_ENGINE_TESTS.md` for detailed rule engine testing documentation

#### Minute Data Tests
- **`minute_data/test_models.py`**: Tests for minute bar data models
- **`minute_data/test_minute_fetching.py`**: Tests for historical minute data fetching
- **`minute_data/test_callbacks.py`**: Tests for minute data callback handling
- **`minute_data/test_caching.py`**: Tests for minute data caching
- **`test_minute_cli.py`**: Tests for minute data CLI commands

#### Integration Tests
- **`integration/test_order_integration.py`**: Tests for live order placement and management
- **`integration/test_market_data_integration.py`**: Tests for live market data functionality
- **`integration/test_error_handling_integration.py`**: Tests for error handling with live gateway
- **`integration/README.md`**: Overview of the integration test suite
- **`integration/RUNNING_INTEGRATION_TESTS.md`**: Guidelines for running integration tests
- **`integration/TEST_VALIDATION.md`**: Validation methodology for integration tests
- **`direct_test.py`**: Direct test script for verifying gateway connectivity

#### Shared Test Components
- **`mocks.py`**: Mock objects used across tests
- **`conftest.py`**: Shared pytest fixtures
- **`unittest_heartbeat.py`**: Unit test for heartbeat
- **`unittest_runner.py`**: Unit test runner
- **`utils/`**: Utility functions for testing

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

# Run all rule engine tests
pytest tests/rule_engine/

# Run with coverage
pytest --cov=src.rule tests/rule_engine/

# Run all minute data tests
pytest tests/minute_data/

# Run with coverage
pytest --cov=src.minute_data tests/minute_data/
```

### Live Testing

For WSL2, use the correct IP address (172.28.64.1) for Windows host:

```bash
# Direct test script (recommended first test)
python tests/direct_test.py

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

### Integration Testing

The comprehensive integration test suite validates real-world behavior against a live IB Gateway:

```bash
# Set required environment variables for WSL2
export IB_HOST=172.28.64.1  # WSL2 to Windows host IP
export IB_PORT=4002         # Paper trading port
export IB_CLIENT_ID=10
export IB_ACCOUNT=YOUR_ACCOUNT_ID

# Run all integration tests
pytest -xvs tests/integration/

# Run specific integration test categories
pytest -xvs tests/integration/test_order_integration.py
pytest -xvs tests/integration/test_market_data_integration.py
pytest -xvs tests/integration/test_error_handling_integration.py
```

See the following files for detailed documentation on integration tests:
- `tests/integration/README.md`: Overview of integration testing
- `tests/integration/RUNNING_INTEGRATION_TESTS.md`: How to run integration tests
- `tests/integration/TEST_VALIDATION.md`: Validation methodology
- `tests/INTEGRATION_TESTING.md`: Comprehensive integration testing guidelines
- `docs/WSL_CONNECTIVITY.md`: Guide for connecting from WSL2 to Windows IB Gateway
- `docs/WSL_CONNECTIVITY_AND_TESTING.md`: Detailed testing architecture for WSL2

## Test Components

### Test Coverage

#### IBKR Connection Tests
- Heartbeat monitoring (initialization, detection, timeouts)
- Event loop (message processing, task scheduling)
- Connection lifecycle (establishment, termination, reconnection)
- Gateway features (market data, orders, positions)
- Error handling and categorization
- Subscription management (creation, persistence, updates)

#### Integration Tests
- Live order placement and execution validation
- Real-world market data quality verification
- Error handling with actual IB Gateway responses
- Connection resilience with actual network conditions
- Account data and position reconciliation

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

#### Rule Engine Tests
- Condition evaluation (event, position, time, and composite conditions)
- Action execution (create/close positions, create/cancel orders)
- Rule lifecycle (initialization, evaluation, execution, cooldown)
- Rule Engine operations (registration, enablement, context sharing)
- Event-based rule triggering
- Rule prioritization and execution ordering
- Integration with event system, position, and order management

#### Minute Data Tests
- Data model validation
- Historical data fetching and processing
- Caching mechanisms and efficiency
- Callback handling for data updates
- API integration for historical data

### Test Fixtures

The tests use fixtures defined in `conftest.py` to set up mock objects and testing environments:

- Mock objects: Configuration, API clients, error handlers
- Pre-configured components: Heartbeat monitors, event loops, gateways
- Testing utilities: Async contexts, HTTP mocks
- Integration test setups: Configured testing environments

For integration tests, special pytest fixtures are used to:
- Create a session-wide event loop
- Maintain a single connection to IB Gateway
- Inject the gateway into each test class automatically

### Understanding Mocks

The tests use mock objects located in `tests/mocks.py`:
- `MockIBKRAPI`: Mocks the IBKR API client
- `MockConfig`: Mocks the configuration
- `MockErrorHandler`: Mocks the error handler
- `AsyncMock`: Utility for mocking async functions
- `MockMarketData`: Mocks market data responses
- `MockOrderExecutor`: Mocks order execution

## Common Issues

1. **ImportError**: If you get import errors, make sure your Python environment can find the project modules
2. **Event loop issues**: If you encounter asyncio errors, check that you're using pytest-asyncio
3. **Test freezes**: If tests hang, check that asyncio tasks and threads are properly cleaned up
4. **Integration test failures**: Live tests may fail due to market conditions, timing, or API rate limits
5. **WSL2 connection issues**: If running in Windows Subsystem for Linux (WSL2), you cannot use localhost/127.0.0.1 to connect to IB Gateway running on Windows. You must use the WSL2-to-Windows IP address 172.28.64.1 instead. Verify connectivity with `nc -vz 172.28.64.1 4002`. Additional considerations:
   - Ensure IB Gateway API settings allow connections from WSL2 IP range
   - Check Windows Firewall allows connections from 172.16.0.0/12 to port 4002
   - Use `python tests/direct_test.py` to verify basic connectivity
   - See `docs/WSL_CONNECTIVITY.md` for complete configuration instructions
6. **Integration test fixture failures**: If you see "Gateway not initialized" errors, check:
   - The _inject_gateway fixture in conftest.py is working properly
   - Test classes are accessing the gateway via self.gateway
   - Event loop scope matches between fixtures and tests
   - See `docs/WSL_CONNECTIVITY_AND_TESTING.md` for detailed fixture documentation

## Best Practices for Extending Tests

When adding new functionality to the codebase:
1. Test normal operation, edge cases, and error handling
2. Use mocks to avoid dependencies on external systems for unit tests
3. Implement integration tests for critical trading functionality
4. Clean up resources to prevent test contamination
5. Keep tests independent from each other
6. Mock HTTP responses for API client tests
7. Test both synchronous and asynchronous interfaces
8. For integration tests, implement multi-faceted validation (see `tests/integration/TEST_VALIDATION.md`)
9. Balance unit tests (for speed/reliability) with integration tests (for real-world validation)
10. For pytest fixtures that inject into classes, use the `_inject_gateway` pattern to ensure proper injection