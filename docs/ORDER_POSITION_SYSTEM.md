# Order and Position Management System

## Overview

The Order and Position Management System is a core component of the Multi-Ticker IB Trading Framework. It provides a comprehensive solution for managing stock trading positions and orders with an event-driven architecture. The system integrates with external data sources, including the Options Flow Monitor API, to enable automated trading strategies based on prediction signals.

**🆕 Recent Enhancement**: Full BUY/SELL side support with automatic order linking, context-based management, and intelligent short position handling.

Key features include:
- **🆕 Explicit BUY/SELL side management** for long and short positions
- **🆕 Automatic order linking** (stop loss, take profit, scale-ins) by symbol  
- **🆕 Smart protective order placement** based on position side
- **🆕 Event-driven context reset** when positions conclude
- Event-driven architecture for responsive trade execution
- Comprehensive position lifecycle management
- Integration with options flow prediction signals
- Support for rule-based trading strategies
- Risk management with stop-loss, take-profit, and trailing stops

## Enhanced Architecture

The system follows an event-driven architecture with these key components:

1. **Event System**: A publish-subscribe pattern for decoupled communication between components
2. **🆕 Linked Order Management**: Automatic linking and management of related orders by symbol
3. **Position Management**: Tracking and risk management for stock positions with side awareness
4. **Order Management**: Creation, tracking, and lifecycle management of orders
5. **API Integration**: Processing prediction signals from external sources

### Component Relationships

```
┌────────────────────┐     ┌───────────────────┐
│                    │     │                   │
│   API Monitor      │────▶│   Event System    │◀───┐
│  (BUY/SELL/SHORT)  │     │      (Bus)        │    │
└────────────────────┘     └───────────┬───────┘    │
                                       │            │
                                       ▼            │
                         ┌─────────────────────────┐ │
                         │                         │ │
                         │ Linked Order Manager    │ │
                         │ (Context + Side Track)  │ │
                         └─────────┬───────────────┘ │
                                   │                 │
                                   ▼                 │
                           ┌───────────────────┐     │
                           │                   │     │
                           │ Position Tracker  │─────┤
                           │  (Side Aware)     │     │
                           └─────────┬─────────┘     │
                                     │               │
                                     ▼               │
                           ┌───────────────────┐     │
                           │                   │     │
                           │  Order Manager    │─────┘
                           │                   │
                           └───────────────────┘
```

## 🆕 Linked Order Management

The new linked order management system provides automatic order relationship management:

### LinkedOrderManager

```python
class LinkedOrderManager:
    """Helper class for managing linked orders in context."""
    
    @staticmethod
    def get_order_group(context: Dict[str, Any], symbol: str, side: str) -> Dict[str, Any]:
        """Get or create order group for symbol with side tracking."""
        
    @staticmethod
    def add_order(context: Dict[str, Any], symbol: str, order_id: str, order_type: str, side: str):
        """Add an order to the appropriate group with side tracking."""
        
    @staticmethod
    async def find_active_position_side(context: Dict[str, Any], symbol: str) -> Optional[str]:
        """Find the side of active position for a symbol."""
```

### Context Structure

Each symbol's context now stores side information and related orders:

```python
context[symbol] = {
    "side": "BUY",              # or "SELL" for short positions
    "main_orders": [],          # Entry order IDs
    "stop_orders": [],          # Stop loss order IDs
    "target_orders": [],        # Take profit order IDs  
    "scale_orders": [],         # Scale-in order IDs
    "status": "active"          # or "closed"
}
```

### LinkedCreateOrderAction

Enhanced order creation with automatic linking and side-aware protective orders:

```python
# Long position with automatic stops/targets
action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",                    # Explicit side
    auto_create_stops=True,
    stop_loss_pct=0.03,           # Stop BELOW entry price
    take_profit_pct=0.08          # Target ABOVE entry price
)

# Short position with correctly positioned stops/targets  
action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100, 
    side="SELL",                  # Short position
    auto_create_stops=True,
    stop_loss_pct=0.03,          # Stop ABOVE entry price
    take_profit_pct=0.08         # Target BELOW entry price
)
```

