# Migration Guide: Context System to PositionTracker

This guide explains the migration from the legacy transient context system to the unified PositionTracker approach.

## Overview of Changes

The system has been simplified by removing the transient context-based position tracking and consolidating all position and order management into the PositionTracker. This provides:

- **Single Source of Truth**: All position data in one place
- **Persistence**: State maintained across rule executions
- **Cleaner Code**: No more dual-write between systems
- **Better Maintainability**: Simpler to understand and debug

## What Changed

### Before (Context System)

```python
# Position data stored in context dictionary
context["AAPL"] = {
    "side": "BUY",
    "main_orders": ["ORDER123"],
    "stop_orders": ["STOP456"],
    "target_orders": ["TARGET789"],
    "quantity": 100,
    "entry_price": 150.00,
    "status": "active"
}

# LinkedOrderManager static methods
LinkedOrderManager.add_order(context, "AAPL", order_id, "stop", "BUY")
order_group = LinkedOrderManager.get_order_group(context, "AAPL", "BUY")
```

### After (PositionTracker)

```python
# Position data stored in Position objects
position = await position_tracker.create_position(
    symbol="AAPL",
    side="BUY",
    quantity=100,
    entry_price=150.00
)

# Direct position object manipulation
position.main_order_ids.append("ORDER123")
position.stop_order_ids.append("STOP456")
position.target_order_ids.append("TARGET789")
```

## Code Migration Examples

### 1. Creating a New Position

**Before:**
```python
# In LinkedCreateOrderAction
if symbol not in context:
    context[symbol] = {
        "side": side,
        "main_orders": [],
        "stop_orders": [],
        "target_orders": [],
        "status": "active"
    }
context[symbol]["main_orders"].append(order.order_id)
```

**After:**
```python
# In LinkedCreateOrderAction
position = await position_tracker.create_position(
    symbol=symbol,
    side=side,
    quantity=quantity,
    entry_price=current_price
)
position.main_order_ids.append(order.order_id)
```

### 2. Checking for Existing Position

**Before:**
```python
if symbol in context and context[symbol]["status"] == "active":
    existing_side = context[symbol]["side"]
    # ... handle existing position
```

**After:**
```python
positions = await position_tracker.get_positions_for_symbol(symbol)
active_positions = [p for p in positions if p.status == PositionStatus.OPEN]
if active_positions:
    existing_position = active_positions[0]
    existing_side = existing_position.side
    # ... handle existing position
```

### 3. Adding Orders to Position

**Before:**
```python
LinkedOrderManager.add_order(context, symbol, stop_order_id, "stop", side)
LinkedOrderManager.add_order(context, symbol, target_order_id, "target", side)
```

**After:**
```python
position.stop_order_ids.append(stop_order_id)
position.target_order_ids.append(target_order_id)
await position_tracker.update_position(position.position_id)
```

### 4. Closing a Position

**Before:**
```python
# Cancel all orders
for order_id in context[symbol]["stop_orders"]:
    await order_manager.cancel_order(order_id)
# ... cancel other order types

# Clear context
del context[symbol]
```

**After:**
```python
# Cancel all orders
for order_id in position.stop_order_ids:
    await order_manager.cancel_order(order_id)
# ... cancel other order types

# Close position
await position_tracker.close_position(position.position_id, reason)
```

### 5. Accessing Position Data in Rules

**Before:**
```python
class MyCondition(Condition):
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if self.symbol in context:
            position_data = context[self.symbol]
            side = position_data["side"]
            # ... use position data
```

**After:**
```python
class MyCondition(Condition):
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        position_tracker = context.get("position_tracker")
        positions = await position_tracker.get_positions_for_symbol(self.symbol)
        if positions:
            position = positions[0]  # Assuming one position per symbol
            side = position.side
            # ... use position data
```

## Testing Changes

### Unit Tests

**Before:**
```python
# Mock context with position data
context = {
    "AAPL": {
        "side": "BUY",
        "main_orders": ["ORDER123"],
        "status": "active"
    }
}
```

**After:**
```python
# Mock position tracker and position
mock_position = Mock()
mock_position.symbol = "AAPL"
mock_position.side = "BUY"
mock_position.main_order_ids = ["ORDER123"]
mock_position.status = PositionStatus.OPEN

context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
```

### Integration Tests

Tests that previously checked `context[symbol]` should now verify position state through PositionTracker:

**Before:**
```python
assert "AAPL" in context
assert context["AAPL"]["side"] == "BUY"
assert len(context["AAPL"]["main_orders"]) == 1
```

**After:**
```python
positions = await position_tracker.get_positions_for_symbol("AAPL")
assert len(positions) == 1
assert positions[0].side == "BUY"
assert len(positions[0].main_order_ids) == 1
```

## Benefits of the New System

1. **Simplified State Management**: No more synchronizing between context and PositionTracker
2. **Type Safety**: Position objects have defined fields vs. dictionary keys
3. **Better Encapsulation**: Position logic contained in Position/PositionTracker classes
4. **Easier Debugging**: Can inspect position objects directly
5. **Persistence**: Position state survives between rule executions

## Backward Compatibility

The migration maintains backward compatibility for:
- Rule engine context passing (still uses Dict[str, Any])
- System component access (order_manager, position_tracker, etc.)
- Event handling and rule evaluation

## Common Pitfalls to Avoid

1. **Don't store position data in context**: Use PositionTracker exclusively
2. **Don't access context[symbol]**: This pattern no longer exists
3. **Remember async operations**: PositionTracker methods are async
4. **Check for empty position lists**: `get_positions_for_symbol` returns a list

## Summary

The migration from context-based position tracking to PositionTracker simplifies the codebase and provides a more robust foundation for position management. While it requires updating existing code, the benefits in maintainability and clarity make it worthwhile. 