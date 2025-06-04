# ATR (Average True Range) Tests

This directory contains tests related to ATR calculations and ATR-based stop loss functionality.

## Test Files

### 1. `test_atr_with_tws.py`
**Purpose:** Tests ATR calculation using live TWS connection.
- Verifies historical data retrieval from TWS
- Tests ATR calculation accuracy
- Validates timezone handling

### 2. `test_atr_config.py`
**Purpose:** Tests ATR configuration and parameter settings.
- Tests different ATR periods
- Validates ATR multiplier configurations
- Tests ATR-based stop loss calculations

### 3. `test_atr_stops.py`
**Purpose:** Tests ATR-based stop loss order creation.
- Verifies stop loss placement based on ATR
- Tests dynamic stop adjustment
- Validates stop loss order parameters

### 4. `test_atr_10_second_bars.py`
**Purpose:** Tests ATR calculation with 10-second bar data.
- Tests high-frequency ATR calculations
- Validates short-term volatility measurements
- Tests real-time ATR updates

## Common Issues Fixed

### Historical Data Issues
- **Problem:** Missing timezone in IB API date requests
- **Fix:** Added " UTC" suffix to date strings

### Date Parsing Issues
- **Problem:** Unix timestamps returned as strings
- **Fix:** Added string timestamp parsing logic

### Variable Naming
- **Problem:** Inconsistent `req_id` vs `reqId` usage
- **Fix:** Standardized variable naming throughout

## Running the Tests

These tests require a live TWS connection with market data subscriptions.

```bash
cd tests/atr_tests
python test_name.py
``` 