### 🆕 Position Reversal Logic

The `LinkedCreateOrderAction` now includes intelligent position reversal logic to ensure only one trade per symbol at a time:

**Behavior:**
- **Same Side Signal** → **IGNORE**: If already in a BUY position and new BUY signal arrives → ignore
- **Opposite Side Signal** → **REVERSE**: If in BUY position and SELL signal arrives → exit BUY completely, then enter SELL
- **No Current Position** → **ENTER**: If no active position → proceed with new position normally

**Clean Context Management:**
The system maintains clean state by completely clearing context when positions are closed:

```python
# When position concludes (stop/target hit or manual close):
# OLD: context[symbol]["status"] = "closed"  # Kept old data around
# NEW: del context[symbol]                   # Complete cleanup

# Benefits of complete context clearing:
# 1. No "corrupted" or "stale" state possible
# 2. Fresh start for each new position  
# 3. Clean position reversal with no conflicts
# 4. Simplified validation logic
```

**Implementation:**
```python
# If current position is BUY and new signal is SELL:
# 1. Cancel all pending orders (stops, targets, scale-ins)  
# 2. Close position via market order
# 3. COMPLETELY CLEAR context for symbol (del context[symbol])
# 4. Create new SELL position with stops/targets

# If current position is BUY and new signal is BUY:
# 1. Log "Ignoring BUY signal - already in BUY position"
# 2. Return without creating any orders
```

**Benefits:**
- Prevents position accumulation from duplicate signals
- Enables clean position reversal on opposing signals  
- Maintains risk management through automatic stop/target recreation
- Provides audit trail through detailed logging
- **🆕 Eliminates context corruption** - no stale data possible

### LinkedScaleInAction

Intelligent scale-in with automatic stop/target adjustment:

```python
action = LinkedScaleInAction(
    symbol="AAPL",
    scale_quantity=50,
    trigger_profit_pct=0.02       # Only scale if 2%+ profitable
)
```

**Features:**
- Automatically detects existing position side
- Validates context consistency  
- Updates stop/target orders for new total position size
- Maintains correct quantity signs for both long and short positions

### LinkedOrderManager Design & Modularity

The `LinkedOrderManager` provides a highly modular, context-based approach to order relationship management:

**Core Purpose:**
The LinkedOrderManager acts as a centralized registry that tracks related orders by symbol and side, enabling complex trading strategies with automatic order coordination.

**How It Works:**
1. **Context-Based Storage**: Uses shared context dictionary with symbol as key
2. **Order Type Classification**: Categorizes orders as "main", "stop", "target", or "scale"
3. **Side Awareness**: Tracks BUY/SELL side to ensure consistency
4. **Event-Driven Updates**: Automatically maintains order relationships as trades execute

**Modular Design Benefits:**

- **Easy Order Addition**: Add new order types by simply extending the order type categories
  ```python
  # Current categories: main_orders, stop_orders, target_orders, scale_orders
  # Easy to add: trail_orders, hedge_orders, etc.
  ```

- **Multiple Scale-In Orders**: Add multiple scale-in orders at different prices
  ```python
  # First scale-in at 2% profit
  scale_1 = LinkedScaleInAction(symbol="AAPL", scale_quantity=25, trigger_profit_pct=0.02)
  
  # Second scale-in at 5% profit  
  scale_2 = LinkedScaleInAction(symbol="AAPL", scale_quantity=25, trigger_profit_pct=0.05)
  
  # Both automatically link and adjust existing stops/targets
  ```

- **Flexible Order Combinations**: Mix and match different order actions
  ```python
  # Entry with auto stops/targets
  entry = LinkedCreateOrderAction(..., auto_create_stops=True)
  
  # Multiple scale-ins at different levels
  scale_small = LinkedScaleInAction(..., scale_quantity=25, trigger_profit_pct=0.02)
  scale_large = LinkedScaleInAction(..., scale_quantity=50, trigger_profit_pct=0.05)
  
  # Manual additional stop orders  
  trailing_stop = LinkedCreateOrderAction(..., link_type="stop", order_type=OrderType.TRAIL)
  ```

