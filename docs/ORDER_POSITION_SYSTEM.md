# Order and Position Management System

This document describes the order and position management system for the IBKR trading application.

**🆕 Recent Enhancement**: Full BUY/SELL side support with automatic order linking, position-based management, and intelligent short position handling.

## Key Features

- **Unified order management** through OrderManager
- **Position tracking** with risk management via PositionTracker
- **🆕 Event-driven position updates** when orders fill
- **Automatic order linking** for related orders (stops, targets, scale-ins)
- **🆕 Side-aware protective orders** (stops above/below based on position side)
- **🆕 Position reversal logic** (exit current position before entering opposite side)

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Rule Engine    │────▶│  Order Manager   │────▶│ TWS Connection  │
└────────┬────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         └─────────────▶│ Position Tracker │
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │   Event Bus      │
                        └──────────────────┘
```

## Core Components

### LinkedCreateOrderAction

The primary action for creating orders with automatic position management:

```python
action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",                    # Explicit side (BUY or SELL)
    order_type=OrderType.MARKET,
    auto_create_stops=True,        # Auto-create protective orders
    stop_loss_pct=0.03,           # 3% stop loss
    take_profit_pct=0.08,         # 8% take profit
    atr_stop_multiplier=6.5,       # Alternative: ATR-based stops
    atr_target_multiplier=12.0    # Alternative: ATR-based targets
)
```

**Key Behaviors:**
- Creates or updates position in PositionTracker
- Stores all order IDs in the position object
- Automatically creates protective orders if requested
- Handles position reversal (closes opposite positions first)

### Position Management

The `PositionTracker` is the single source of truth for all position information:

```python
# Position object contains all trading state
position = Position(
    symbol="AAPL",
    side="BUY",
    quantity=100,
    entry_price=150.00,
    main_order_ids=["ORDER_123"],
    stop_order_ids=["STOP_456"],
    target_order_ids=["TARGET_789"],
    scale_order_ids=[],
    doubledown_order_ids=[],
    atr_stop_multiplier=6.5,       # Stored for position management
    atr_target_multiplier=3.0,     # Stored for position management
    status=PositionStatus.OPEN
)
```

**Position Lifecycle:**
1. **Creation**: When first order is placed
2. **Updates**: As orders fill, scale-ins occur, or prices change
3. **Closure**: When stop/target hits or manual close
4. **Cleanup**: Position marked as CLOSED, ready for new trades

### Side-Aware Order Placement

The system automatically adjusts order placement based on position side:

**Long Positions (BUY side):**
- Main order: Positive quantity (e.g., +100)
- Stop loss: Below entry price, negative quantity to close
- Take profit: Above entry price, negative quantity to close

**Short Positions (SELL side):**
- Main order: Negative quantity (e.g., -100)
- Stop loss: Above entry price, positive quantity to close
- Take profit: Below entry price, positive quantity to close

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

**Clean Position Management:**
The system maintains clean state by properly updating position status when trades conclude:

```python
# When position concludes (stop/target hit or manual close):
# Position status is updated to CLOSED
# All related orders are cancelled
# New trades can start fresh with no conflicts
```

**Implementation:**
```python
# If current position is BUY and new signal is SELL:
# 1. Cancel all pending orders (stops, targets, scale-ins)  
# 2. Close position via market order
# 3. Update position status to CLOSED
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
- **🆕 Single source of truth** - all state in PositionTracker

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
- Automatically detects existing position from PositionTracker
- Validates position consistency  
- Updates stop/target orders for new total position size
- Maintains correct quantity signs for both long and short positions

### Position-Based Order Management

The system uses the `PositionTracker` as the central registry for all order relationships:

**Core Purpose:**
The PositionTracker maintains complete trading state, tracking all related orders by position.

**How It Works:**
1. **Position-Based Storage**: Each position object contains all order IDs
2. **Order Type Classification**: Order IDs organized by type (main, stop, target, scale)
3. **Side Awareness**: Position tracks BUY/SELL side to ensure consistency
4. **Event-Driven Updates**: Automatically updates position state as trades execute

**Design Benefits:**

- **Easy Order Addition**: Add new order types by extending position fields
  ```python
  # Current fields: main_order_ids, stop_order_ids, target_order_ids, scale_order_ids
  # Easy to add: trail_order_ids, hedge_order_ids, etc.
  ```

