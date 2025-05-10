# Event-Driven Order and Position Management System Documentation

## Overview

This documentation covers the implementation of the event-driven order and position management system for the IBKR Trading Framework. The system provides a robust foundation for building algorithmic trading strategies focused on stock trading, with key features including:

- Event-driven architecture for responsive trade execution
- Comprehensive position lifecycle management
- Integration with options flow prediction signals
- Support for rule-based trading strategies

## Architecture

The system is built around these core components:

1. **Event System**: The central nervous system that enables communication between components
2. **Position Management**: Tracks and manages stock positions
3. **API Integration**: Processes prediction signals from the options flow monitor API

### Directory Structure

```
src/
  ├── event/               # Event system
  │   ├── base.py          # Base event classes
  │   ├── bus.py           # Event bus implementation
  │   ├── market.py        # Market events (price, volume)
  │   ├── order.py         # Order events
  │   ├── position.py      # Position events
  │   └── api.py           # API events (prediction signals)
  │
  ├── position/            # Position management
  │   ├── base.py          # Base position class
  │   ├── stock.py         # Stock position implementation
  │   └── tracker.py       # Position tracking and management
  │
  └── api/                 # API integration
      └── monitor.py       # Options flow API monitoring
```

## Event System

### Overview

The event system enables loosely coupled components to communicate through a publish-subscribe pattern. Events represent significant occurrences in the system (price changes, order updates, position changes, API signals), and components can subscribe to receive notifications when specific event types occur.

### Key Components

#### BaseEvent (`src/event/base.py`)

The foundation class for all events in the system:

```python
@dataclass
class BaseEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
```

**Notable Methods**:
- `to_dict()`: Converts the event to a dictionary
- `event_type`: Property that returns the class name

#### EventBus (`src/event/bus.py`)

The central message dispatcher that connects event publishers and subscribers:

```python
class EventBus:
    async def subscribe(self, event_type: Type[BaseEvent], handler: Callable) -> None:
        # Register a handler for an event type
        
    async def unsubscribe(self, event_type: Type[BaseEvent], handler: Callable) -> bool:
        # Remove a handler for an event type
        
    async def emit(self, event: BaseEvent) -> None:
        # Publish an event to all subscribers
```

**Features**:
- Supports both synchronous and asynchronous event handlers
- Implements inheritance-based subscription (handlers receive events of the subscribed type and its subclasses)
- Thread-safe using asyncio locks
- Provides enable/disable control for event distribution

### Event Types

The system defines a rich hierarchy of event types:

#### Market Events (`src/event/market.py`)

Events related to market data:
- `MarketEvent`: Base class for market events
- `PriceEvent`: Price updates (includes price, change, bid/ask)
- `VolumeEvent`: Volume changes
- `IndicatorEvent`: Technical indicator signals

#### Position Events (`src/event/position.py`)

Events related to position lifecycle:
- `PositionEvent`: Base class for position events
- `PositionOpenEvent`: Position opened
- `PositionUpdateEvent`: Position updated (price, stops, quantity)
- `PositionCloseEvent`: Position closed

#### Order Events (`src/event/order.py`)

Events related to order management:
- `OrderEvent`: Base class for order events
- `NewOrderEvent`: Order created
- `OrderStatusEvent`: Order status changes
- `FillEvent`: Order (partially) filled
- `CancelEvent`: Order cancelled
- `RejectEvent`: Order rejected

#### API Events (`src/event/api.py`)

Events related to API signals:
- `OptionsFlowEvent`: Base class for options flow events
- `PredictionSignalEvent`: ML-based trading signals
- `FlowThresholdEvent`: Placeholder for future usage

## Position Management

### Overview

The position management system tracks and manages stock positions throughout their lifecycle, from planning to closing. It supports position sizing, risk management, and P&L tracking.

### Key Components

#### Position (`src/position/base.py`)

The base position class with common functionality:

```python
class Position:
    def __init__(self, symbol: str, position_id: Optional[str] = None):
        # Position identifiers and state
        
    @property
    def status(self) -> PositionStatus:
        return self._status
        
    async def open(self, quantity: float, entry_price: float, order_id: Optional[str] = None) -> None:
        # Open the position
        
    async def close(self, exit_price: float, reason: Optional[str] = None, order_id: Optional[str] = None) -> None:
        # Close the position
        
    async def update_price(self, price: float) -> None:
        # Update position with current price
        
    async def adjust(self, quantity: Optional[float] = None, 
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> None:
        # Adjust position parameters
```

