# Order and Position Management System

## Overview

The Order and Position Management System is a core component of the Multi-Ticker IB Trading Framework. It provides a comprehensive solution for managing stock trading positions and orders with an event-driven architecture. The system integrates with external data sources, including the Options Flow Monitor API, to enable automated trading strategies based on prediction signals.

Key features include:
- Event-driven architecture for responsive trade execution
- Comprehensive position lifecycle management
- Integration with options flow prediction signals
- Support for rule-based trading strategies
- Risk management with stop-loss, take-profit, and trailing stops

## Architecture

The system follows an event-driven architecture with these key components:

1. **Event System**: A publish-subscribe pattern for decoupled communication between components
2. **Position Management**: Tracking and risk management for stock positions
3. **Order Management**: Creation, tracking, and lifecycle management of orders
4. **API Integration**: Processing prediction signals from external sources

### Component Relationships

```
┌────────────────────┐     ┌───────────────────┐
│                    │     │                   │
│   API Monitor      │────▶│   Event System    │◀───┐
│                    │     │      (Bus)        │    │
└────────────────────┘     └───────────┬───────┘    │
                                       │            │
                                       ▼            │
                           ┌───────────────────┐    │
                           │                   │    │
                           │ Position Tracker  │────┤
                           │                   │    │
                           └─────────┬─────────┘    │
                                     │              │
                                     ▼              │
                           ┌───────────────────┐    │
                           │                   │    │
                           │  Order Manager    │────┘
                           │                   │
                           └───────────────────┘
```

## Event System

The event system provides a flexible, decoupled communication mechanism between components. It is implemented in the `src/event` directory with these key files:

- `base.py`: Base event classes
- `bus.py`: Event bus implementation
- `market.py`: Market data events
- `position.py`: Position-related events
- `order.py`: Order-related events
- `api.py`: API-related events

### Event Bus

The `EventBus` class provides the central hub for event distribution:

```python
class EventBus:
    """Central event bus for distributing events to subscribers."""
    
    async def subscribe(self, event_type: Type[BaseEvent], handler: Callable):
        """Subscribe to an event type with a handler function."""
        
    async def unsubscribe(self, event_type: Type[BaseEvent], handler: Callable):
        """Unsubscribe a handler from an event type."""
        
    async def emit(self, event: BaseEvent):
        """Emit an event to all subscribed handlers."""
```

### Event Types

Key event types include:

- **Market Events**: `PriceEvent`, `VolumeEvent`
- **Position Events**: `PositionOpenEvent`, `PositionUpdateEvent`, `PositionCloseEvent`
- **Order Events**: `OrderCreatedEvent`, `OrderSubmittedEvent`, `OrderFilledEvent`
- **API Events**: `PredictionSignalEvent`

## Position Management

The position management system tracks and manages stock positions with risk controls. It is implemented in the `src/position` directory with these key files:

- `base.py`: Base position class
- `stock.py`: Stock position implementation
- `tracker.py`: Position tracking and management

### Position Class

The `Position` class represents a trading position:

```python
class Position:
    """Base class for all position types."""
    
    def __init__(self, symbol: str, position_id: Optional[str] = None):
        """Initialize a position."""
        self.symbol = symbol
        self.position_id = position_id or str(uuid.uuid4())
        self.status = PositionStatus.PLANNED
        self.entry_price = None
        self.quantity = 0
        self.unrealized_pnl = 0.0
        # Risk management parameters
        self.stop_loss = None
        self.take_profit = None
        self.trailing_stop = None
        
    async def open(self, quantity: int, entry_price: float):
        """Open a position with a specified quantity and entry price."""
        
    async def update(self, current_price: float):
        """Update position with current market price."""
        
    async def close(self, exit_price: float, reason: str = "manual"):
        """Close the position."""
```

### Position Tracker

The `PositionTracker` class manages multiple positions:

```python
class PositionTracker:
    """Tracks and manages multiple positions."""
    
    def __init__(self, event_bus: EventBus):
        """Initialize with event bus."""
        self.positions = {}
        self.event_bus = event_bus
        
    async def create_position(self, symbol: str, **kwargs) -> Position:
        """Create a new position."""
        
    async def get_position(self, position_id: str) -> Optional[Position]:
        """Get a position by ID."""
        
    async def update_positions(self, market_data: Dict[str, float]):
        """Update all positions with latest market data."""
        
    async def close_position(self, position_id: str, reason: str = "manual"):
        """Close a position."""
```

## Order Management

The order management system handles the creation, submission, and tracking of orders. It is implemented in the `src/order` directory with these key files:

- `base.py`: Base order class and enums
- `group.py`: Order group management
- `manager.py`: Order tracking and execution

### Order Class

The `Order` class represents a trade order:

