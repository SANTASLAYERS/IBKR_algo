# Order System IBKR Gateway Integration

## Overview

This document describes the integration between the Order Management System and the Interactive Brokers Gateway in the IBKR Trading Framework. This integration enables the system to place real orders with Interactive Brokers, receive order status updates, and process execution reports, forming a complete bidirectional communication path.

## Architecture

The integration follows these key principles:

1. **Clean separation of concerns** between the Order Management System and the IB Gateway
2. **Bidirectional communication** with order submission and status updates
3. **Unified event system** for consistent notification of order state changes
4. **Error resilience** with proper error handling and reconnection support

### Components

The integration consists of these key components:

#### OrderManager (`src/order/manager.py`)

- Manages the lifecycle of orders
- Converts internal order objects to IB API format
- Submits orders to the IB Gateway
- Processes status updates from IB Gateway

#### IBGateway (`src/gateway.py`)

- Provides connection to Interactive Brokers API
- Submits orders to IB and receives status updates
- Handles executions and commission reports
- Routes callbacks to the appropriate handlers

#### OrderGatewayIntegration (`src/gateway_order_manager.py`)

- Connects the OrderManager with IBGateway
- Sets up callbacks for order status updates
- Processes execution details and commissions
- Provides initialization and shutdown management

## Order Flow

### Order Submission

1. **OrderManager** receives a request to create an order
2. Order is created with `CREATED` status
3. Submit request triggers conversion to IB API format
4. IBGateway submits the order to Interactive Brokers
5. Order status is updated to `PENDING_SUBMIT`
6. `OrderStatusEvent` is emitted on the event bus

### Order Status Updates

1. IB sends order status updates to IBGateway
2. Gateway routes updates to the OrderGatewayIntegration
3. Integration converts IB status to internal status
4. OrderManager updates the order status
5. `OrderStatusEvent` is emitted on the event bus

### Order Fills

1. IB sends execution details to IBGateway
2. Gateway routes execution details to OrderGatewayIntegration
3. Integration maps execution to the appropriate order
4. Commission reports are associated with executions
5. OrderManager processes the fill
6. `FillEvent` is emitted on the event bus

### Order Cancellation

1. OrderManager receives a request to cancel an order
2. Internal order status is updated to `PENDING_CANCEL`
3. IBGateway sends cancellation request to IB
4. IB confirms cancellation via status update
5. OrderManager updates order status to `CANCELLED`
6. `CancelEvent` is emitted on the event bus

## Status Mapping

| IB Status | System Status |
|-----------|---------------|
| PendingSubmit | PENDING_SUBMIT |
| PreSubmitted | ACCEPTED |
| ApiPending | ACCEPTED |
| Submitted | SUBMITTED |
| ApiCancelled | CANCELLED |
| Cancelled | CANCELLED |
| Filled | FILLED |
| Partially Filled | PARTIALLY_FILLED |
| PendingCancel | PENDING_CANCEL |
| Inactive | INACTIVE |

## Setup

To enable the IBKR Gateway integration with the Order Management System:

```python
from src.gateway import IBGateway, IBGatewayConfig
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.gateway_order_manager import OrderGatewayIntegration

# Create components
event_bus = EventBus()
config = IBGatewayConfig(
    host="127.0.0.1",
    port=4002,  # Paper trading port
    client_id=1,
    account_id="YOUR_ACCOUNT_ID",
    trading_mode="paper"
)
gateway = IBGateway(config)
order_manager = OrderManager(event_bus)

# Create and initialize the integration
integration = OrderGatewayIntegration(gateway, order_manager)
integration.initialize()

# Connect to IB Gateway
await gateway.connect_gateway()

# Now OrderManager and IBGateway are connected and ready to use
```

## Testing

The integration can be tested using two approaches:

### 1. Simulated Environment (No Gateway)

The Order Manager can operate without a real IB Gateway connection, simulating order submission and status updates. This is useful for development and testing without a live connection.

### 2. Integration Testing with Paper Trading

For real integration testing, connect to the IB Gateway in paper trading mode:

```bash
# Run integration tests for order system
pytest tests/test_order_ibkr_integration.py
```

The integration tests validate:
- Order submission and tracking
- Status updates from IB
- Order cancellation
- Bracket order creation and management

## Common Issues

1. **Order ID Conflicts**: IBKR requires unique order IDs. Ensure client IDs are unique across connections.
2. **Connection Issues**: If the Gateway disconnects, orders may be in an unknown state. Implement reconciliation logic.
3. **Gateway Timeouts**: Add proper timeout handling for order operations.
4. **Error Handling**: Process IB API errors and update order status accordingly.

## Future Enhancements

1. **Order Recovery**: Implement order state recovery after reconnection
2. **Advanced Order Types**: Add support for more complex order types
3. **Performance Optimization**: Batch order operations for better throughput
4. **Order History**: Add persistent storage for order history