# TWS Integration and WSL Connectivity Updates

## Overview

This document summarizes the migration from Interactive Brokers Gateway to Trader Workstation (TWS) for more reliable connectivity and testing. The codebase has been updated to use direct TWS connections with a focus on WSL-to-Windows connectivity.

## Recent Updates (2025-05-16)

We've made significant progress with the TWS integration, addressing several key issues:

1. **Message Processing Thread**: Added to ensure callbacks like `orderStatus` are properly received
2. **Order Manager Implementation**: Created a dedicated order manager for tracking orders
3. **Fixed ETradeOnly Parameter**: Resolved issues with order submission by explicitly setting `eTradeOnly=False`
4. **Callback Registration**: Improved position and order callbacks with proper registration methods
5. **Position Query Functionality**: Successfully tested position querying directly from TWS

## Implementation Details

### Connection Configuration

We've standardized on TWS connectivity with these parameters:
- Host: `172.28.64.1` (WSL-to-Windows IP)
- Port: `7497` (TWS paper trading)
- Client ID: Configurable, with `1` as default

### Architecture Changes

#### Previous Approach
- Gateway daemon with persistent connection
- Connection manager with reconnection logic
- Gateway-specific API methods

#### New Approach
- Direct TWS connections using IBKRConnection
- Simplified connection lifecycle
- Consistent TWS-compatible API methods
- Proper connection cleanup

### Implementation Files

1. **Core Connection**:
   - `/home/pangasa/IBKR/src/connection.py` - Updated with TWS connection methods
   - `/home/pangasa/IBKR/src/tws_helper.py` - Helper utilities for TWS

2. **Testing Framework**:
   - `/home/pangasa/IBKR/tests/integration/conftest.py` - Updated with TWS connection fixtures
   - `/home/pangasa/IBKR/tests/integration/connection_helper.py` - Updated helper for direct TWS connections
   - `/home/pangasa/IBKR/check_tws_connection.py` - TWS connection diagnostics
   - `/home/pangasa/IBKR/simple_direct_test.py` - Basic TWS connectivity test

3. **Documentation**:
   - `/home/pangasa/IBKR/docs/WSL_CONNECTIVITY.md` - WSL-to-Windows connectivity guide
   - `/home/pangasa/IBKR/tests/INTEGRATION_TESTING.md` - Updated test documentation

### Removed Gateway Components

The following Gateway-specific components were removed:
- `/home/pangasa/IBKR/src/gateway.py`
- `/home/pangasa/IBKR/src/gateway_order_manager.py`
- `/home/pangasa/IBKR/connection_daemon.py`
- `/home/pangasa/IBKR/connection_manager.py`
- `/home/pangasa/IBKR/test_daemon.py`
- `/home/pangasa/IBKR/test_connection_manager.py`

## Technical Challenges & Solutions

### 1. WSL-to-Windows Connectivity

**Challenge**: WSL runs in a virtual environment with a separate network stack.

**Solution**:
- Use the Windows host IP address `172.28.64.1` instead of localhost
- Configure Windows Firewall to allow connections from WSL subnet
- Configure TWS to accept API connections from WSL IP range
- Verify connectivity using `nc -vz 172.28.64.1 7497`

### 2. Test Framework Updates

**Challenge**: 
- Update test fixtures to use TWS connection
- Maintain consistent connection pattern
- Avoid connection overhead during tests
- Proper cleanup of resources

**Solution**:
- Session-scoped event loop fixture
- TWS-specific connection fixtures
- Backward compatibility layer for smooth transition
- Consistent cleanup at end of tests

### 3. API Method Standardization

**Challenge**: 
- Update API methods to work with TWS connection
- Maintain consistent naming pattern
- Support callback-based IBApi workflow

**Solution**:
- Implemented methods in IBKRConnection that follow a consistent pattern
- Standardized on lower_case_with_underscores naming (e.g., `req_current_time`)
- Added higher-level helper methods for complex operations (e.g., `subscribe_market_data`)

## New Methods in IBKRConnection

The following methods were added to IBKRConnection to provide a consistent API:

