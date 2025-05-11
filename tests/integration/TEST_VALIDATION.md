# IB Gateway Test Validation Guide

This document explains how to interpret test results and determine success/failure criteria for IB Gateway integration tests.

## Understanding IB Gateway Responses

Interactive Brokers Gateway communicates using:

1. **Callbacks**: Asynchronous notifications for events and data
2. **Error codes**: Specific codes for various error conditions
3. **Status updates**: Order and connection state transitions
4. **Data responses**: Market data, account values, positions, etc.

Tests must validate responses across multiple channels to determine success.

## Response Types and Success Criteria

### 1. Order Placement Validation

A successful order placement test should check:

| Response Type | Success Criteria | Failure Indicators |
|---------------|------------------|-------------------|
| Order ID | Positive integer (>0) | Negative or zero ID |
| Order Status | 'Submitted', 'PreSubmitted', 'Filled' | 'Rejected', 'Error', no status received |
| Error Callbacks | No error for order ID | Error code with order ID |
| Fill Notifications | Execution details match order (for market orders) | No execution received (for market orders) |

Error codes to watch for:
- 104: Can't modify a filled order
- 201: Order rejected - reason text explains why
- 202: Order cancelled
- 399: Order message error - check order fields

### 2. Market Data Validation

A successful market data test should check:

| Response Type | Success Criteria | Failure Indicators |
|---------------|------------------|-------------------|
| Subscription ID | Positive integer (>0) | Negative or zero ID |
| Data Callbacks | Data contains price fields | No data received, empty fields |
| Error Callbacks | No error for request ID | Error with request ID |
| Data Integrity | Bid ≤ Ask, High ≥ Low, etc. | Inconsistent price data |

Error codes to watch for:
- 10: Cannot find requested historical data
- 162: Historical market data service error
- 200: No security definition found for contract
- 354: Requested market data is not subscribed

### 3. Connection Validation

A successful connection test should check:

| Response Type | Success Criteria | Failure Indicators |
|---------------|------------------|-------------------|
| Connection Status | is_connected() returns True | is_connected() returns False |
| Heartbeat | Current time callbacks received | No responses to heartbeat requests |
| Account Data | Account values retrieved | No account data received |
| Error Callbacks | No connection errors | Error codes 326, 502, 504, etc. |

Error codes to watch for:
- 326: Unable to connect to TWS
- 502: Socket closed unexpectedly
- 504: Not connected

## Multi-faceted Test Validation

For robust validation, tests should check multiple conditions:

1. **Primary Check**: Direct response from the action
   - Example: Order ID > 0 when placing an order

2. **Secondary Check**: Follow-up state verification
   - Example: Order appears in active orders list

3. **Error Check**: No relevant errors received
   - Example: No error callbacks with the request ID

4. **Timeout Check**: Response received in reasonable time
   - Example: Status update within 10 seconds

## Handling Delayed Responses

IB Gateway uses callback patterns which are asynchronous. Tests should:

1. Set appropriate timeouts for each operation type
2. Use async/await patterns to handle waiting for callbacks
3. Implement proper cleanup, even when tests fail

## Pass/Fail Result Recording

For integration tests, implement detailed result tracking:

```python
# Example validation with multiple checks
def validate_order_submission(order_id, status_updates, errors):
    result = {
        "success": False,
        "checks": {
            "order_id_valid": order_id > 0,
            "status_received": any(s.get('order_id') == order_id for s in status_updates),
            "no_errors": not any(e.get('req_id') == order_id for e in errors),
            "status_acceptable": False  # Will be set below
        },
        "details": {
            "order_id": order_id,
            "status": None,
            "errors": []
        }
    }
    
    # Find status
    for update in status_updates:
        if update.get('order_id') == order_id:
            status = update.get('status')
            result['details']['status'] = status
            result['checks']['status_acceptable'] = status in ['Submitted', 'PreSubmitted', 'Filled']
    
    # Collect errors
    for error in errors:
        if error.get('req_id') == order_id:
            result['details']['errors'].append(error)
    
    # Overall success
    result['success'] = all(result['checks'].values())
    
    return result
```

## Test Logging for Diagnosis

For tests that may fail due to external systems, implement comprehensive logging:

1. Log all requests sent to IB Gateway
2. Log all callbacks received from IB Gateway
3. Log validation checks performed
4. For failures, log detailed diagnostic information

This enables troubleshooting when tests fail due to network issues, market conditions, or API changes.