- **Symbol Isolation**: Each symbol maintains independent order context
  ```python
  # AAPL and MSFT positions managed completely separately
  context["AAPL"] = {"side": "BUY", "main_orders": [...], ...}
  context["MSFT"] = {"side": "SELL", "main_orders": [...], ...}
  ```

**Extensibility Examples:**

- **Custom Order Types**: Add new `link_type` values (e.g., "hedge", "trail", "bracket")
- **Advanced Scaling**: Implement pyramid scaling with multiple price levels
- **Risk Overlays**: Add portfolio-level risk orders that span multiple symbols
- **Time-Based Orders**: Link orders with time-based triggers (e.g., close at EOD)

## 🆕 Trade Tracking System (TradeTracker vs Context)

The system uses two complementary mechanisms for trade management:

### TradeTracker - Duplicate Prevention

The `TradeTracker` is a singleton class that provides persistent tracking of active trades to prevent duplicate positions:

```python
class TradeTracker:
    """
    Singleton class to track active trades across the application.
    
    This provides persistent tracking that survives between rule executions,
    unlike the context which gets copied.
    """
    
    def has_active_trade(self, symbol: str) -> bool:
        """Check if there's an active trade for a symbol."""
        
    def start_trade(self, symbol: str, side: str) -> TradeInfo:
        """Start tracking a new trade."""
        
    def close_trade(self, symbol: str):
        """Mark a trade as closed."""
```

**Key Features:**
- **Persistence**: Survives between rule executions (singleton pattern)
- **Simple State**: Only tracks symbol, side, and active/closed status
- **Duplicate Prevention**: Primary purpose is to prevent multiple positions on same symbol
- **Lightweight**: Minimal data storage for fast lookups

**Usage Example:**
```python
# In LinkedCreateOrderAction
tracker = TradeTracker()
if tracker.has_active_trade(symbol):
    active_trade = tracker.get_active_trade(symbol)
    if active_trade.side == side:
        logger.info(f"Ignoring {side} signal for {symbol} - already have active {side} trade")
        return  # Prevent duplicate
```

### Context - Order Relationship Management

The Context system provides detailed order management and relationships:

```python
context[symbol] = {
    "side": "BUY",              # Position side
    "main_orders": ["id1"],     # Entry order IDs
    "stop_orders": ["id2"],     # Stop loss order IDs
    "target_orders": ["id3"],   # Take profit order IDs
    "doubledown_orders": ["id4"], # Double down order IDs
    "quantity": 100,            # Position size
    "entry_price": 150.50,      # Entry price
    "atr_stop_multiplier": 6.0, # ATR multiplier for stops
    "status": "active"          # Position status
}
```

**Key Features:**
- **Detailed Tracking**: Stores all order IDs and their relationships
- **Order Management**: Enables bulk operations (cancel all stops, update targets)
- **Position Parameters**: Maintains entry prices, quantities, ATR multipliers
- **Transient**: Gets copied during rule execution (not persistent)

### How They Work Together

1. **Trade Entry**:
   - TradeTracker checks for duplicates (fast, persistent check)
   - If no duplicate, Context stores detailed order information
   - Both systems updated when position opens

2. **During Trade**:
   - Context manages order relationships and updates
   - TradeTracker maintains simple active/closed state
   - Context enables complex operations (update stops after scale-in)

3. **Trade Exit**:
   - Context used to cancel all related orders
   - TradeTracker marks trade as closed
   - Context cleared for fresh start on next trade

**Example Flow:**
```python
# 1. New BUY signal arrives
if not tracker.has_active_trade("AAPL"):  # TradeTracker check
    # Create position with orders
    context["AAPL"] = {                    # Context stores details
        "side": "BUY",
        "main_orders": ["123"],
        "stop_orders": ["124"],
        "target_orders": ["125"],
        ...
    }
    tracker.start_trade("AAPL", "BUY")    # TradeTracker marks active

# 2. Stop loss fills
# LinkedOrderConclusionManager uses context to:
# - Find all related orders
# - Cancel remaining orders
# - Clear context
# - Update TradeTracker
tracker.close_trade("AAPL")
del context["AAPL"]  # Clean slate for next trade
```