**Features**:
- Position state machine (planned, opening, open, adjusting, closing, closed)
- Thread-safe operations with asyncio locks
- Unrealized and realized P&L tracking
- Stop loss and take profit management
- Comprehensive update history

#### StockPosition (`src/position/stock.py`)

Extended position class with stock-specific features:

```python
class StockPosition(Position):
    async def set_stock_info(self, avg_volume=None, beta=None, ...) -> None:
        # Set stock-specific information
        
    async def calculate_optimal_stop_loss(self, atr_multiple=2.0, atr_value=None) -> float:
        # Calculate stop loss based on ATR
        
    async def calculate_optimal_take_profit(self, risk_reward_ratio=2.0) -> float:
        # Calculate take profit based on risk-reward ratio
        
    async def calculate_trailing_stop(self, price: float, trail_percentage=0.03) -> float:
        # Calculate trailing stop price
```

**Features**:
- Stock metadata tracking (beta, sector, market cap)
- ATR-based stop loss calculation
- Risk/reward-based take profit calculation
- Trailing stop management
- Advanced drawdown tracking

#### PositionTracker (`src/position/tracker.py`)

Manages multiple positions and handles lifecycle events:

```python
class PositionTracker:
    def __init__(self, event_bus: EventBus):
        # Initialize with event bus
        
    async def create_stock_position(self, symbol: str, quantity=0, ...) -> StockPosition:
        # Create and track a new stock position
        
    async def close_position(self, position_id: str, exit_price: float, ...) -> None:
        # Close a position
        
    async def update_position_price(self, position_id: str, price: float) -> None:
        # Update a position with new price
        
    async def get_position_summary(self) -> Dict[str, Any]:
        # Get summary of active positions
```

**Features**:
- Position creation and tracking
- Position lookup by ID or symbol
- Automatic event generation
- Closed position history
- Position summary calculations

## API Integration

### Overview

The API integration connects the system to the options flow monitor API, allowing it to process prediction signals and generate corresponding events.

### Key Components

#### OptionsFlowMonitor (`src/api/monitor.py`)

Monitors the options flow API and generates events:

```python
class OptionsFlowMonitor:
    def __init__(self, event_bus: EventBus, api_client: Any):
        # Initialize with event bus and API client
        
    def configure(self, tickers: List[str], thresholds: Optional[Dict[str, float]] = None) -> None:
        # Configure monitored tickers and thresholds
        
    async def start_monitoring(self) -> None:
        # Start the monitoring process
        
    async def stop_monitoring(self) -> None:
        # Stop the monitoring process
        
    async def _poll_predictions(self) -> None:
        # Poll for new predictions
        
    async def _process_prediction(self, ticker: str, prediction: Dict[str, Any]) -> None:
        # Process prediction data and emit events
```

**Features**:
- Periodic polling for new predictions
- Configurable confidence thresholds
- Duplicate prediction handling
- Error resilience
- Placeholder functions for future data sources

## Usage Examples

### Basic Event System Usage

```python
# Create event bus
event_bus = EventBus()

# Subscribe to events
async def price_handler(event):
    print(f"Price update: {event.symbol} @ {event.price}")
    
await event_bus.subscribe(PriceEvent, price_handler)

# Emit an event
await event_bus.emit(PriceEvent(symbol="AAPL", price=150.0))
```

### Position Management

```python
# Create position tracker
position_tracker = PositionTracker(event_bus)

# Create a position
position = await position_tracker.create_stock_position(
    symbol="AAPL",
    quantity=100,
    entry_price=150.0,
    stop_loss=145.0,
    take_profit=165.0
)

# Update with new price
await position_tracker.update_position_price(position.position_id, 155.0)

# Close position
await position_tracker.close_position(position.position_id, 160.0, "Take profit")
```

### API Signal Handling

```python
# Create options flow monitor
monitor = OptionsFlowMonitor(event_bus, api_client)

# Configure and start
monitor.configure(tickers=["AAPL", "MSFT", "GOOGL"])
await monitor.start_monitoring()

# Handle prediction signals
async def prediction_handler(event):
    if event.signal == "BUY" and event.confidence > 0.8:
        # Create position based on prediction
        await position_tracker.create_stock_position(
            symbol=event.symbol,
            quantity=100,
            entry_price=event.price,
            stop_loss=event.price * 0.95,
            take_profit=event.price * 1.15
        )

await event_bus.subscribe(PredictionSignalEvent, prediction_handler)
```

## Detailed API Reference

### Event Classes

#### BaseEvent

