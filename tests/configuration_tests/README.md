# Configuration and Setup Tests

This directory contains tests for system configuration, API connections, and trading setup validation.

## Test Files

### 1. `test_api_connection.py`
**Purpose:** Basic API connection test.
- Verifies connection to prediction API
- Tests environment variable configuration
- Validates API response format

### 2. `test_position_sizing.py`
**Purpose:** Tests position sizing calculations.
- Validates Kelly Criterion implementation
- Tests position size limits
- Verifies risk management calculations

### 3. `test_buy_sell_enhancement.py`
**Purpose:** Tests enhanced buy/sell signal processing.
- Tests signal filtering logic
- Validates confidence thresholds
- Tests signal enhancement features

### 4. `test_updated_configurations.py`
**Purpose:** Tests system configuration updates.
- Validates configuration changes
- Tests parameter updates
- Verifies configuration persistence

### 5. `quick_test.py`
**Purpose:** Quick system validation test.
- Basic smoke test for system components
- Rapid validation of core functionality
- Quick health check

## Key Features Tested

### API Configuration
- Environment variable setup
- API endpoint connectivity
- Authentication and credentials

### Position Sizing
- Kelly Criterion calculations
- Maximum position limits
- Risk-based sizing

### Signal Processing
- Confidence threshold filtering
- Signal enhancement logic
- Buy/sell decision making

## Running the Tests

Most of these tests can run without TWS connection:

```bash
cd tests/configuration_tests
python test_name.py
```

Note: `test_api_connection.py` requires valid API credentials in environment variables. 