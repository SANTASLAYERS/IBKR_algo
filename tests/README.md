# Trading System Tests

This directory contains all tests for the IBKR trading system, organized by functionality.

## Test Categories

### 1. `/tws_order_management/`
**Live TWS order management tests**
- Order submission and tracking
- Duplicate trade prevention
- Context-based order management
- Stop/target/double-down order handling
- **⚠️ Warning:** These tests create REAL orders in TWS

### 2. `/atr_tests/`
**ATR (Average True Range) calculation tests**
- Historical data retrieval
- ATR calculation validation
- ATR-based stop loss testing
- Different timeframe ATR calculations

### 3. `/configuration_tests/`
**System configuration and setup tests**
- API connection validation
- Position sizing calculations
- Signal processing and enhancement
- Configuration management

### 4. `/live_tests/` (if exists)
**Live trading integration tests**
- End-to-end trading scenarios
- Real-time signal processing
- Complete trading workflows

## Running Tests

### Prerequisites
1. For TWS tests: TWS or IB Gateway must be running with API enabled
2. For API tests: Valid API credentials in environment variables
3. Python environment with all dependencies installed

### Running Individual Tests
```bash
cd tests/<category>
python test_name.py
```

### Safety Notes
- **TWS Order Management Tests**: Run only in paper trading accounts unless you want real trades
- **ATR Tests**: Require market data subscriptions
- **Configuration Tests**: Generally safe to run anytime

## Test Development Guidelines

When adding new tests:
1. Place them in the appropriate category directory
2. Include clear documentation of what the test does
3. Note any prerequisites (TWS connection, API keys, etc.)
4. Add any discovered issues and fixes to the category README

## Key Achievements

These tests helped identify and fix:
- Order submission issues (missing `auto_submit=True`)
- Order ID management problems
- Thread safety issues with TWS callbacks
- ATR calculation timezone problems
- Duplicate trade prevention
- Complex order relationship management 