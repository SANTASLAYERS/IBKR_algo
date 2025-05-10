# IB Gateway Testing Guidelines

This document provides guidelines for creating tests that connect to the Interactive Brokers Gateway.

**IMPORTANT:** While mocks are useful for unit testing, testing against the actual IB Gateway provides the most reliable verification of functionality. Always prefer real Gateway testing for integration and end-to-end tests whenever possible.

## Connection Parameters

When creating tests that need to connect to the IB Gateway, always use the following configuration:

```python
# Use these connection parameters for reliable testing
host = "172.28.64.1"  # Working IB Gateway host
port = 4002           # Paper trading port
client_id = 1         # Use unique client IDs for concurrent tests
```

## Test Implementation Best Practices

1. **Always check connectivity first**:
   ```python
   # Verify Gateway is reachable before running tests
   is_running = await gateway._is_gateway_running()
   if not is_running:
       logger.warning("IB Gateway not available at 172.28.64.1:4002")
       # Handle appropriately (skip test, report failure, etc.)
   ```

2. **Use appropriate timeouts**:
   ```python
   # Use longer heartbeat timeouts for data-intensive operations
   config = IBGatewayConfig(
       host="172.28.64.1",
       port=4002,
       client_id=client_id,
       heartbeat_timeout=20.0,   # Longer timeout for data requests
       heartbeat_interval=5.0
   )
   ```

3. **Clean up connections**:
   ```python
   # Always disconnect when done
   try:
       # Test code here
   finally:
       if gateway.is_connected():
           gateway.disconnect()
           logger.info("Disconnected from IB Gateway")
   ```

4. **Use unique client IDs for concurrent tests**:
   ```python
   # Generate a unique client ID to avoid conflicts
   import random
   client_id = random.randint(100, 999)  # Or use a more sophisticated approach
   ```

## Handling Errors

Common IB Gateway errors and how to handle them:

1. **Connection Errors (502)**:
   - This typically means the Gateway isn't running or is unreachable
   - Try alternate host/port configurations
   - Skip tests if Gateway is unavailable

2. **Pacing Violations (162)**:
   - IB limits the rate of historical data requests
   - Implement exponential backoff or request throttling
   - Combine requests where possible to reduce API calls

3. **Data Not Available Errors**:
   - Some data may not be available for certain securities or timeframes
   - Implement graceful fallbacks or skip tests for unavailable data

## Example Test Setup

```python
import asyncio
import logging
from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler

async def test_feature():
    """Test a feature that requires IB Gateway connectivity."""
    # Create configuration
    config = IBGatewayConfig(
        host="172.28.64.1",
        port=4002,
        client_id=1,
        heartbeat_timeout=20.0,
        heartbeat_interval=5.0
    )
    
    # Create gateway
    error_handler = ErrorHandler()
    gateway = IBGateway(config, error_handler)
    
    try:
        # Connect to IB Gateway
        connected = await gateway.connect_async()
        if not connected:
            logger.error("Failed to connect to IB Gateway")
            return False
        
        # Perform test operations
        # ...
        
        return True
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        return False
    finally:
        # Clean up
        if gateway.is_connected():
            gateway.disconnect()
```

## Recommended Testing Pattern

For features requiring IB Gateway:

1. First test with `gateway._is_gateway_running()` to verify connectivity
2. If connected, proceed with feature-specific tests
3. Implement timeout and retry logic appropriate for the operation
4. Always disconnect in a finally block
5. Log both successes and failures with appropriate detail

By following these guidelines, tests will connect reliably to the IB Gateway and produce consistent results.