# Running IB Gateway Integration Tests

This guide explains how to run the integration test suite against a live Interactive Brokers Gateway instance.

## Prerequisites

1. **IB Gateway Installation**
   - Interactive Brokers Gateway or TWS installed and running
   - Paper trading account configured (recommended for testing)
   - API connectivity enabled in settings

2. **Environment Setup**
   - Python 3.7+ with required packages installed
   - Environment variables configured (see below)
   - Network access to IB Gateway (default: 127.0.0.1:4002 for paper trading)

## Environment Configuration

Set up the following environment variables before running tests:

```bash
# Required environment variables
export IB_HOST=127.0.0.1               # IB Gateway host (default: localhost)
export IB_PORT=4002                    # 4002 for paper trading, 4001 for live
export IB_CLIENT_ID=10                 # Unique client ID for this connection
export IB_ACCOUNT=DU123456             # Your IB account number

# Optional environment variables
export IB_LOG_LEVEL=INFO               # Logging level (default: INFO)
export IB_TEST_SYMBOLS=SPY,QQQ,IWM     # Test symbols (default: SPY,QQQ,IWM)
export IB_TEST_TIMEOUT=30              # Default test timeout in seconds (default: 30)
```

## Preparing IB Gateway

1. **Start IB Gateway**
   - Launch IB Gateway application
   - Log in to paper trading account
   - Ensure API connectivity is enabled:
     - Configure > API > Settings
     - Enable "Enable ActiveX and Socket Clients"
     - Set socket port to match IB_PORT
     - Disable "Read-Only API" unless testing with read-only access

2. **Verify Connection**
   - Run a simple connectivity test:
     ```bash
     python tests/test_gateway_connectivity.py --host $IB_HOST --port $IB_PORT
     ```
   - If successful, proceed with integration tests

## Running Tests

### Run All Integration Tests

```bash
# Run all integration tests
pytest -xvs tests/integration/

# Run with increased verbosity
pytest -xvs tests/integration/ --log-cli-level=DEBUG
```

### Run Specific Test Categories

```bash
# Order placement and management tests
pytest -xvs tests/integration/test_order_integration.py

# Market data tests
pytest -xvs tests/integration/test_market_data_integration.py

# Error handling tests
pytest -xvs tests/integration/test_error_handling_integration.py

# Run a specific test
pytest -xvs tests/integration/test_order_integration.py::TestOrderIntegration::test_market_order_submission
```

### Forcing Tests When Gateway Is Down

By default, tests will be skipped if IB Gateway is not available. To force test execution (for debugging):

```bash
pytest -xvs tests/integration/ --force-ib-gateway
```

Note: Tests will likely fail with connection errors, but this can be useful for debugging test code.

## Expected Failures

Some integration tests are expected to fail under certain conditions:

1. **Outside Market Hours**
   - Market order tests may fail when markets are closed
   - Some market data tests may return limited data

2. **Account Restrictions**
   - Order placement tests will fail with read-only API access
   - Paper accounts may have position or order value limitations

3. **Network Issues**
   - Tests may timeout if network connectivity to IB Gateway is slow
   - Frequent execution may trigger rate limiting

## Interpreting Test Results

The test output will indicate which tests passed and failed:

```
============================= test session starts ==============================
...
tests/integration/test_order_integration.py::TestOrderIntegration::test_market_order_submission PASSED
tests/integration/test_order_integration.py::TestOrderIntegration::test_limit_order_placement_and_cancellation PASSED
...
=============================== 14 passed, 3 skipped in 45.26s ================
```

For failed tests, detailed error logs will be displayed. Common failures and their meanings:

- `IB Gateway not available`: Connection to gateway failed
- `Timeout waiting for order status`: Order was submitted but no status update received
- `Error code 200`: Contract not found
- `Error code 504`: Not connected to IB Gateway
- `AssertionError: No market data received`: Market data subscription failed

See `TEST_VALIDATION.md` for more details on validating test results.

## Troubleshooting

1. **Connection Issues**
   - Verify IB Gateway is running and logged in
   - Check that port matches IB_PORT setting
   - Ensure no firewall is blocking the connection
   - Try resetting API settings in IB Gateway

2. **Test Timeouts**
   - Increase test timeouts with IB_TEST_TIMEOUT
   - Check IB Gateway Activity panel for API requests
   - Verify account status and permissions

3. **Order Placement Failures**
   - Confirm account has sufficient funds (paper trading)
   - Check if account is in read-only mode
   - Verify IB Gateway Global Configuration > API settings

## Development Tips

When implementing new integration tests:

1. Use the common testing patterns demonstrated in existing tests
2. Implement proper cleanup in finally blocks
3. Add detailed logging for debugging
4. Keep test symbols consistent (use IB_TEST_SYMBOLS environment variable)
5. Use the validation utilities in test_utils.py
6. Run tests individually during development
7. Consider market hours when testing order functionality