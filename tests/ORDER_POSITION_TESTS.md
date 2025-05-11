# Order and Position Management Test Suite

## Overview

This document describes the test suite for the Order and Position Management System components. The tests are designed to verify correct functionality of the event system, position management, and order management components.

## Test Structure

The tests are organized into three main categories:

### Event System Tests (`/tests/event_system/test_events.py`)

Tests for the event-driven architecture foundation including:

- Base event functionality
- Event bus subscription and emission
- Event inheritance and hierarchical event handling
- Event type-specific functionality (market, order, position, API events)

### Position Management Tests (`/tests/event_system/test_position.py`)

Tests for position tracking and management including:

- Position initialization and lifecycle (planned → open → closed)
- Stock position-specific functionality
- Position adjustments (quantity, stop loss, take profit)
- PositionTracker functionality for managing multiple positions
- Event emission during position lifecycle changes

### Order Management Tests (`/tests/order_system/test_order.py`)

Tests for order creation, tracking, and execution including:

- Order initialization and validation
- Order lifecycle (created → submitted → accepted → filled/cancelled)
- Fill processing and average price calculation
- Order group functionality (basic groups, bracket orders, OCO groups)
- OrderManager for creating and tracking orders

## Key Features Tested

1. **Event System**
   - Event subscription and unsubscription
   - Event inheritance for hierarchical event handling
   - Event processing through the event bus

2. **Position Management**
   - Position lifecycle management
   - P&L calculation (unrealized and realized)
   - Risk management (stop loss, take profit, trailing stops)
   - Position adjustments
   - Multiple position tracking

3. **Order Management**
   - Order validation and creation
   - Order status transitions
   - Fill processing
   - Bracket orders (entry + stop loss + take profit)
   - OCO (One-Cancels-Other) order groups
   - Order cancellation

## Test Types

The test suite consists primarily of **unit tests** that verify individual component functionality. The tests use:

- `pytest` as the test framework
- `pytest-asyncio` for testing asynchronous code
- Mock objects to avoid dependency on external systems

The tests **do not require an IB Gateway connection** as they use mock objects for all external dependencies. This allows the tests to run quickly and reliably in any environment.

## Running the Tests

To run the tests for the order and position management system:

```bash
# Run all order and position management tests
pytest tests/event_system/ tests/order_system/

# Run specific test files
pytest tests/event_system/test_events.py
pytest tests/event_system/test_position.py
pytest tests/order_system/test_order.py

# Run tests with coverage report
pytest --cov=src.event --cov=src.position --cov=src.order tests/event_system/ tests/order_system/
```

## Mock Components

The tests use simple in-memory implementations rather than complex mocks. This approach allows for:

1. Testing the core logic without external dependencies
2. Fast test execution
3. Deterministic test behavior

The actual IB Gateway integration will be tested separately in integration tests.

## Integration Tests

The order and position management system can now be tested against a live IB Gateway using the integration test suite in `/tests/integration/`. These tests validate real-world order placement, execution, and position management:

- **`test_order_integration.py`**: Tests for order placement and management
  - Market order submission and validation
  - Limit order placement and cancellation
  - Bracket order creation and status tracking
  - Position query and validation

See [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) for comprehensive documentation on running and interpreting these tests.

## Future Test Enhancements

Additional planned enhancements to the test suite include:

1. **Performance Tests** - Tests that verify system performance under load
2. **Stress Tests** - Tests that verify system behavior under extreme conditions
3. **Scenario Tests** - Tests that verify system behavior in real-world trading scenarios

## Best Practices for Extending Tests

When adding new functionality to the Order and Position Management System:

1. Add unit tests for all new components
2. Test normal operation, edge cases, and error handling
3. Ensure asyncio-based code is properly tested with `pytest-asyncio`
4. Clean up resources to prevent test contamination
5. Keep tests independent from each other