- **Multiple Scale-In Orders**: Add multiple scale-in orders at different prices
  ```python
  # First scale-in at 2% profit
  scale_1 = LinkedScaleInAction(symbol="AAPL", scale_quantity=25, trigger_profit_pct=0.02)
  
  # Second scale-in at 5% profit  
  scale_2 = LinkedScaleInAction(symbol="AAPL", scale_quantity=25, trigger_profit_pct=0.05)
  
  # Both automatically link to position and adjust existing stops/targets
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

- **Symbol Isolation**: Each symbol maintains independent positions
  ```python
  # AAPL and MSFT positions managed completely separately
  # Each with their own order lists and state
  ```

**Extensibility Examples:**

- **Custom Order Types**: Add new order ID lists (e.g., hedge_order_ids, trail_order_ids)
- **Advanced Scaling**: Implement pyramid scaling with multiple price levels
- **Risk Overlays**: Add portfolio-level risk orders that span multiple symbols
- **Time-Based Orders**: Link orders with time-based triggers (e.g., close at EOD)

## 🆕 Position Tracking System

The system uses `PositionTracker` as the single source of truth for all trading state:

### PositionTracker - Complete Trade Management

The `PositionTracker` provides persistent tracking and complete trade state management:

```python
class PositionTracker:
    """
    Manages all positions and their complete state.
    
    This is the single source of truth for position information,
    including all related order IDs and trading parameters.
    """
    
    async def create_position(self, symbol: str, side: str, **kwargs) -> Position:
        """Create a new position with initial parameters."""
        
    async def get_positions_for_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol."""
        
    async def update_position(self, position_id: str, **updates):
        """Update position with new information."""
        
    async def close_position(self, position_id: str, reason: str):
        """Mark a position as closed."""
```

**Key Features:**
- **Complete State**: Stores all order IDs, prices, quantities, and parameters
- **Persistence**: Maintains state across rule executions
- **Order Management**: Enables bulk operations (cancel all stops, update targets)
- **Position Parameters**: Maintains entry prices, quantities, ATR multipliers
- **Clean Lifecycle**: Clear status tracking (OPEN → CLOSED)

### Position Object Structure

The Position object contains all trading information:

```python
@dataclass
class Position:
    # Identity
    symbol: str
    position_id: str
    side: str  # "BUY" or "SELL"
    
    # Quantities and Prices
    quantity: int
    entry_price: float
    current_price: float
    
    # Order ID Lists
    main_order_ids: List[str]
    stop_order_ids: List[str]
    target_order_ids: List[str]
    scale_order_ids: List[str]
    doubledown_order_ids: List[str]
    
    # Risk Parameters
    atr_stop_multiplier: Optional[float]
    atr_target_multiplier: Optional[float]
    
    # Status
    status: PositionStatus  # OPEN, CLOSED, etc.
    created_at: datetime
    updated_at: datetime
```

### How It Works

1. **Trade Entry**:
   - LinkedCreateOrderAction creates/updates position in PositionTracker
   - All order IDs stored in appropriate lists
   - Risk parameters (ATR multipliers) saved for later use

2. **During Trade**:
   - Position object manages all order relationships
   - Enables complex operations (update stops after scale-in)
   - Maintains complete trading state

3. **Trade Exit**:
   - Position used to find and cancel all related orders
   - Status updated to CLOSED
   - Clean slate for next trade on same symbol

**Example Flow:**
```python
# 1. New BUY signal arrives
positions = await position_tracker.get_positions_for_symbol("AAPL")
if not positions or all(p.status == PositionStatus.CLOSED for p in positions):
    # Create new position
    position = await position_tracker.create_position(
        symbol="AAPL",
        side="BUY",
        quantity=100,
        entry_price=150.00
    )
    # Add order IDs as orders are created
    position.main_order_ids.append("123")
    position.stop_order_ids.append("124")
    position.target_order_ids.append("125")

# 2. Stop loss fills
# UnifiedFillManager uses position to:
# - Track all order fills (main, double down, protective)
# - Update protective orders on any fill to match position size
# - Close position only when protective orders FULLY fill
await position_tracker.close_position(position.position_id, "Stop loss hit")
```

### Summary

The PositionTracker serves as the complete trade management system:
- **Single Source of Truth**: All trading state in one place
- **Complete Information**: Order IDs, prices, parameters, status
- **Clean Lifecycle**: Clear progression from OPEN to CLOSED
- **Enables Complex Operations**: Scale-ins, order updates, bulk cancellations

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

### 🆕 Automatic Position Updates

The `UnifiedFillManager` monitors ALL fill events to automatically update positions:

```python
class UnifiedFillManager:
    """Centralized manager for all order fills and protective order updates."""
    
    async def on_order_fill(self, event):
        """Handle order fill events and update protective orders."""
        # Handles ALL fill types (main, double down, protective)
        # Updates protective orders on ANY fill to match position size
        # Handles partial fills correctly
        # Only closes position on FULL protective fills
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
- **🆕 Order Mixing Prevention**: Position side tracking prevents mixing long/short orders

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

# Create rule
buy_rule = Rule(
    rule_id="high_confidence_buy",
    name="High Confidence Buy Entry",
    condition=buy_condition,
    action=buy_action,
    priority=100
)
```

## Best Practices

1. **Always specify position side explicitly** when creating orders
2. **Use PositionTracker** to check for existing positions before creating new ones
3. **Let the system handle order signs** - it will ensure correct positive/negative values
4. **Monitor position status** to understand trade lifecycle
5. **Use protective orders** to manage risk automatically
6. **Leverage position reversal** for clean transitions between long/short positions

## Common Patterns

### Entry with Protective Orders
```python
# Long entry with percentage-based stops
LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    auto_create_stops=True,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Short entry with ATR-based stops
LinkedCreateOrderAction(
    symbol="AAPL", 
    quantity=100,
    side="SELL",
    auto_create_stops=True,
    atr_stop_multiplier=2.0,
    atr_target_multiplier=4.0
)
```

### Scale-In on Profit
```python
# Add to position when profitable
LinkedScaleInAction(
    symbol="AAPL",
    scale_quantity=50,
    trigger_profit_pct=0.02
)
```

### Clean Position Exit
```python
# Close all orders and position
LinkedCloseAllAction(
    symbol="AAPL",
    reason="Manual exit"
)
```

## Summary

The order and position management system provides:

1. **🆕 Unified position tracking** through PositionTracker
2. **🆕 Complete order relationship management** in Position objects
3. **🆕 Automatic side-aware order placement** for both long and short positions
4. **🆕 Clean position lifecycle** with proper status tracking
5. **🆕 Position reversal capability** for opposing signals
6. **Event-driven architecture** for loose coupling
7. **Comprehensive risk management** with automatic protective orders
8. **Flexible and extensible design** for custom trading strategies