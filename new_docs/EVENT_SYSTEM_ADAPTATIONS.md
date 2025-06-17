# Alpaca Event System Adaptations

## Overview

The event system has been adapted to seamlessly handle Alpaca's trade updates and convert them to the internal event format. This ensures that all existing event-driven components continue to work without modification.

## Components

### 1. AlpacaEventAdapter (`src/event/alpaca_adapter.py`)

The main component responsible for adapting Alpaca events to internal format.

**Features:**
- Status mapping from Alpaca to internal OrderStatus enum
- Fill event generation with proper quantity tracking
- Rejection and cancellation handling
- Event enrichment with Alpaca-specific data

**Key Methods:**
- `handle_trade_update(data)` - Main entry point for Alpaca trade updates
- `_handle_fill_event()` - Processes fill and partial fill events
- `_handle_rejection()` - Processes order rejections
- `_handle_cancellation()` - Processes order cancellations
- `_emit_status_update()` - Emits status change events

### 2. Status Mapping

Alpaca statuses are mapped to internal OrderStatus enum:

```python
STATUS_MAP = {
    'new': OrderStatus.CREATED,
    'partially_filled': OrderStatus.PARTIALLY_FILLED,
    'filled': OrderStatus.FILLED,
    'canceled': OrderStatus.CANCELLED,
    'rejected': OrderStatus.REJECTED,
    'pending_new': OrderStatus.SUBMITTED,
    'accepted': OrderStatus.ACCEPTED,
    # ... more mappings
}
```

### 3. Event Flow

```
Alpaca WebSocket
    ↓
AlpacaConnection.on_trade_update()
    ↓
AlpacaEventAdapter.handle_trade_update()
    ↓
    ├── OrderStatusEvent
    ├── FillEvent
    ├── CancelEvent
    └── RejectEvent
    ↓
EventBus.emit()
    ↓
Event Subscribers (UnifiedFillManager, etc.)
```

## Integration

### AlpacaConnection Updates

The AlpacaConnection now accepts an optional EventBus:

```python
connection = AlpacaConnection(config, event_bus)
```

When an EventBus is provided:
1. An AlpacaEventAdapter is automatically created
2. All trade updates are processed through the adapter
3. Appropriate events are emitted to the EventBus

### Backward Compatibility

The system maintains backward compatibility:
- Legacy callbacks (orderStatus, execDetails) still work
- Event-driven and callback-driven approaches can coexist
- No changes required to existing event subscribers

## Event Types

### OrderStatusEvent
Emitted when order status changes:
- Contains current and previous status
- Includes Alpaca order ID in order_data
- Provides status change reason

### FillEvent
Emitted when order is filled or partially filled:
- Tracks new fill quantity (not cumulative)
- Includes fill price and timestamp
- Indicates if fill is partial
- Contains execution details

### CancelEvent
Emitted when order is cancelled:
- Includes cancellation time
- Provides cancellation reason
- Contains final filled quantity

### RejectEvent
Emitted when order is rejected:
- Includes rejection reason
- Contains error details
- Provides order information

## Usage Examples

### Subscribing to Events

```python
# Create event bus
event_bus = EventBus()

# Subscribe to events
await event_bus.subscribe(OrderStatusEvent, on_order_status)
await event_bus.subscribe(FillEvent, on_fill)

# Create connection with event bus
connection = AlpacaConnection(config, event_bus)
```

### Event Handler Example

```python
async def on_fill(event: FillEvent):
    print(f"Order {event.order_id} filled:")
    print(f"  Symbol: {event.symbol}")
    print(f"  Quantity: {event.fill_quantity} @ ${event.fill_price}")
    print(f"  Remaining: {event.remaining_quantity}")
```

## Testing

Run the event system test:

```bash
python test_alpaca_events.py
```

This will:
1. Connect to Alpaca with event adapter
2. Place a test order
3. Monitor events generated
4. Test event adapter with mock data
5. Verify all event types

## Best Practices

1. **Event Subscriptions**: Subscribe to events before connecting
2. **Error Handling**: Always handle exceptions in event handlers
3. **Event Data**: Use order_data dict for Alpaca-specific information
4. **Fill Tracking**: The adapter tracks cumulative fills per order
5. **Status Changes**: Only emits status events when status actually changes

## Troubleshooting

### No Events Received
- Verify EventBus is passed to AlpacaConnection
- Check WebSocket connection is established
- Ensure event subscriptions are set up before connecting

### Duplicate Events
- The adapter tracks status to prevent duplicate status events
- Fill quantities are tracked to emit only new fills

### Missing Data
- Check Alpaca order object for available fields
- Some fields may be None during certain states 