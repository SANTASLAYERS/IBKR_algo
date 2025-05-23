# TWS Integration Tests

This directory contains integration tests that actually connect to and interact with TWS (Trader Workstation).

## ⚠️ Safety First

**CRITICAL**: These tests interact with real TWS instances. Always ensure:
- You are using **PAPER TRADING ONLY** 
- Never run against live trading accounts
- Monitor order placement tests manually
- Start with basic tests and work your way up

## Quick Start

1. **Start TWS** in paper trading mode
2. **Enable API** in Global Configuration → API Settings
3. **Set up environment**:
   ```bash
   export TWS_HOST=127.0.0.1
   export TWS_PORT=7497
   export TWS_CLIENT_ID=10
   export TWS_ACCOUNT=your_paper_account
   ```

4. **Run basic tests first**:
   ```bash
   python run_integration_tests.py basic
   ```

## Test Levels

### 🟢 SAFE Tests
- **Basic Connectivity**: Socket connections, API handshake
- **Market Data**: Real-time price feeds (read-only)
- **End-to-End**: System integration without trading

### 🟡 CAUTION Tests  
- **Order Placement**: Places real orders (immediately cancelled)

## Running Tests

Use the test runner for safety:
```bash
# Show available test levels
python run_integration_tests.py --list

# Run safe connectivity tests
python run_integration_tests.py basic

# Run market data tests
python run_integration_tests.py market_data

# Enable and run order tests (CAUTION!)
export TWS_ENABLE_ORDER_TESTS=true
python run_integration_tests.py orders

# Run all tests (includes order placement!)
python run_integration_tests.py all
```

## Manual Test Execution

If you prefer to run tests manually:
```bash
# Basic tests (always safe)
pytest tests/integration/test_basic_tws_connection.py -v
pytest tests/integration/test_tws_connection.py -v

# Market data tests (safe - read only)
pytest tests/integration/test_market_data_tws.py -v

# Order tests (CAUTION - places real orders)
export TWS_ENABLE_ORDER_TESTS=true
pytest tests/integration/test_order_placement_tws.py -v

# End-to-end tests
pytest tests/integration/test_e2e_trading_workflow.py -v
```

## What Gets Tested

### Basic Connectivity
- TWS socket connection
- API handshake and authentication
- Basic API calls (time, accounts, order IDs)
- Connection timeout behavior

### Market Data
- Real-time price subscriptions
- Multiple symbol handling
- Market data validation
- Error handling for invalid symbols

### Order Placement (⚠️ CAUTION)
- Market order placement/cancellation
- Limit order lifecycle
- Order rejection handling
- Multiple order management
- **Safety**: Uses 1-share quantities, immediate cancellation

### End-to-End Workflows
- Complete system integration
- Event-driven architecture testing
- Error handling workflows
- Reconnection testing
- Basic performance metrics

## Troubleshooting

### Tests Skip with "TWS not available"
- Ensure TWS is running
- Check TWS is on port 7497 (paper trading)
- Verify API is enabled in TWS settings
- Check firewall isn't blocking connections

### Order tests are skipped
- Set `TWS_ENABLE_ORDER_TESTS=true` environment variable
- Ensure you're using paper trading account
- Never run against live accounts

### Connection timeouts
- TWS may be busy or overloaded
- Try increasing timeout in test configuration
- Restart TWS and try again

## Next Steps

After basic integration tests pass, consider:
1. **Real Trading Validation**: Test with actual order fills
2. **Risk Management Testing**: Validate stop losses, position limits
3. **Performance Testing**: Load testing with multiple symbols
4. **Extended Runtime Testing**: 24+ hour stability tests

See `tests/COMPREHENSIVE_TESTING_STRATEGY.md` for complete testing roadmap. 