# Order and Position Management System

## Overview

The Order and Position Management System is a core component of the Multi-Ticker IB Trading Framework. It provides a comprehensive solution for managing stock trading positions and orders with an event-driven architecture. The system integrates with external data sources, including the Options Flow Monitor API, to enable automated trading strategies based on prediction signals.

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
│    Event System    │◄────┤  API Integration  │
│                    │     │                   │
└─────────┬──────────┘     └───────────────────┘
          │
          │ Events
          ▼
┌─────────┴──────────┐     ┌───────────────────┐
│                    │     │                   │
│ Position Management│◄────┤ Order Management  │
│                    │     │                   │
└────────────────────┘     └───────────────────┘
```

## Event System

The event system is the foundation for communication between components. It consists of:

### Base Event (`/src/event/base.py`)

```python
@dataclass
class BaseEvent:
    """Base class for all events in the system."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
```

### Event Types

- **MarketEvents**: Price updates, volume changes, etc.
- **OrderEvents**: Order creation, fills, cancellations, etc.
- **PositionEvents**: Position creation, updates, closures, etc.
- **APIEvents**: Prediction signals, external data updates, etc.

### Event Bus (`/src/event/bus.py`)

The `EventBus` class provides:
- Event subscription by event type
- Asynchronous event emission
- Handler management

Example usage:

```python
# Create an event bus
event_bus = EventBus()

# Subscribe to events
await event_bus.subscribe(OrderFillEvent, handle_order_fill)

# Emit an event
await event_bus.emit(OrderFillEvent(order_id="ORD123", fill_quantity=100, fill_price=150.25))
```

## Position Management

The position management component tracks and manages trading positions.

### Position Classes

#### Base Position (`/src/position/base.py`)

Defines the base `Position` class with:
- Position lifecycle (NEW → ACTIVE → CLOSING → CLOSED)
- Core properties (symbol, quantity, average price)
- Risk management (stop loss, take profit)
- P&L tracking

```python
class Position:
    """Base class representing a trading position."""
    
    def __init__(self, position_id: str, symbol: str, quantity: float = 0,
                 avg_price: float = 0, status: PositionStatus = PositionStatus.NEW):
        self.position_id = position_id
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.status = status
        # Additional properties...
```

#### Stock Position (`/src/position/stock.py`)

Extends the base Position with stock-specific functionality:
- Stock-specific risk calculations
- Trailing stop implementation
- Market value and P&L calculations

```python
class StockPosition(Position):
    """A position in a stock/equity."""
    
    async def update_market_price(self, price: float) -> None:
        """Update the current market price and recalculate values."""
        # Implementation...
```

#### Position Tracker (`/src/position/tracker.py`)

The `PositionTracker` manages all positions:
- Creates and tracks positions
- Processes position-related events
- Aggregates position statistics

```python
class PositionTracker:
    """Tracks all positions in the system."""
    
    async def create_stock_position(self, symbol: str, **kwargs) -> StockPosition:
        """Create a new stock position."""
        # Implementation...
```

### Position Lifecycle

1. **Creation**: Position is created with NEW status
2. **Activation**: Position becomes ACTIVE when filled
3. **Modification**: Position quantity/price updated on partial fills
4. **Closing**: Position marked as CLOSING when exit orders are placed
5. **Closed**: Position is CLOSED when fully exited

## Order Management

The order management component handles the creation, tracking, and lifecycle of orders.

### Order Classes

#### Base Order (`/src/order/base.py`)

The `Order` class represents a single order:
- Order properties (symbol, quantity, price, etc.)
- Order lifecycle (NEW → PENDING → ACTIVE → FILLED/CANCELLED/REJECTED)
- Fill processing

```python
class Order:
    """Base class representing a trading order."""
    
    def __init__(self, order_id: str, symbol: str, quantity: float,
                 order_type: OrderType, side: OrderSide, limit_price: Optional[float] = None):
        self.order_id = order_id
        self.symbol = symbol
        self.quantity = quantity
        self.order_type = order_type
        self.side = side
        self.limit_price = limit_price
        # Additional properties...
```

#### Order Groups (`/src/order/group.py`)

- **OrderGroup**: Base class for related orders
- **BracketOrder**: Entry + Stop Loss + Take Profit
- **OCOGroup**: One-Cancels-Other order group

```python
class BracketOrder(OrderGroup):
    """Bracket order group (entry + stop loss + take profit)."""
    
    def __init__(self, entry_order: Order, stop_loss_order: Order, 
                 take_profit_order: Optional[Order] = None):
        super().__init__()
        self.entry_order = entry_order
        self.stop_loss_order = stop_loss_order
        self.take_profit_order = take_profit_order
        self.add_orders([entry_order, stop_loss_order])
        if take_profit_order:
            self.add_orders([take_profit_order])
```

#### Order Manager (`/src/order/manager.py`)

The `OrderManager` handles order submission and tracking:
- Creates and tracks orders
- Handles order events
- Interfaces with the broker (IBKR)

```python
class OrderManager:
    """Manages orders and their lifecycle."""
    
    async def create_order(self, symbol: str, quantity: float, order_type: OrderType, 
                           side: OrderSide, **kwargs) -> Order:
        """Create a new order."""
        # Implementation...
```

### Order Lifecycle

1. **Creation**: Order is created with NEW status
2. **Submission**: Order submitted to broker, becomes PENDING
3. **Activation**: Order accepted by broker, becomes ACTIVE
4. **Execution**: Order fills (partial or complete)
5. **Completion**: Order becomes FILLED, CANCELLED, or REJECTED

## API Integration

### Options Flow Monitor (`/src/api/monitor.py`)

The `OptionsFlowMonitor` processes prediction signals:
- Polls the Options Flow Monitor API
- Processes prediction signals
- Generates events based on signals

```python
class OptionsFlowMonitor:
    """Monitors the Options Flow API for signals."""
    
    async def start(self):
        """Start monitoring for signals."""
        self._polling_task = asyncio.create_task(self._poll_predictions())
        
    async def _poll_predictions(self):
        """Poll for new predictions from the API."""
        # Implementation...
```

## Usage Examples

### Position Management Example

```python
# Create a position tracker
position_tracker = PositionTracker(event_bus)

# Create a stock position
position = await position_tracker.create_stock_position(
    symbol="AAPL",
    quantity=100,
    avg_price=150.25,
    stop_loss=145.00,
    take_profit=160.00
)

# Update market price (triggers unrealized P&L calculation)
await position.update_market_price(152.50)

# Activate trailing stop
await position.set_trailing_stop(percent=1.5)
```

### Order Management Example

```python
# Create an order manager
order_manager = OrderManager(event_bus)

# Create a market order
market_order = await order_manager.create_order(
    symbol="AAPL",
    quantity=100,
    order_type=OrderType.MARKET,
    side=OrderSide.BUY
)

# Create a bracket order
bracket = await order_manager.create_bracket_order(
    symbol="MSFT",
    quantity=50,
    entry_price=250.00,
    stop_loss_price=245.00,
    take_profit_price=265.00,
    side=OrderSide.BUY
)
```

## Integration with Event System

Components communicate through events:

1. Market price update → Position unrealized P&L recalculated
2. Order fill → Position quantity/price updated
3. API prediction signal → New position created
4. Position stop loss triggered → Cancel take profit order

Example event flow:

```
Market data update
  ↓
MarketPriceEvent emitted
  ↓
Position.update_market_price() called
  ↓
Position stop loss triggered
  ↓
PositionStopTriggeredEvent emitted
  ↓
OrderManager cancels related orders
```

## Future Enhancements

1. **Rule Engine**: A configurable engine for strategy rules
2. **Risk Management**: Advanced position sizing and portfolio-level risk controls
3. **Reporting**: Performance metrics and position/order reporting
4. **UI Integration**: Real-time dashboard for positions and orders
5. **Strategy Backtesting**: Historical simulation of position management

## Testing

The system includes comprehensive unit and integration tests:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test interactions between components
- **Demo Scripts**: Demonstrate functionality with simulated data

Example test command:

```bash
# Run position management tests
pytest tests/test_position_management.py

# Run order management tests
pytest tests/test_order_management.py
```

## Best Practices

1. **Event-First Design**: Design components around events rather than direct calls
2. **Proper State Management**: Ensure position and order states follow defined lifecycles
3. **Error Handling**: Implement comprehensive error handling and recovery
4. **Logging**: Use structured logging for debugging and auditing
5. **Idempotency**: Ensure event handlers are idempotent to prevent duplicate processing