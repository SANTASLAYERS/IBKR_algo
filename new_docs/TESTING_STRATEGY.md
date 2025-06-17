# Alpaca Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for the Alpaca trading system. The tests ensure all components work correctly both individually and as an integrated system.

## Test Suite Components

### 1. Integration Tests (`test_alpaca_integration.py`)

Comprehensive tests for all major components working together.

**Test Coverage:**
- Position tracking and synchronization
- Market data retrieval (historical and real-time)
- Order lifecycle (create, submit, cancel)
- Stop/target orders (bracket orders)
- Fill event handling
- Multiple simultaneous positions
- Event flow validation

**Key Features:**
- Tests real Alpaca API interactions
- Validates event propagation
- Ensures data consistency
- Tests error scenarios

### 2. End-to-End Test (`test_alpaca_e2e.py`)

Simulates complete trading flow from signal to position management.

**Test Coverage:**
- Complete system initialization
- Rule engine integration
- Trading signal processing
- Position lifecycle
- Error handling and recovery

**Key Features:**
- Tests full trading workflow
- Validates rule execution
- Tests prediction-to-trade flow
- Ensures system resilience

### 3. Component-Specific Tests

#### Connection Test (`test_alpaca_connection.py`)
- Connection establishment
- Order placement/cancellation
- Account information retrieval
- WebSocket stream initialization

#### Position Sync Test (`test_alpaca_position_sync.py`)
- Position synchronization
- Discrepancy handling
- Periodic sync functionality
- Single position updates

#### Event System Test (`test_alpaca_events.py`)
- Event adapter functionality
- Status mapping accuracy
- Fill event generation
- Event flow validation

#### Market Data Test (`test_alpaca_minute_data.py`)
- Historical data retrieval
- Multiple timeframes
- Caching functionality
- Data format conversion

## Running the Tests

### Prerequisites

1. Set environment variables:
```bash
export ALPACA_API_KEY="your_api_key"
export ALPACA_SECRET_KEY="your_secret_key"
export ALPACA_TRADING_MODE="paper"
```

2. Ensure paper trading account is active

### Individual Test Execution

```bash
# Integration tests
python test_alpaca_integration.py

# End-to-end test
python test_alpaca_e2e.py

# Component tests
python test_alpaca_connection.py
python test_alpaca_position_sync.py
python test_alpaca_events.py
python test_alpaca_minute_data.py
```

### Test Suite Execution

Run all tests in sequence:
```bash
# Windows PowerShell
$env:ALPACA_API_KEY="your_key"; python test_alpaca_integration.py; python test_alpaca_e2e.py

# Linux/Mac
export ALPACA_API_KEY="your_key" && python test_alpaca_integration.py && python test_alpaca_e2e.py
```

## Test Results Interpretation

### Integration Test Results

Expected output:
```
📊 Testing Position Tracking...
  ✓ Synced X positions
  ✓ Alpaca positions: X
  ✓ Tracker positions: X

📈 Testing Market Data Retrieval...
  ✓ Retrieved XXX minute bars
  ✓ Latest bar: [timestamp] - Close: $XXX.XX

🔄 Testing Order Lifecycle...
  ✓ Order created: ORD_XXX
  ✓ Order submitted
  ✓ Order cancelled successfully
```

### E2E Test Results

Expected output:
```
🎯 Simulating trading flow...
  ✓ Rule engine started
  ✓ Emitted bullish prediction
  ✓ Order created: ORD_XXX
  ✓ Position closed successfully
  ✓ Total P/L: $X.XX
```

## Test Scenarios

### 1. Market Hours Testing
- Tests should handle both market hours and after-hours
- Fill events only occur during market hours
- Orders may be queued outside market hours

### 2. Position Scenarios
- Empty account (no positions)
- Single position
- Multiple positions
- Partial fills
- Position reversals

### 3. Order Scenarios
- Market orders
- Limit orders
- Stop orders
- Bracket orders
- Order cancellation
- Order rejection

### 4. Error Scenarios
- Invalid symbols
- Insufficient buying power
- Network errors
- API rate limits
- WebSocket disconnections

## Best Practices

### 1. Test Isolation
- Each test should clean up after itself
- Cancel all test orders
- Close all test positions
- Use unique order IDs

### 2. Market Awareness
- Check if market is open before fill tests
- Use limit orders for predictable behavior
- Account for order queuing

### 3. Error Handling
- Expect and handle API errors gracefully
- Log all errors for debugging
- Implement retry logic where appropriate

### 4. Performance
- Minimize API calls
- Use appropriate delays between operations
- Batch operations where possible

## Continuous Testing

### Daily Validation
Run these tests daily:
1. Connection test
2. Position sync test
3. Market data test

### Pre-Production Checklist
Before production deployment:
1. Run full integration test suite
2. Verify E2E test passes
3. Check all component tests
4. Review error logs
5. Validate position reconciliation

### Monitoring
- Monitor test execution times
- Track API rate limit usage
- Log all test failures
- Alert on critical failures

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify API credentials
   - Check network connectivity
   - Ensure paper trading is enabled

2. **No Fill Events**
   - Market may be closed
   - Order price may be unrealistic
   - Check order status manually

3. **Position Sync Issues**
   - Manual trades may cause discrepancies
   - Check Alpaca dashboard
   - Force manual sync

4. **Test Timeouts**
   - Increase wait times
   - Check API status
   - Verify WebSocket connection

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Test Metrics

Track these metrics:
- Test pass rate
- Average execution time
- API calls per test
- Error frequency
- Position sync accuracy

## Future Enhancements

1. **Automated Test Runs**
   - Schedule daily test execution
   - Automated result reporting
   - Integration with CI/CD

2. **Performance Testing**
   - Load testing with multiple symbols
   - Stress testing order placement
   - Latency measurements

3. **Advanced Scenarios**
   - Options trading tests
   - Crypto trading tests
   - Extended hours testing 