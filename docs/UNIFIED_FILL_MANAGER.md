# Unified Fill Manager Documentation

## Overview

The Unified Fill Manager is a centralized component that handles ALL order fill events in the trading system and automatically updates protective orders based on the current position size. This replaces the previous approach of having separate managers for different fill types.

## Key Features

1. **Centralized Fill Handling**: Single manager handles all fill types (main orders, double downs, protective orders)
2. **Automatic Protective Order Updates**: Updates stop loss and take profit orders on ANY fill to match current position size
3. **Partial Fill Support**: Correctly handles partial fills for limit and stop orders
4. **Position Closure Logic**: Only closes positions when protective orders are FULLY filled

## Architecture

### Component Relationships

```
FillEvent → UnifiedFillManager → PositionManager
                ↓                      ↓
          OrderManager          Position Tracking
                ↓
        Protective Order Updates
```

### Fill Event Processing Flow

1. **Fill Event Received**: Manager receives fill event from event bus
2. **Order Type Detection**: Determines if fill is for main, double down, stop, or target order
3. **Position Calculation**: Calculates current net position including partial fills
4. **Action Based on Order Type**:
   - **Main Order**: No action needed (protective orders already created)
   - **Double Down**: Update protective orders to new position size
   - **Protective Order (Partial)**: Update OTHER protective order to match remaining position
   - **Protective Order (Full)**: Close entire position and cancel all orders

## Implementation Details

### Key Methods

#### `on_order_fill(event: FillEvent)`
Main event handler that processes all fill events.

```python
async def on_order_fill(self, event: FillEvent):
    # Get position from PositionManager
    position = position_manager.get_position(symbol)
    
    # Determine order type
    order_type = self._get_order_type(position, order_id)
    
    # Check if fully filled
    is_fully_filled = (order.status.value == "filled")
    
    # Handle based on order type
    if order_type == "main":
        # Market order - always complete
        await self._handle_main_order_fill(symbol, position)
    elif order_type == "doubledown":
        # May be partial
        await self._handle_doubledown_fill(symbol, position)
    elif order_type in ["stop", "target"]:
        if is_fully_filled:
            await self._handle_position_closure(symbol, reason)
        else:
            await self._handle_protective_partial_fill(symbol, position, order_type)
```

#### `_calculate_current_position_size(symbol: str)`
Calculates the current net position considering all fills.

```python
async def _calculate_current_position_size(self, symbol: str) -> float:
    total_position = 0.0
    
    # Main orders (market - always fully filled)
    for order_id in position.main_orders:
        order = await order_manager.get_order(order_id)
        total_position += order.quantity  # Full quantity
    
    # Double down orders (may be partially filled)
    for order_id in position.doubledown_orders:
        order = await order_manager.get_order(order_id)
        total_position += order.filled_quantity  # Actual filled amount
    
    # Protective order fills (reduce position)
    for order_id in position.stop_orders + position.target_orders:
        order = await order_manager.get_order(order_id)
        total_position += order.filled_quantity  # Negative for closing
    
    return total_position
```

#### `_update_protective_orders(symbol, position_size, position, exclude_type)`
Updates protective orders to match current position size.

```python
async def _update_protective_orders(self, symbol: str, position_size: float, 
                                   position, exclude_type: Optional[str] = None):
    # Determine protective quantity (opposite sign)
    is_long = position_size > 0
    protective_quantity = -abs(position_size) if is_long else abs(position_size)
    
    # Update stop orders (unless excluded)
    if exclude_type != "stop":
        for stop_id in position.stop_orders:
            await self._replace_protective_order(
                symbol, stop_id, protective_quantity, "stop", 
                stop_order.stop_price, position
            )
    
    # Update target orders (unless excluded)
    if exclude_type != "target":
        for target_id in position.target_orders:
            await self._replace_protective_order(
                symbol, target_id, protective_quantity, "target",
                target_order.limit_price, position
            )
```

## Migration from Legacy Managers

### Deprecated Components

1. **LinkedOrderConclusionManager**: Previously handled position closure on protective fills
2. **LinkedDoubleDownFillManager**: Previously handled protective order updates after double down fills

### Migration Steps

1. **Update Imports**:
```python
# Old
from src.rule.linked_order_actions import LinkedOrderConclusionManager, LinkedDoubleDownFillManager

# New
from src.rule.unified_fill_manager import UnifiedFillManager
```

2. **Initialize UnifiedFillManager**:
```python
# Replace both managers with single unified manager
self.unified_fill_manager = UnifiedFillManager(
    context=self.rule_engine.context,
    event_bus=self.event_bus
)
await self.unified_fill_manager.initialize()
```

3. **Feature Flag for Legacy Managers**:
```python
# Only initialize legacy managers if explicitly enabled
if FeatureFlags.get("ENABLE_LEGACY_FILL_MANAGERS", False):
    # Initialize deprecated managers
```

## Benefits

1. **Simplified Architecture**: Single manager instead of multiple specialized managers
2. **Consistent Behavior**: All fills handled uniformly
3. **Better Partial Fill Support**: Correctly handles partial fills for all order types
4. **Reduced Code Duplication**: Common logic centralized
5. **Easier Maintenance**: Single place to update fill handling logic

## Example Scenarios

### Scenario 1: Double Down Partial Fill
1. Position: Long 100 shares
2. Double down order for 100 shares fills 60 shares
3. New position: 160 shares
4. Manager updates stop/target orders from -100 to -160 shares

### Scenario 2: Stop Loss Partial Fill
1. Position: Long 200 shares
2. Stop loss for -200 shares fills -50 shares
3. Remaining position: 150 shares
4. Manager updates target order from -200 to -150 shares
5. Stop order continues working for remaining -150 shares

### Scenario 3: Take Profit Full Fill
1. Position: Long 100 shares
2. Take profit order fills completely (-100 shares)
3. Position flat
4. Manager cancels all remaining orders and closes position

## Configuration

No special configuration required. The manager automatically:
- Subscribes to FillEvent on initialization
- Uses existing context components (OrderManager, PositionManager, etc.)
- Handles all fill types without configuration

## Testing

Test coverage includes:
- Main order fills (market orders)
- Double down fills (partial and full)
- Protective order partial fills
- Protective order full fills
- Position closure scenarios
- Edge cases (flat positions, missing orders, etc.)

## Future Enhancements

1. **Fill Aggregation**: Combine multiple partial fills before updating orders
2. **Smart Order Replacement**: Only replace orders if quantity change is significant
3. **Performance Optimization**: Batch order updates for efficiency
4. **Advanced Partial Fill Strategies**: Different handling based on fill percentage 