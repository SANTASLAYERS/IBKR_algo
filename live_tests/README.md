# Live Testing Suite

This directory contains live tests that use real TWS (Trader Workstation) connections to validate trading system components with actual market data.

## Overview

The live tests validate our trading system components using real TWS connections and market data:

- **Price Service**: Real-time price fetching from TWS
- **Position Sizing**: Dynamic position calculations with real prices  
- **ATR System**: 10-second ATR calculations with actual market data
- **Complete Integration**: End-to-end component integration testing

## Test Files

### `test_price_service_live.py`
Tests the PriceService component with real TWS market data:
- Single ticker price fetching
- Our actual trading tickers (CVNA, UVXY, SOXL, SOXS, TQQQ, SQQQ, GLD, SLV)
- Concurrent price fetching
- Error handling with invalid tickers

### `test_position_sizing_live.py`
Tests position sizing with real market prices:
- Position calculations using actual current prices
- Efficiency validation for $10K allocations
- Extreme price scenario testing
- Multiple allocation amounts

### `test_atr_system_live.py`
Tests ATR indicator system with real 10-second market data:
- ATR calculations for individual tickers
- Our actual trading tickers with 6x/3x multipliers
- Different ATR periods comparison
- Realistic stop-loss scenarios

### `test_component_integration_live.py`
Tests complete component integration:
- End-to-end trading decision flow
- Multi-ticker simultaneous processing
- Error resilience testing
- Performance validation

## Requirements

### TWS/IB Gateway Setup
1. **TWS or IB Gateway running**:
   - Paper Trading: Port 7497 (default)
   - Live Trading: Port 7496
   
2. **API Settings**:
   - Enable ActiveX and Socket Clients
   - Socket port: 7497 (paper) or 7496 (live)
   - Trusted IP addresses: 127.0.0.1
   - Read-Only API: No (we need market data)

3. **Market Data Subscription**:
   - Free delayed data available for testing
   - Real-time data requires market data subscriptions
   - IBKR Pro accounts include basic US equity data

### Environment Variables
Set these environment variables to configure TWS connection:

```bash
# TWS Connection Settings
export TWS_HOST=127.0.0.1         # TWS hostname
export TWS_PORT=7497               # TWS port (7497=paper, 7496=live)
export TWS_CLIENT_ID=10            # Unique client ID
export TWS_ACCOUNT=DU1234567       # Your IBKR account number

# Optional: Force tests even if TWS appears unavailable
export TWS_FORCE_TESTS=true
```

## Running Tests

### Prerequisites Check
First, ensure TWS is running and accessible:

```bash
# Quick connectivity check
python -m live_tests.test_price_service_live
```

### Run Individual Test Suites

```bash
# Test price service
pytest live_tests/test_price_service_live.py -v

# Test position sizing
pytest live_tests/test_position_sizing_live.py -v

# Test ATR system
pytest live_tests/test_atr_system_live.py -v

# Test complete integration
pytest live_tests/test_component_integration_live.py -v
```

### Run All Live Tests

```bash
# Run all live tests
pytest live_tests/ -v

# Run with force flag (skip TWS availability check)
pytest live_tests/ -v --force-tws

# Run only live tests (if you have both unit and live tests)
pytest live_tests/ -v --live-only
```

### Manual Testing
Each test file includes a manual test runner for quick validation:

```bash
# Manual price service test
python live_tests/test_price_service_live.py

# Manual position sizing test  
python live_tests/test_position_sizing_live.py

# Manual ATR system test
python live_tests/test_atr_system_live.py

# Manual integration test
python live_tests/test_component_integration_live.py
```

## Test Coverage

### Market Data Testing
- ✅ Real-time price fetching
- ✅ Multiple ticker processing
- ✅ Concurrent price requests
- ✅ Error handling for invalid symbols
- ✅ Performance validation

### Position Sizing Testing
- ✅ Dynamic position calculations with real prices
- ✅ Allocation efficiency validation (>95%)
- ✅ Safety limits (min/max shares)
- ✅ Edge case handling

### ATR System Testing
- ✅ 10-second bar ATR calculations
- ✅ Multiple period comparisons (7, 14, 21)
- ✅ Stop-loss/profit-target multipliers (6x/3x)
- ✅ Risk/reward ratio validation (1:0.5)

### Integration Testing
- ✅ Complete trading decision flow
- ✅ Multi-ticker simultaneous processing
- ✅ Error resilience with invalid data
- ✅ Performance benchmarking
- ✅ Component interaction validation

## Expected Results

### During Market Hours
- Price fetching: Success rate >90%
- ATR calculations: Success rate >75%
- Position sizing: 99%+ efficiency
- Complete flow: <45 seconds total time

### Outside Market Hours
- Price fetching: May use delayed/cached data
- ATR calculations: May have limited data
- Position sizing: Should still work with available prices
- Some tests may be skipped automatically

## Troubleshooting

### Common Issues

**"TWS not available"**
- Check TWS/IB Gateway is running
- Verify API settings are enabled
- Check port numbers (7497 for paper, 7496 for live)
- Ensure client ID is unique

**"No market data available"**
- Check market data subscriptions
- Verify market hours for specific symbols
- Some symbols may not have real-time data
- Free accounts get delayed data

**"Connection timeout"**
- TWS may be busy with other connections
- Try different client ID
- Check network connectivity
- Restart TWS if needed

**"Permission denied"**
- Check TWS API configuration
- Ensure IP address 127.0.0.1 is trusted
- Verify account permissions

### Debug Mode
Enable detailed logging for troubleshooting:

```bash
# Run with debug logging
pytest live_tests/ -v -s --log-cli-level=DEBUG

# Or set environment variable
export LOG_LEVEL=DEBUG
pytest live_tests/ -v
```

## Safety Notes

### Paper Trading Recommended
- Live tests use real TWS connections but **DO NOT place actual orders**
- Tests only fetch market data and perform calculations
- Use paper trading account (port 7497) for safety
- No actual trades or account modifications occur

### Rate Limiting
- Tests include delays between requests to be respectful to TWS
- Concurrent requests are limited and controlled
- Tests automatically throttle if needed

### Error Handling
- All tests include comprehensive error handling
- Invalid symbols and network issues are handled gracefully
- Tests will not crash or corrupt TWS state
- Connection cleanup is guaranteed

## Performance Benchmarks

### Expected Performance
- Price fetch: <5 seconds per ticker
- ATR calculation: <20 seconds per ticker  
- Position sizing: <0.1 seconds
- Complete integration: <45 seconds total

### Optimization Notes
- Concurrent requests improve performance
- 10-second ATR requires more data, takes longer
- Network latency affects performance
- Market hours vs. off-hours data availability varies

## Integration with Main System

These live tests validate the same components used in the main trading application:

- `src/price/service.py` - Price fetching
- `src/position/sizer.py` - Position sizing
- `src/indicators/manager.py` - ATR calculations
- `src/tws_connection.py` - TWS connectivity

Successful live tests confirm the main trading system will work correctly with real market data and TWS connections. 