```python
# Core API methods
get_next_request_id()
req_current_time()
req_mkt_data()
cancel_mkt_data()
req_contract_details()
cancel_order()

# Higher-level helper methods
subscribe_market_data()
unsubscribe_market_data()
req_account_summary()
cancel_account_summary()
submit_order()
```

## Test Fixtures

### Primary Fixtures

1. `tws_connection` - Provides a direct TWS connection to test classes
   - This is now the recommended fixture for tests requiring a TWS connection
   - Usage: `@pytest.mark.usefixtures("tws_connection")`

2. `ib_gateway` - Legacy fixture maintained for backward compatibility during transition 
   - This redirects to the TWS connection for compatibility
   - Usage: `@pytest.mark.usefixtures("ib_gateway")`

### Usage Pattern

The test files follow this consistent pattern:
1. Use the `tws_connection` fixture for test classes
2. Access the connection via `self.connection` in test methods
3. Initialize and connect to TWS at the beginning of test suite
4. Properly disconnect and clean up at the end of tests

Example:
```python
@pytest.mark.usefixtures("tws_connection")
class TestTWSIntegration:
    """Integration tests for TWS connection."""
    
    # This will be populated by the fixture
    connection = None
    
    async def test_market_data(self):
        """Test market data subscription."""
        # Skip if no connection
        if not self.connection or not self.connection.is_connected():
            pytest.skip("TWS not available")
            
        # Test implementation
        # ...
```

## Updated Test Files

The following test files were updated to use the TWS connection pattern:

1. `tests/integration/test_order_integration.py`
2. `tests/integration/test_error_handling_integration.py`
3. `tests/integration/test_market_data_integration.py`
4. `tests/integration/test_connection_simple.py`
5. `tests/integration/test_persistent_connection.py`
6. `tests/integration/test_simplified_integration.py`
7. `tests/integration/test_tws_integration.py`

## Recommendations

1. **TWS Configuration**:
   - Enable API connections in TWS
   - Add WSL subnet to trusted IPs
   - Set socket port to 7497
   - Disable read-only API

2. **Windows Firewall**:
   - Create inbound rule for TCP port 7497
   - Allow connections from WSL subnet

3. **Testing Framework**:
   - Use session-scoped connection fixtures
   - Implement proper cleanup
   - Handle order cancellation systematically

## Running Tests

To run the integration tests:

```bash
# Run all integration tests
python -m pytest tests/integration/

# Run specific test file
python -m pytest tests/integration/test_tws_integration.py

# Run a specific test
python -m pytest tests/integration/test_simplified_integration.py::TestSimplifiedIntegration::test_tws_connection
```

Note: Tests will be skipped if TWS is not available or not properly configured.

## Simple Connection Test

For a quick connectivity check, you can run:

```bash
python simple_direct_test.py
```

This script establishes a direct connection to TWS and verifies basic functionality.

## Next Steps

1. Run the updated `check_tws_connection.py` to diagnose connectivity issues
2. Fix the intermittent test timeouts in integration tests:
   - Investigate the TWS API message processing thread and ensure it's correctly receiving callbacks
   - Update the test fixtures to better handle connection setup and teardown
3. Implement the remaining integration tests with TWS (instead of Gateway):
   - Complete the order integration tests
   - Add market data integration tests
   - Update position management tests
4. Ensure all components use the updated IBKRConnection class with order manager
5. Reference the `docs/WSL_CONNECTIVITY.md` for troubleshooting any connection issues
6. Consistently use TWS (not Gateway) for all testing from WSL

## Recent Technical Improvements (2025-05-16)

1. **Order Status Handling**:
   - Added dedicated OrderManager class for tracking order status
   - Fixed order status callbacks to use the message processing thread
   - Implemented proper error reporting for order submissions

2. **Position Management**:
   - Updated position callbacks to properly process positionEnd message
   - Added filtering for None entries in position data lists
   - Improved error handling in position queries

3. **Message Processing**:
   - Added a dedicated message processing thread to ensure callbacks are properly received
   - This fixed several issues with missing callbacks from TWS

4. **TWS-specific Fixes**:
   - Fixed a critical issue with ETradeOnly parameter causing order submission failures
   - Implemented proper account tracking from managedAccounts message
   - Added reconnection logic specific to TWS