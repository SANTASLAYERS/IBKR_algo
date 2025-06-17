# Alpaca Connection Implementation

## Overview

The `AlpacaConnection` class provides direct integration with Alpaca Markets API for automated trading. This implementation handles all aspects of connecting to Alpaca, managing orders, and receiving real-time updates.

## Key Features

- **REST API Integration**: Full support for Alpaca's REST API endpoints
- **WebSocket Streaming**: Real-time trade updates and market data
- **Order Management**: Place, cancel, and track orders
- **Position Tracking**: Monitor open positions and P&L
- **Paper/Live Trading**: Support for both paper and live trading modes

## Architecture

```
AlpacaConnection
├── REST API Client (TradingClient)
├── WebSocket Streams
│   ├── Trading Stream (order updates)
│   └── Data Stream (market data)
├── Order Management
│   ├── Order Placement
│   ├── Order Cancellation
│   └── Order Status Tracking
└── Account Management
    ├── Account Info
    └── Position Queries
```

## Configuration

The connection uses `AlpacaConfig` for configuration:

```python
config = AlpacaConfig(
    api_key="your_api_key",
    secret_key="your_secret_key",
    trading_mode="paper"  # or "live"
)
```

## Connection Lifecycle

1. **Initialization**: Create connection instance with config
2. **Connect**: Establish connection to Alpaca
3. **Authenticate**: Validate API credentials
4. **Initialize Streams**: Set up WebSocket connections
5. **Ready**: Connection ready for trading

## Order Management

### Placing Orders

```python
connection.placeOrder(
    orderId="unique_order_id",
    symbol="AAPL",
    quantity=100,
    order_type="LMT",
    side="BUY",
    limit_price=150.00
)
```

### Order Types Supported

- Market Orders (MKT)
- Limit Orders (LMT)
- Stop Orders (STP)
- Stop Limit Orders (STP_LMT)

### Order Status Updates

The connection provides real-time order status updates through callbacks:

```python
def on_order_status(orderId, status, filled, remaining, avgFillPrice, lastFillPrice):
    print(f"Order {orderId}: {status}")
```

## WebSocket Streaming

### Trade Updates

Real-time updates for order fills and status changes:

```python
async def on_trade_update(data):
    if data.event == "fill":
        # Handle fill event
        pass
```

### Supported Events

- `new`: New order accepted
- `fill`: Order filled (complete)
- `partial_fill`: Order partially filled
- `canceled`: Order canceled
- `rejected`: Order rejected

## Error Handling

The connection includes comprehensive error handling:

- Connection failures
- Authentication errors
- Order rejection
- Network interruptions
- Rate limiting

## Usage Example

```python
# Create connection
config = AlpacaConfig.from_env()
connection = AlpacaConnection(config)

# Set callbacks
connection.orderStatus = my_order_status_handler
connection.execDetails = my_execution_handler

# Connect
await connection.connect()

# Place an order
order_id = connection.get_next_order_id()
connection.placeOrder(
    orderId=order_id,
    symbol="AAPL",
    quantity=100,
    order_type="MKT",
    side="BUY"
)

# Cancel an order
connection.cancelOrder(order_id)

# Disconnect when done
connection.disconnect()
```

## Integration with Trading System

The AlpacaConnection integrates seamlessly with:

- **OrderManager**: Handles order lifecycle
- **EventBus**: Publishes connection and trade events
- **MinuteBarManager**: Provides historical data
- **PositionTracker**: Monitors positions

## Best Practices

1. **Connection Management**
   - Always check connection status before operations
   - Handle disconnections gracefully
   - Implement reconnection logic

2. **Order Management**
   - Use unique client order IDs
   - Track order status updates
   - Handle partial fills

3. **Error Handling**
   - Log all errors for debugging
   - Implement retry logic for transient failures
   - Monitor rate limits

4. **Testing**
   - Always test with paper trading first
   - Verify order flow in paper mode
   - Test error scenarios

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check API credentials
   - Verify network connectivity
   - Check Alpaca service status

2. **Orders Rejected**
   - Verify account permissions
   - Check buying power
   - Validate order parameters

3. **Missing Updates**
   - Check WebSocket connection
   - Verify event subscriptions
   - Check callback registration 