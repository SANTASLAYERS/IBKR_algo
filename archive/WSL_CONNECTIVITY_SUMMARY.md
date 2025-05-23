# WSL to TWS Connectivity Guide

## Overview

This document provides detailed information about connecting from Windows Subsystem for Linux (WSL) to Interactive Brokers Trader Workstation (TWS) running on Windows. This is a critical component for reliable integration testing.

## Recent Updates (2025-05-16)

We've made significant improvements to the WSL-to-Windows TWS connectivity:

1. **Direct TWS Connection**: Implemented a reliable direct connection to TWS from WSL
2. **Message Processing Thread**: Added dedicated thread for handling TWS API callbacks
3. **Order & Position Management**: Fixed critical issues with order submission and position querying
4. **Connection Testing**: Added comprehensive connection test scripts (`check_tws_connection.py`, `minimal_position_test.py`)
5. **Test Fixtures**: Updated integration test fixtures for better TWS connection handling

## WSL-to-Windows Connectivity

### Key Connection Parameters

For connecting from WSL to TWS running on Windows:

- **Host IP**: `172.28.64.1` (WSL-to-Windows host IP)
- **Port**: `7497` (TWS paper trading)
- **Client ID**: Configurable, with `1` as default

### Connection Flow

1. WSL application creates socket connection to `172.28.64.1:7497`
2. Windows host receives connection via its WSL network adapter
3. TWS accepts the connection if API connections are enabled
4. Initial handshake establishes the TWS API session

## Technical Details

### Network Architecture

WSL has its own virtual network, with the Windows host accessible via a specific IP. In WSL 2:

```
WSL VM (172.28.xx.xx) <--> Windows Host (172.28.64.1) <--> TWS (localhost:7497)
```

This means that from WSL, you must connect to `172.28.64.1` instead of `localhost` to reach programs running on Windows.

### Connectivity Testing

Use these commands to verify your WSL-to-Windows connectivity:

```bash
# Test TCP connectivity to TWS
nc -vz 172.28.64.1 7497

# Check network route to Windows host
ip route | grep 172.28.64.1
```

### Common Issues

1. **Connection Timeout**:
   - TWS not running or API not enabled
   - Windows Firewall blocking connection
   - Incorrect host/port configuration

2. **Handshake Failure**:
   - Connection established but API handshake fails
   - TWS API configuration issue (read-only, trusted IPs)
   - Client ID already in use

3. **Intermittent Connectivity**:
   - Windows host IP changes after WSL restart
   - TWS connectivity changes when switching networks

## Configuration Steps

### 1. TWS Configuration

1. Open TWS and go to **Edit > Global Configuration > API > Settings**
2. Enable API connections
3. Add the WSL IP range to trusted IPs (e.g., `172.28.0.0/16`)
4. Set socket port to `7497`
5. Disable "Read-Only API" unless specifically needed

### 2. Windows Firewall

1. Open Windows Defender Firewall with Advanced Security
2. Create a new Inbound Rule
3. Select "Port" as the rule type
4. Specify TCP port 7497
5. Allow the connection
6. Apply to Domain, Private, and Public networks
7. Name the rule "TWS API Connection"

### 3. WSL Configuration

No special configuration is needed in WSL, but you should use the correct connection parameters in your code:

```python
# Example connection code
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class IBConnection(EWrapper, EClient):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

# Connect using WSL-to-Windows parameters
conn = IBConnection()
conn.connect("172.28.64.1", 7497, clientId=1)
```

## Implementation Details

### Connection Approach

The new implementation connects to TWS running on Windows from WSL using:
- Windows host IP (172.28.64.1) for cross-environment connectivity
- TWS paper trading port (7497) for non-production testing
- Fixed client ID (1) for connection consistency
- Session-scoped connection for all tests to prevent throttling

### Test Execution Flow

1. A single TWS connection is established at the beginning of the test suite
2. All tests share this connection, avoiding reconnection overhead
3. Each test performs its specific validation
4. Cleanup occurs after each test to reset state
5. The connection is properly closed at the end of the test suite

### Benefits Over Previous Approach

1. **Reliability**: TWS provides more stable connections than Gateway for WSL
2. **Simplicity**: Avoids Gateway authentication complexity
3. **Performance**: Single connection reduces test execution time
4. **Maintainability**: Consistent approach across development and CI environments

## Diagnostics

### Simple Connection Test

You can run a simple connection test to verify TWS connectivity:

```bash
python simple_direct_test.py
```

This script implements a minimal connection to TWS and reports success or detailed errors.

### Error Messages and Fixes

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| Connection refused | TWS not running or firewall blocking | Start TWS and check firewall settings |
| Connection timeout | Incorrect host/port | Verify TWS is accepting connections |
| Socket error | Network configuration issue | Check TWS API settings |
| Client ID 1 already in use | Another application connected | Use a different client ID |

## Multiple Connections

To run multiple connections to TWS simultaneously:

1. Use different client IDs for each connection
2. Ensure TWS is configured to accept multiple connections
3. Be aware of TWS API rate limits
4. Consider using the `run_multiple_tws_tests.py` script for parallel testing

Example of running multiple tests:

```bash
python run_multiple_tws_tests.py --clients 3
```

This will run 3 separate test instances with client IDs 1, 2, and 3.

## Usage Instructions

To run integration tests with the new TWS connection:

```bash
# Set environment variables if needed
export IB_HOST=172.28.64.1  # Windows host IP from WSL
export IB_PORT=7497         # TWS paper trading port
export IB_CLIENT_ID=1       # Client ID

# Run all integration tests
python run_integration_tests.py

# Run specific test file
python run_integration_tests.py tests/integration/test_tws_integration.py
```

## Best Practices

1. **Use Direct Connection**: Avoid proxies or unnecessary network abstractions
2. **Single Client ID**: Maintain a consistent client ID (e.g., 1)
3. **Check TWS Status**: Verify TWS is running before tests
4. **Use Session-Scoped Connections**: Reuse connections when possible
5. **Implement Proper Cleanup**: Close connections and cancel orders after tests

## Troubleshooting

### WSL Networking Issues

If WSL networking changes after system restart:

1. Check your current WSL IP: `ip addr show eth0`
2. Verify Windows host IP: `ip route | grep default`
3. Update connection parameters if needed

### TWS Configuration Issues

If TWS rejects connections:

1. Verify API settings in TWS
2. Check trusted IP configuration
3. Restart TWS and try again
4. Check TWS API connectivity from Windows applications first

## References

- [Interactive Brokers API Documentation](https://interactivebrokers.github.io/tws-api/)
- [WSL Networking Documentation](https://docs.microsoft.com/en-us/windows/wsl/networking)
- [TWS API Configuration Guide](https://interactivebrokers.github.io/tws-api/initial_setup.html)