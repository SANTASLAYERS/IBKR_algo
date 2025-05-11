# Rule Engine Test Suite Documentation

## Overview

This document describes the test suite for the Rule Engine component of the IBKR Trading Framework. The tests verify the functionality of the rule-based decision system that enables automated trading strategies.

## Test Structure

The tests are organized in the following categories:

### Condition Tests

Tests for the condition evaluation components that determine when rules should trigger:

1. **Event Conditions**: Tests for conditions that trigger based on events
   - Verify matching on event types
   - Verify filtering on event field values
   - Test condition evaluation with context

2. **Position Conditions**: Tests for conditions that trigger based on position state
   - Verify filtering based on unrealized P&L percentages
   - Verify filtering based on position properties
   - Test evaluation with varying position contexts

3. **Time Conditions**: Tests for conditions that trigger based on time
   - Verify time range restrictions
   - Verify day-of-week filtering
   - Test market hours filtering

4. **Composite Conditions**: Tests for logical combinations of conditions
   - Test AND combinations (`condition1 & condition2`)
   - Test OR combinations (`condition1 | condition2`)
   - Test NOT expressions (`~condition1`)
   - Test complex nested expressions

### Action Tests

Tests for the action execution components that determine what happens when rules trigger:

1. **Position Actions**: Tests for position-related actions
   - Test creating positions
   - Test closing positions
   - Test adjusting position parameters

2. **Order Actions**: Tests for order-related actions
   - Test creating orders
   - Test cancelling orders
   - Test creating bracket orders

3. **Composite Actions**: Tests for action composition
   - Test sequential action execution
   - Test conditional action execution

### Rule Tests

Tests for the `Rule` class that combines conditions and actions:

1. **Rule Initialization**: Tests for rule creation and properties
   - Verify rule properties are correctly set
   - Test default values

2. **Rule Evaluation and Execution**: Tests for rule behavior
   - Test condition evaluation followed by action execution
   - Verify execution tracking (counts, timestamps)
   
3. **Rule Cooldown**: Tests for execution rate limiting
   - Verify cooldown periods prevent re-execution
   - Test cooldown expiration

### Rule Engine Tests

Tests for the `RuleEngine` class that manages rules:

1. **Engine Initialization**: Tests for engine creation and properties
   - Verify initial state

2. **Rule Registration**: Tests for rule management
   - Test registering rules
   - Test unregistering rules
   - Test enabling/disabling rules

3. **Context Management**: Tests for context sharing
   - Test setting individual context values
   - Test updating multiple context values

4. **Event Handling**: Tests for event-based rule triggering
   - Test rule evaluation on event reception
   - Verify event propagation to rule conditions

5. **Rule Prioritization**: Tests for execution ordering
   - Verify rules execute in priority order (highest first)
   - Test equal priority handling

6. **Real-World Scenarios**: Integration tests for realistic use cases
   - Test trading based on price signals
   - Verify position creation through the rule system

## Key Test Files

- `/tests/rule_engine/test_rule_engine.py`: Main test file for all rule engine components

## Test Fixtures

The tests use several fixtures to facilitate testing:

1. **event_loop**: Provides an asyncio event loop for testing asynchronous code
2. **event_bus**: Creates an `EventBus` instance for testing event handling
3. **position_tracker**: Provides a mock position tracker for testing position actions
4. **order_manager**: Provides a mock order manager for testing order actions
5. **rule_engine**: Creates a `RuleEngine` connected to the test event bus

## Test Approach

The Rule Engine tests follow these principles:

1. **Unit Testing**: Components are tested in isolation with mocks for dependencies
2. **Integration Testing**: Components are tested together to verify interaction
3. **Scenario Testing**: Realistic trading scenarios verify end-to-end behavior

## Mocking Strategy

The tests use mocks to isolate the Rule Engine from external dependencies:

1. **Position Tracker**: Mocked to verify actions without actual position creation
2. **Order Manager**: Mocked to verify order operations without broker interaction
3. **Event Bus**: Real instance used for proper event propagation testing
4. **Events**: Real instances used with controlled properties

## Special Testing Considerations

1. **Asynchronous Testing**: All tests use `pytest-asyncio` for testing async code
2. **Clock Manipulation**: Time-based conditions are tested by mocking datetime functions
3. **Evaluation Loop**: Tests can disable the periodic evaluation loop using the `_skip_evaluation_loop_for_testing` context flag

## Running the Tests

```bash
# Run all rule engine tests
pytest tests/rule_engine/ -v

# Run specific test classes
pytest tests/rule_engine/test_rule_engine.py::TestConditions -v
pytest tests/rule_engine/test_rule_engine.py::TestActions -v
pytest tests/rule_engine/test_rule_engine.py::TestRule -v
pytest tests/rule_engine/test_rule_engine.py::TestRuleEngine -v

# Run with coverage
pytest --cov=src.rule tests/rule_engine/
```

## Test Examples

### Condition Test Example

```python
@pytest.mark.asyncio
async def test_event_condition(self):
    """Test event condition evaluation."""
    # Create a condition that matches PriceEvent with symbol="AAPL"
    condition = EventCondition(
        event_type=PriceEvent,
        field_conditions={"symbol": "AAPL"}
    )
    
    # Create matching and non-matching events
    matching_event = PriceEvent(symbol="AAPL", price=150.0)
    non_matching_event = PriceEvent(symbol="MSFT", price=250.0)
    
    # Test with matching event
    context = {"event": matching_event}
    result = await condition.evaluate(context)
    assert result is True
    
    # Test with non-matching event
    context = {"event": non_matching_event}
    result = await condition.evaluate(context)
    assert result is False
```

### Real-World Scenario Test Example

```python
@pytest.mark.asyncio
async def test_real_world_rule_scenario(self, rule_engine, event_bus, position_tracker, order_manager):
    """Test a more realistic rule scenario."""
    # Create a rule to buy AAPL when price is above 150
    buy_condition = EventCondition(
        event_type=PriceEvent,
        field_conditions={
            "symbol": "AAPL",
            "price": lambda p: p > 150.0
        }
    )
    
    buy_action = CreatePositionAction(
        symbol="AAPL",
        quantity=100,
        stop_loss_pct=0.03,
        take_profit_pct=0.09
    )
    
    buy_rule = Rule(
        rule_id="buy_aapl_momentum",
        name="Buy AAPL Momentum",
        description="Buy AAPL when price breaks above 150",
        condition=buy_condition,
        action=buy_action,
        enabled=True
    )
    
    # Register and activate the rule
    rule_engine.register_rule(buy_rule)
    await rule_engine.start()
    
    # Emit a price event that should trigger the rule
    price_event = PriceEvent(symbol="AAPL", price=152.0)
    await event_bus.emit(price_event)
    
    # Verify the rule created a position
    position_tracker.create_stock_position.assert_called_once_with(
        symbol="AAPL",
        quantity=100,
        stop_loss_pct=0.03,
        take_profit_pct=0.09
    )
```

## Future Test Enhancements

1. **Performance Testing**: Add tests to verify rule evaluation performance with many rules
2. **Concurrency Testing**: Enhance tests for concurrent rule execution
3. **Rule Persistence**: Add tests for saving and loading rule configurations
4. **Extended Scenarios**: Add more complex multi-rule scenarios 
5. **Stress Testing**: Test behavior under high event volume