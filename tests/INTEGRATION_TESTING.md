# Integration Testing with IB Gateway

This document explains the comprehensive integration test suite for validating the system against a live Interactive Brokers Gateway instance.

## Why Integration Tests Matter

While unit tests with mocks are valuable for rapid development and reliable CI/CD pipelines, integration tests against the actual IB Gateway are critical for:

1. **Validating real-world behavior** - Actual IB Gateway interactions can differ from mock expectations
2. **Ensuring API compatibility** - Detecting changes in IB Gateway API behavior
3. **Verifying end-to-end functionality** - Testing complete workflows from order creation to execution
4. **Identifying performance issues** - Detecting latency or rate limiting problems
5. **Validating error handling** - Testing recovery from real network issues and API errors

## Integration Test Structure

The integration tests are organized in the `tests/integration` directory with the following components:

### Core Test Files

| File | Purpose |
|------|---------|
| `test_order_integration.py` | Tests order placement, modification, and lifecycle |
| `test_market_data_integration.py` | Tests market data subscriptions and historical data |
| `test_error_handling_integration.py` | Tests error response handling and recovery |

### Supporting Files

| File | Purpose |
|------|---------|
| `conftest.py` | Fixtures for IB Gateway connection and test setup |
| `README.md` | Overview of the integration test suite |
| `TEST_VALIDATION.md` | Detailed explanation of success/failure criteria |
| `RUNNING_INTEGRATION_TESTS.md` | Step-by-step guide to run integration tests |

## Validation Approach

Integration tests require clear pass/fail criteria. Our tests implement multi-layered validation:

1. **Primary Validation**: Check immediate API responses (IDs, status codes)
2. **Callback Validation**: Verify expected callbacks are received with correct data
3. **Error Monitoring**: Check for unexpected error conditions
4. **Secondary Verification**: Validate effects through follow-up queries
5. **State Reconciliation**: Confirm local state matches IB Gateway state

## Key Test Scenarios

### Order Management Integration

- **Market order submission** - Verify submission, status updates, and fills
- **Limit order placement and cancellation** - Test order management lifecycle
- **Bracket order creation** - Test complex order types with parent/child relationships
- **Position querying** - Validate position retrieval and reconciliation

### Market Data Integration

- **Real-time market data subscription** - Test data quality and field validation
- **Historical data retrieval** - Verify OHLC data integrity and format
- **Account information retrieval** - Test account summary and position reporting

### Error Handling Integration

- **Invalid contract handling** - Test responses to non-existent symbols
- **Invalid order specifications** - Verify proper rejection of malformed orders
- **Multiple error handling** - Test recovery from sequences of errors
- **Connection loss and reconnection** - Validate heartbeat and reconnection logic

## Running the Integration Tests

See [RUNNING_INTEGRATION_TESTS.md](integration/RUNNING_INTEGRATION_TESTS.md) for detailed instructions.

Basic operation:

```bash
# Set required environment variables
export IB_HOST=127.0.0.1
export IB_PORT=4002
export IB_CLIENT_ID=10
export IB_ACCOUNT=YOUR_ACCOUNT_ID

# Run all integration tests
pytest -xvs tests/integration/

# Run specific category
pytest -xvs tests/integration/test_order_integration.py
```

### Paper vs. Live Testing

Always use a **paper trading account** for integration tests. The tests are designed to work with both paper and live accounts, but paper trading eliminates financial risk.

## Understanding Test Results

For details on interpreting test results and troubleshooting failures, see [TEST_VALIDATION.md](integration/TEST_VALIDATION.md).

Key validation metrics:

- **Request IDs** - Expected to be positive integers
- **Status updates** - Should transition through normal states
- **Data integrity** - Market data should have consistent price relationships
- **Timing** - Responses should arrive within expected timeframes
- **Error absence** - No unexpected error codes for normal operations

## Development Guidelines

When extending the integration test suite:

1. **Follow existing patterns** - The established structure provides clear validation
2. **Implement proper cleanup** - Always use `finally` blocks to clean up resources
3. **Validate multi-faceted responses** - Check both immediate responses and follow-up state
4. **Document validation criteria** - Clearly define success/failure for new tests
5. **Consider market hours** - Account for different behavior outside market hours

See the `tests/integration/README.md` for additional development guidelines.

## Relationship to Unit Tests

Integration tests complement rather than replace unit tests:

- **Unit tests** verify individual components with mocks (fast, reliable)
- **Integration tests** verify real-world behavior (comprehensive, realistic)

Run integration tests:
- During final validation before releases
- When making changes to IB Gateway interaction code
- Periodically to catch API changes or regressions