```python
class Order:
    """Base class for all order types."""
    
    def __init__(
        self,
        symbol: str,
        quantity: int,
        order_type: OrderType,
        order_id: Optional[str] = None
    ):
        """Initialize an order."""
        self.symbol = symbol
        self.quantity = quantity
        self.order_type = order_type
        self.order_id = order_id or str(uuid.uuid4())
        self.status = OrderStatus.CREATED
        self.execution_details = {}
        
    async def submit(self):
        """Submit the order to the broker."""
        
    async def cancel(self):
        """Cancel the order."""
        
    async def update_status(self, status: OrderStatus):
        """Update the order status."""
```

### Order Manager

The `OrderManager` class coordinates order execution:

```python
class OrderManager:
    """Manages order creation, submission, and tracking."""
    
    def __init__(self, gateway: IBGateway, event_bus: EventBus):
        """Initialize with Gateway and event bus."""
        self.gateway = gateway
        self.event_bus = event_bus
        self.orders = {}
        
    async def create_order(self, symbol: str, quantity: int, **kwargs) -> Order:
        """Create a new order."""
        
    async def submit_order(self, order_id: str):
        """Submit an order to the broker."""
        
    async def create_and_submit(self, symbol: str, quantity: int, **kwargs) -> Order:
        """Create and immediately submit an order."""
        
    async def cancel_order(self, order_id: str):
        """Cancel an order."""
```

## Risk Management

The system provides comprehensive risk management features:

- **Stop Loss**: Automatic exit when price falls below specified threshold
- **Take Profit**: Automatic exit when price rises above specified threshold
- **Trailing Stop**: Dynamic stop loss that follows price movements
- **Position Sizing**: Calculation of appropriate position size based on risk parameters
- **Exposure Limits**: Prevention of overexposure to specific symbols or sectors

## Integration with Rule Engine

The order and position system integrates with the rule engine to enable automated trading strategies:

```python
# Example rule for automated position creation
from src.rule.condition import EventCondition
from src.rule.action import CreatePositionAction
from src.event.api import PredictionSignalEvent

# Condition: When a BUY prediction arrives with high confidence
condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "BUY",
        "confidence": lambda c: c > 0.8
    }
)

# Action: Create a position with risk management
action = CreatePositionAction(
    symbol=lambda ctx: ctx["event"].symbol,
    quantity=100,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Register rule with rule engine
rule = Rule(
    rule_id="prediction_entry",
    name="Enter Position on High Confidence Buy Signal",
    condition=condition,
    action=action
)
rule_engine.register_rule(rule)
```

## Usage Examples

### Basic Position Management

```python
from src.event.bus import EventBus
from src.position.tracker import PositionTracker

# Initialize event bus and position tracker
event_bus = EventBus()
position_tracker = PositionTracker(event_bus)

# Create a new position
position = await position_tracker.create_position(
    symbol="AAPL",
    quantity=100,
    stop_loss_pct=0.03,
    take_profit_pct=0.08,
    trailing_stop_pct=0.02
)

# Update position with current market price
await position_tracker.update_positions({"AAPL": 150.75})

# Close position
await position_tracker.close_position(position.position_id, reason="manual exit")
```

### Order Creation and Submission

```python
from src.order.manager import OrderManager
from src.order.base import OrderType

# Initialize order manager
order_manager = OrderManager(gateway, event_bus)

# Create and submit a market order
order = await order_manager.create_and_submit(
    symbol="AAPL",
    quantity=100,
    order_type=OrderType.MARKET
)

# Create a limit order
limit_order = await order_manager.create_order(
    symbol="MSFT",
    quantity=50,
    order_type=OrderType.LIMIT,
    limit_price=280.50
)

# Submit the order later
await order_manager.submit_order(limit_order.order_id)
```

## Execution Flow

1. **Signal Reception**: API Monitor receives prediction signal
2. **Event Emission**: Signal converted to PredictionSignalEvent and emitted on event bus
3. **Position Creation**: Position Tracker creates position based on signal
4. **Order Creation**: Order Manager creates necessary orders for position
5. **Order Execution**: Orders submitted to broker via Gateway
6. **Position Monitoring**: Position status updated with market data and fill events
7. **Risk Management**: Stop loss, take profit, and trailing stops monitored and executed
8. **Position Closure**: Position closed when exit criteria met or manually

## Best Practices

When working with the Order and Position Management System:

1. **Always Use Events**: Communicate between components using events, not direct method calls
2. **Error Handling**: Implement comprehensive error handling, especially for broker communication
3. **Risk First**: Always set appropriate risk parameters when creating positions
4. **Order Grouping**: Use order groups for related orders (e.g., brackets, OCO)
5. **Position Tracking**: Keep position and order data in sync with broker state
6. **Event Logging**: Log all significant events for auditing and analysis
7. **Concurrency Management**: Handle potential race conditions in async event processing

## Future Enhancements

Planned enhancements for the system include:

1. Support for additional asset classes (options, futures)
2. Enhanced simulation mode for strategy testing
3. Portfolio-level risk management
4. Integration with additional data sources
5. Performance optimization for high-frequency trading