# OrderManager Migration to Alpaca

## Overview

The OrderManager has been successfully migrated from Interactive Brokers (IBKR/TWS) to work exclusively with Alpaca. This document describes the changes made and how to use the updated OrderManager.

## Key Changes

### 1. Removed IBKR Dependencies

- Removed all `ibapi` imports and IB-specific code
- Removed `_create_ib_contract()` and `_create_ib_order()` methods
- Removed TWS-specific order ID management

### 2. Updated Connection Handling

```python
# Old (IBKR)
order_manager = OrderManager(event_bus, tws_connection)

# New (Alpaca)
order_manager = OrderManager(event_bus, broker_connection)  # AlpacaConnection instance
```

### 3. Order Type Mapping

The OrderManager now automatically converts internal order types to Alpaca format:

| Internal OrderType | Alpaca Format |
|-------------------|---------------|
| OrderType.MARKET | 'MKT' |
| OrderType.LIMIT | 'LMT' |
| OrderType.STOP | 'STP' |
| OrderType.STOP_LIMIT | 'STP_LMT' |

### 4. Time in Force Mapping

| Internal TimeInForce | Alpaca Format |
|---------------------|---------------|
| TimeInForce.DAY | 'DAY' |
| TimeInForce.GTC | 'GTC' |
| TimeInForce.IOC | 'IOC' |
| TimeInForce.FOK | 'FOK' |

## Usage Example

```python
import asyncio
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.order.base import OrderType, TimeInForce
from src.alpaca_connection import AlpacaConnection
from src.alpaca_config import AlpacaConfig

async def main():
    # Create event bus
    event_bus = EventBus()
    
    # Create Alpaca connection
    config = AlpacaConfig.from_env()
    alpaca_conn = AlpacaConnection(config)
    await alpaca_conn.connect()
    
    # Create OrderManager
    order_manager = OrderManager(event_bus, alpaca_conn)
    await order_manager.initialize()
    
    # Create and submit a market order
    order = await order_manager.create_order(
        symbol="AAPL",
        quantity=10,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        auto_submit=True
    )
    
    # Create a bracket order
    bracket = await order_manager.create_bracket_order(
        symbol="TSLA",
        quantity=5,
        entry_type=OrderType.MARKET,
        stop_loss_price=180.00,
        take_profit_price=220.00,
        auto_submit=True
    )
    
    # Get active orders
    active_orders = await order_manager.get_active_orders()
    
    # Cancel an order
    await order_manager.cancel_order(order.order_id)

if __name__ == "__main__":
    asyncio.run(main())
```

## Order Lifecycle

1. **Order Creation**: Orders are created with `create_order()` or specialized methods like `create_bracket_order()`
2. **Order Submission**: Orders are submitted to Alpaca via `submit_order()` or `auto_submit=True`
3. **Order Tracking**: Orders are tracked internally and mapped to Alpaca order IDs
4. **Status Updates**: Order status updates are received via WebSocket callbacks (when implemented)
5. **Fill Processing**: Fills are processed and tracked via `process_fill()`
6. **Order Completion**: Orders move to completed state when filled, cancelled, or rejected

## Event System Integration

The OrderManager emits the following events:

- `NewOrderEvent`: When an order is created
- `OrderStatusEvent`: When order status changes
- `FillEvent`: When an order is filled (partially or fully)
- `CancelEvent`: When an order is cancelled
- `RejectEvent`: When an order is rejected
- `OrderGroupEvent`: When an order group (bracket, OCO) is created

## Error Handling

- Connection errors are caught and orders are rejected with appropriate error messages
- If no connection is available, orders can be simulated for testing
- All errors are logged with detailed information

## Testing

The OrderManager can be tested with or without a live Alpaca connection:

```python
# Test with simulated orders (no connection)
order_manager = OrderManager(event_bus, None)
await order_manager.initialize()

# Orders will be simulated
order = await order_manager.create_order(
    symbol="AAPL",
    quantity=10,
    auto_submit=True
)
```

## Migration Checklist

- [x] Remove all IBKR/TWS imports and dependencies
- [x] Update constructor to accept AlpacaConnection
- [x] Convert order types to Alpaca format
- [x] Handle Alpaca-specific order submission
- [x] Update order cancellation for Alpaca
- [x] Fix method compatibility issues (async/sync)
- [x] Update documentation
- [x] Create comprehensive tests
- [x] Verify event system integration

## Known Limitations

1. **Order Callbacks**: The current implementation doesn't fully utilize Alpaca's WebSocket callbacks for order updates. This can be enhanced by implementing proper callback registration in AlpacaConnection.

2. **Broker Order ID**: Currently using client order ID as broker order ID. In production, this should be the actual Alpaca order ID returned from the submission.

3. **Advanced Order Types**: Only basic order types (market, limit, stop, stop-limit) are supported. Alpaca's advanced order types (trailing stop, etc.) can be added as needed.

## Future Enhancements

1. Implement full WebSocket callback integration for real-time order updates
2. Add support for Alpaca's advanced order types
3. Implement order modification capabilities
4. Add support for extended hours trading
5. Implement position-based order validation 