| Property/Method | Description |
|-----------------|-------------|
| `event_id` | Unique identifier for the event |
| `timestamp` | When the event occurred |
| `metadata` | Additional event data |
| `source` | Source of the event (market, order, position, api) |
| `event_type` | Type of the event (class name) |
| `to_dict()` | Convert the event to a dictionary |

#### EventBus

| Method | Description |
|--------|-------------|
| `subscribe(event_type, handler)` | Register handler for event type |
| `unsubscribe(event_type, handler)` | Remove handler for event type |
| `emit(event)` | Publish event to all subscribers |
| `enable()` | Enable event distribution |
| `disable()` | Disable event distribution |
| `get_subscriber_count()` | Get subscriber counts by event type |

### Position Classes

#### Position

| Property/Method | Description |
|-----------------|-------------|
| `symbol` | The ticker symbol |
| `position_id` | Unique identifier |
| `status` | Current status (enum) |
| `quantity` | Position size |
| `entry_price` | Average entry price |
| `current_price` | Current market price |
| `unrealized_pnl` | Unrealized profit/loss |
| `realized_pnl` | Realized profit/loss |
| `is_long` | True if position is long |
| `is_short` | True if position is short |
| `is_active` | True if position is active |
| `stop_loss` | Stop loss price |
| `take_profit` | Take profit price |
| `open(quantity, entry_price)` | Open the position |
| `close(exit_price, reason)` | Close the position |
| `update_price(price)` | Update with current price |
| `update_stop_loss(price)` | Update stop loss |
| `update_take_profit(price)` | Update take profit |
| `adjust(quantity, stop_loss, take_profit)` | Adjust position |

#### StockPosition

| Method | Description |
|--------|-------------|
| `set_stock_info(...)` | Set stock metadata |
| `calculate_optimal_stop_loss(...)` | Calculate ATR-based stop |
| `calculate_optimal_take_profit(...)` | Calculate take profit |
| `calculate_trailing_stop(...)` | Calculate trailing stop |

#### PositionTracker

| Method | Description |
|--------|-------------|
| `create_stock_position(...)` | Create new position |
| `get_position(position_id)` | Get position by ID |
| `get_positions_for_symbol(symbol)` | Get all positions for symbol |
| `get_all_positions()` | Get all active positions |
| `get_closed_positions()` | Get position history |
| `update_position_price(...)` | Update price for position |
| `update_all_positions_price(...)` | Update all positions for symbol |
| `close_position(...)` | Close a position |
| `adjust_position(...)` | Adjust position parameters |
| `update_stop_loss(...)` | Update stop loss |
| `update_take_profit(...)` | Update take profit |
| `has_open_positions(...)` | Check for open positions |
| `get_position_summary()` | Get summary statistics |

### API Monitor

#### OptionsFlowMonitor

| Method | Description |
|--------|-------------|
| `configure(tickers, thresholds)` | Configure monitoring |
| `start_monitoring()` | Start monitoring process |
| `stop_monitoring()` | Stop monitoring process |

## Best Practices

### Event Handling

1. **Keep handlers lightweight**: Avoid long-running operations in event handlers
2. **Handle exceptions**: Always catch exceptions in event handlers
3. **Use inheritance**: Subscribe to the most specific event class needed
4. **Emit responsibly**: Only emit events for significant state changes

### Position Management

1. **Always use async methods**: All position operations are async
2. **Verify position state**: Check position status before operations
3. **Update prices regularly**: Keep positions updated with current prices
4. **Log position changes**: Position events provide an audit trail
5. **Avoid direct attribute access**: Use provided methods for state changes

### API Integration

1. **Configure thresholds**: Set appropriate confidence thresholds
2. **Track processed signals**: Avoid duplicate processing
3. **Handle API errors**: Implement proper error handling
4. **Throttle requests**: Respect API rate limits

## Future Enhancements

1. **Order Management**: Implementation of order state machine and IB Gateway integration
2. **Rule Engine**: Rule-based decision system for automated trading
3. **Backtesting**: Support for strategy backtesting
4. **Divergence and Trade Data**: Integration with additional API data sources

## Troubleshooting

### Common Issues

1. **Event handlers not called**: Ensure correct event type subscription
2. **Position state transitions**: Check position status before operations
3. **Concurrent operations**: All operations are thread-safe but may interact

### Debugging

1. **Enable DEBUG logging**: Set logging level to DEBUG for detailed output
2. **Event tracing**: Subscribe to all events for debugging purposes
3. **Position snapshots**: Use `position.to_dict()` for state snapshots