### Summary of Roles

| Feature | TradeTracker | Context |
|---------|--------------|---------|
| **Purpose** | Prevent duplicates | Manage order relationships |
| **Persistence** | Singleton (persistent) | Transient (copied) |
| **Data Stored** | Symbol, side, status | All order IDs, prices, parameters |
| **Primary Use** | "Can I trade this?" | "How do I manage this trade?" |
| **Scope** | Application-wide | Rule execution scope |

Both systems are essential and complementary:
- **TradeTracker** = Traffic light (red/green for new trades)
- **Context** = Control panel (detailed trade management)

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
- **Order Events**: `OrderCreatedEvent`, `OrderSubmittedEvent`, `OrderFilledEvent`, `FillEvent`
- **API Events**: `PredictionSignalEvent` (supports BUY, SELL, SHORT signals)

### 🆕 Automatic Context Reset

The `LinkedOrderConclusionManager` monitors fill events to automatically reset context:

```python
class LinkedOrderConclusionManager:
    """Manages automatic context reset when positions are concluded via stops/targets."""
    
    async def on_order_fill(self, event):
        """Handle order fill events to detect position conclusions."""
        # Detects when stop/target orders fill
        # Automatically marks symbol status as "closed"
        # Enables fresh context on next trade
```

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
        self.quantity = 0                    # Positive for long, negative for short
        self.unrealized_pnl = 0.0
        # Risk management parameters
        self.stop_loss = None
        self.take_profit = None
        self.trailing_stop = None
        
    @property
    def is_long(self) -> bool:
        """Check if position is long (positive quantity)."""
        return self.quantity > 0
        
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
        
    async def get_positions_for_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol."""
        
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
        quantity: int,              # Positive for buy, negative for sell
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
    
    def __init__(self, event_bus: EventBus, tws_connection: TWSConnection):
        """Initialize with event bus and TWS connection."""
        self.event_bus = event_bus
        self.tws_connection = tws_connection
        self.orders = {}
        
    async def create_order(self, symbol: str, quantity: int, **kwargs) -> Order:
        """Create a new order."""
        
    async def submit_order(self, order_id: str):
        """Submit an order to the broker."""
        
    async def create_and_submit_order(self, symbol: str, quantity: int, **kwargs) -> Order:
        """Create and immediately submit an order."""
        
    async def cancel_order(self, order_id: str, reason: str = "manual"):
        """Cancel an order."""
```

## Risk Management

The system provides comprehensive risk management features:

- **🆕 Side-Aware Stop Loss**: Positioned correctly for both long and short positions
- **🆕 Side-Aware Take Profit**: Positioned correctly for both long and short positions  
- **Trailing Stop**: Dynamic stop loss that follows price movements
- **Position Sizing**: Calculation of appropriate position size based on risk parameters
- **Exposure Limits**: Prevention of overexposure to specific symbols or sectors
- **🆕 Order Mixing Prevention**: Context side tracking prevents mixing long/short orders

## Integration with Rule Engine

The order and position system integrates with the rule engine to enable automated trading strategies:

```python
# Example: Long position entry rule
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import LinkedCreateOrderAction
from src.event.api import PredictionSignalEvent

# Condition: When a BUY prediction arrives with high confidence
buy_condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "BUY",
        "confidence": lambda c: c > 0.8
    }
)

# Action: Create long position with automatic protective orders
buy_action = LinkedCreateOrderAction(
    symbol=lambda ctx: ctx["event"].symbol,
    quantity=100,
    side="BUY",                    # Explicit long side
    auto_create_stops=True,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Example: Short position entry rule  
short_condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "SHORT",
        "confidence": lambda c: c > 0.8
    }
)

# Action: Create short position with correctly positioned protective orders
short_action = LinkedCreateOrderAction(
    symbol=lambda ctx: ctx["event"].symbol,
    quantity=100,
    side="SELL",                   # Explicit short side
    auto_create_stops=True,        # Stop ABOVE entry, target BELOW entry
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Register rules with rule engine
buy_rule = Rule(
    rule_id="prediction_buy_entry",
    name="Enter Long Position on Buy Signal",
    condition=buy_condition,
    action=buy_action
)

short_rule = Rule(
    rule_id="prediction_short_entry", 
    name="Enter Short Position on Short Signal",
    condition=short_condition,
    action=short_action
)

rule_engine.register_rule(buy_rule)
rule_engine.register_rule(short_rule)
```

## Usage Examples

### 🆕 Enhanced Position Management with Sides

```python
from src.event.bus import EventBus
from src.position.tracker import PositionTracker
from src.rule.linked_order_actions import LinkedCreateOrderAction

# Initialize components
event_bus = EventBus()
position_tracker = PositionTracker(event_bus)

# Create long position with automatic linking
buy_action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    auto_create_stops=True,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Create short position with automatic linking
short_action = LinkedCreateOrderAction(
    symbol="TSLA", 
    quantity=50,
    side="SELL",
    auto_create_stops=True,
    stop_loss_pct=0.04,
    take_profit_pct=0.10
)

# Scale into existing position (automatically detects side)
scale_action = LinkedScaleInAction(
    symbol="AAPL",
    scale_quantity=50,
    trigger_profit_pct=0.02
)

# Close all orders and position for symbol
close_action = LinkedCloseAllAction(
    symbol="AAPL",
    reason="risk management exit"
)
```

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
order_manager = OrderManager(event_bus, tws_connection)

# Create and submit a market buy order (long)
buy_order = await order_manager.create_and_submit_order(
    symbol="AAPL",
    quantity=100,                 # Positive for buy
    order_type=OrderType.MARKET
)

# Create and submit a market sell order (short)
sell_order = await order_manager.create_and_submit_order(
    symbol="MSFT",
    quantity=-50,                 # Negative for sell/short
    order_type=OrderType.MARKET
)

# Create a limit order
limit_order = await order_manager.create_order(
    symbol="NVDA",
    quantity=25,
    order_type=OrderType.LIMIT,
    limit_price=280.50
)

# Submit the order later
await order_manager.submit_order(limit_order.order_id)
```

## Execution Flow

1. **Signal Reception**: API Monitor receives prediction signal (BUY/SELL/SHORT)
2. **Event Emission**: Signal converted to PredictionSignalEvent and emitted on event bus
3. **Rule Evaluation**: Rule engine evaluates conditions and triggers appropriate actions
4. **🆕 Linked Order Creation**: LinkedCreateOrderAction creates position with explicit side
5. **🆕 Automatic Protective Orders**: Stop and target orders created with correct positioning
6. **Order Execution**: Orders submitted to broker via TWS connection
7. **Position Monitoring**: Position status updated with market data and fill events
8. **🆕 Context Management**: Related orders tracked and managed by symbol and side
9. **Risk Management**: Stop loss, take profit monitored and executed
10. **🆕 Automatic Context Reset**: Context cleaned when positions conclude via stops/targets

## Best Practices

When working with the enhanced Order and Position Management System:

1. **Always Specify Side**: Use explicit "BUY" or "SELL" side parameters for clarity
2. **Use Linked Actions**: Prefer LinkedOrderActions for automatic order management  
3. **Validate Context Consistency**: System prevents mixing long/short orders for same symbol
4. **Monitor Context State**: Use context status to understand position lifecycle
5. **Always Use Events**: Communicate between components using events, not direct method calls
6. **Error Handling**: Implement comprehensive error handling, especially for broker communication
7. **Risk First**: Always set appropriate risk parameters when creating positions
8. **Position Tracking**: Keep position and order data in sync with broker state
9. **Event Logging**: Log all significant events for auditing and analysis
10. **Concurrency Management**: Handle potential race conditions in async event processing

## Future Enhancements

Planned enhancements for the system include:

1. Support for additional asset classes (options, futures)
2. Enhanced simulation mode for strategy testing
3. Portfolio-level risk management
4. Integration with additional data sources
5. Performance optimization for high-frequency trading
6. **🆕 Advanced order types**: OCO (One-Cancels-Other), bracket orders with linked management
7. **🆕 Multi-leg strategies**: Complex strategies spanning multiple positions with automatic linking