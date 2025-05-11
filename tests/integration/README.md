# Integration Tests for IB Gateway

This directory contains integration tests that validate the trading system against a live Interactive Brokers (IB) Gateway. These tests require:

1. A running IB Gateway instance (either paper trading or live)
2. Valid credentials and connection parameters
3. Appropriate permissions to execute trades in the testing environment

## Test Validation Approach

Unlike unit tests that rely on mocks, these integration tests validate actual responses from the IB Gateway. Each test follows this pattern:

1. **Setup**: Connect to IB Gateway with credentials and prepare test state
2. **Action**: Execute trading operation (e.g., place order, modify order, etc.)
3. **Validation**: Verify the operation was successful through multiple mechanisms:
   - Validate response codes from IB Gateway
   - Verify operation via secondary queries (e.g., check positions after order)
   - Confirm expected callbacks were received
   - Reconcile local state with IB Gateway state
4. **Cleanup**: Return the system to its original state (cancel orders, close positions)

## Running Tests

These tests require environment variables for connection parameters:

```bash
# Set environment variables
export IB_HOST=127.0.0.1  # IB Gateway host
export IB_PORT=4002       # 4002 for paper trading, 4001 for live
export IB_CLIENT_ID=10    # Client ID for this connection
export IB_ACCOUNT=YOUR_ACCOUNT_ID  # Your IB account ID

# Run all integration tests
pytest -xvs tests/integration/

# Run specific test category
pytest -xvs tests/integration/test_order_integration.py
```

## Skipping Tests

If IB Gateway is not available, these tests will be automatically skipped with a message indicating the reason. To force test execution even when expected to fail (for development purposes):

```bash
pytest -xvs tests/integration/ --force-ib-gateway
```

## Critical Path Scenarios Tested

1. **Basic Connectivity**
   - Test connection establishment and management
   - Validate error handling for invalid credentials

2. **Order Placement and Lifecycle**
   - Market order submission and execution
   - Limit order submission and modification
   - Order cancellation and verification

3. **Position Management**
   - Open position creation
   - Position reconciliation with IB Gateway
   - Position closure verification

4. **Order Strategies**
   - Bracket order (entry, stop loss, take profit)
   - OCO (One-Cancels-Other) order groups
   - Complex multi-leg orders

5. **Error Handling and Recovery**
   - Connection interruption recovery
   - Invalid order handling
   - Network issue resilience

## Adding New Tests

When adding new integration tests, follow these guidelines:

1. Each test must have clear pass/fail criteria
2. Include proper cleanup procedures in `finally` blocks
3. Use paper trading environment for test development
4. Document expected behavior and validation approach
5. Ensure tests are idempotent and can run repeatedly