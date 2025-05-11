"""
Tests for the rule engine components including conditions, actions, and rule evaluation.
"""

import asyncio
import pytest
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.event.base import BaseEvent
from src.event.bus import EventBus
from src.event.market import MarketEvent, PriceEvent
from src.event.order import OrderEvent, FillEvent as OrderFillEvent, OrderStatus, OrderType, TimeInForce, OrderSide
from enum import Enum
from src.event.position import PositionEvent, PositionUpdateEvent, PositionStatus


# Import Rule Engine components (these will fail until implemented)
from src.rule.base import Rule, Condition, Action
from src.rule.condition import (
    EventCondition, PositionCondition, TimeCondition, MarketCondition,
    AndCondition, OrCondition, NotCondition
)
from src.rule.action import (
    CreatePositionAction, ClosePositionAction, AdjustPositionAction,
    CreateOrderAction, CancelOrderAction, CreateBracketOrderAction,
    SequentialAction, ConditionalAction, LogAction
)
from src.rule.engine import RuleEngine


@pytest.fixture
def event_loop():
    """Create an event loop for testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def position_tracker():
    """Create a mock position tracker."""
    mock = AsyncMock()
    mock.create_stock_position = AsyncMock()
    mock.close_position = AsyncMock()
    mock.adjust_position = AsyncMock()
    mock.get_position = AsyncMock()
    return mock


@pytest.fixture
def order_manager():
    """Create a mock order manager."""
    mock = AsyncMock()
    mock.create_order = AsyncMock()
    mock.cancel_order = AsyncMock()
    mock.create_bracket_order = AsyncMock()
    return mock


@pytest.fixture
def rule_engine(event_bus, position_tracker, order_manager):
    """Create a rule engine for testing."""
    engine = RuleEngine(event_bus)
    engine.set_context("position_tracker", position_tracker)
    engine.set_context("order_manager", order_manager)
    return engine


class TestConditions:
    """Tests for the condition components."""

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
    
    @pytest.mark.asyncio
    async def test_position_condition(self):
        """Test position condition evaluation."""
        # Create a condition for profitable positions
        condition = PositionCondition(
            min_unrealized_pnl_pct=0.05  # 5% profit
        )
        
        # Create mock positions
        profitable_position = MagicMock()
        profitable_position.unrealized_pnl_pct = 0.07  # 7% profit
        
        unprofitable_position = MagicMock()
        unprofitable_position.unrealized_pnl_pct = 0.02  # 2% profit (below threshold)
        
        # Test with profitable position
        context = {"position": profitable_position}
        result = await condition.evaluate(context)
        assert result is True
        
        # Test with unprofitable position
        context = {"position": unprofitable_position}
        result = await condition.evaluate(context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_time_condition(self):
        """Test time condition evaluation."""
        # Create a condition for market hours (9:30 AM to 4:00 PM)
        condition = TimeCondition(
            start_time=time(9, 30),
            end_time=time(16, 0),
            days_of_week=[0, 1, 2, 3, 4]  # Monday to Friday
        )
        
        # Mock datetime.now for testing
        # This would be Monday at 10:00 AM
        mock_now = datetime(2023, 5, 1, 10, 0)  # Monday at 10:00 AM
        
        # Test during market hours on a weekday
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr("src.rule.condition.datetime", MagicMock(now=lambda: mock_now))
            result = await condition.evaluate({})
            assert result is True
        
        # Test outside market hours on a weekday
        mock_now = datetime(2023, 5, 1, 8, 0)  # Monday at 8:00 AM (before market)
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr("src.rule.condition.datetime", MagicMock(now=lambda: mock_now))
            result = await condition.evaluate({})
            assert result is False
        
        # Test on weekend
        mock_now = datetime(2023, 5, 6, 10, 0)  # Saturday at 10:00 AM
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr("src.rule.condition.datetime", MagicMock(now=lambda: mock_now))
            result = await condition.evaluate({})
            assert result is False
    
    @pytest.mark.asyncio
    async def test_composite_conditions(self):
        """Test composite conditions (AND, OR, NOT)."""
        # Create simple conditions
        condition_a = EventCondition(
            event_type=PriceEvent,
            field_conditions={"symbol": "AAPL"}
        )
        
        condition_b = EventCondition(
            event_type=PriceEvent,
            field_conditions={"price": lambda p: p > 150.0}
        )
        
        # Create composite conditions
        and_condition = AndCondition(condition_a, condition_b)
        or_condition = OrCondition(condition_a, condition_b)
        not_condition = NotCondition(condition_a)
        
        # Create test events
        event1 = PriceEvent(symbol="AAPL", price=160.0)  # Matches both
        event2 = PriceEvent(symbol="AAPL", price=140.0)  # Matches only A
        event3 = PriceEvent(symbol="MSFT", price=160.0)  # Matches only B
        event4 = PriceEvent(symbol="MSFT", price=140.0)  # Matches neither
        
        # Test AND condition
        assert await and_condition.evaluate({"event": event1}) is True
        assert await and_condition.evaluate({"event": event2}) is False
        assert await and_condition.evaluate({"event": event3}) is False
        assert await and_condition.evaluate({"event": event4}) is False
        
        # Test OR condition
        assert await or_condition.evaluate({"event": event1}) is True
        assert await or_condition.evaluate({"event": event2}) is True
        assert await or_condition.evaluate({"event": event3}) is True
        assert await or_condition.evaluate({"event": event4}) is False
        
        # Test NOT condition
        assert await not_condition.evaluate({"event": event1}) is False
        assert await not_condition.evaluate({"event": event2}) is False
        assert await not_condition.evaluate({"event": event3}) is True
        assert await not_condition.evaluate({"event": event4}) is True
        
        # Test operator overloading
        combined_condition = condition_a & condition_b  # AND
        assert await combined_condition.evaluate({"event": event1}) is True
        assert await combined_condition.evaluate({"event": event2}) is False
        
        combined_condition = condition_a | condition_b  # OR
        assert await combined_condition.evaluate({"event": event1}) is True
        assert await combined_condition.evaluate({"event": event3}) is True
        
        combined_condition = ~condition_a  # NOT
        assert await combined_condition.evaluate({"event": event1}) is False
        assert await combined_condition.evaluate({"event": event3}) is True


class TestActions:
    """Tests for the action components."""
    
    @pytest.mark.asyncio
    async def test_create_position_action(self, position_tracker):
        """Test create position action."""
        # Create the action
        action = CreatePositionAction(
            symbol="AAPL",
            quantity=100,
            stop_loss_pct=0.03,
            take_profit_pct=0.09
        )
        
        # Execute the action
        context = {"position_tracker": position_tracker}
        result = await action.execute(context)
        
        # Verify the action called the position tracker
        assert result is True
        position_tracker.create_stock_position.assert_called_once_with(
            symbol="AAPL",
            quantity=100,
            stop_loss_pct=0.03,
            take_profit_pct=0.09
        )
    
    @pytest.mark.asyncio
    async def test_close_position_action(self, position_tracker):
        """Test close position action."""
        # Create the action
        action = ClosePositionAction(
            position_id="test_position_123",
            reason="Take profit"
        )
        
        # Execute the action
        context = {"position_tracker": position_tracker}
        result = await action.execute(context)
        
        # Verify the action called the position tracker
        assert result is True
        position_tracker.close_position.assert_called_once_with(
            position_id="test_position_123",
            reason="Take profit"
        )
    
    @pytest.mark.asyncio
    async def test_create_order_action(self, order_manager):
        """Test create order action."""
        # Create the action
        action = CreateOrderAction(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            auto_submit=True
        )
        
        # Execute the action
        context = {"order_manager": order_manager}
        result = await action.execute(context)
        
        # Verify the action called the order manager
        assert result is True
        order_manager.create_order.assert_called_once_with(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            limit_price=None,
            stop_price=None,
            time_in_force=None,
            auto_submit=True
        )
    
    @pytest.mark.asyncio
    async def test_sequential_action(self, position_tracker, order_manager):
        """Test sequential action execution."""
        # Create component actions
        action1 = CreatePositionAction(symbol="AAPL", quantity=100)
        action2 = CreateOrderAction(symbol="AAPL", quantity=-100, order_type=OrderType.LIMIT, limit_price=160.0)
        
        # Create sequential action
        sequential = SequentialAction(action1, action2)
        
        # Execute the action
        context = {
            "position_tracker": position_tracker,
            "order_manager": order_manager
        }
        result = await sequential.execute(context)
        
        # Verify both actions were called
        assert result is True
        position_tracker.create_stock_position.assert_called_once()
        order_manager.create_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conditional_action(self, position_tracker):
        """Test conditional action execution."""
        # Create condition and action
        condition = PositionCondition(min_unrealized_pnl_pct=0.05)
        action = ClosePositionAction(reason="Take profit")
        
        # Create conditional action
        conditional = ConditionalAction(condition, action)
        
        # Create mock positions
        profitable_position = MagicMock()
        profitable_position.unrealized_pnl_pct = 0.07  # 7% profit
        profitable_position.position_id = "test_position_123"
        
        unprofitable_position = MagicMock()
        unprofitable_position.unrealized_pnl_pct = 0.02  # 2% profit (below threshold)
        
        # Test with profitable position (should execute)
        context = {
            "position": profitable_position,
            "position_tracker": position_tracker
        }
        result = await conditional.execute(context)
        
        assert result is True
        position_tracker.close_position.assert_called_once()
        
        # Reset mock
        position_tracker.close_position.reset_mock()
        
        # Test with unprofitable position (should not execute)
        context = {
            "position": unprofitable_position,
            "position_tracker": position_tracker
        }
        result = await conditional.execute(context)
        
        assert result is True  # Still returns True for "success"
        position_tracker.close_position.assert_not_called()


class TestRule:
    """Tests for the Rule class."""
    
    def test_rule_initialization(self):
        """Test rule initialization and properties."""
        # Create a mock condition and action
        condition = MagicMock()
        action = MagicMock()
        
        # Create a rule
        rule = Rule(
            rule_id="test_rule_123",
            name="Test Rule",
            description="A rule for testing",
            condition=condition,
            action=action,
            priority=100,
            cooldown_seconds=60
        )
        
        # Verify rule properties
        assert rule.rule_id == "test_rule_123"
        assert rule.name == "Test Rule"
        assert rule.description == "A rule for testing"
        assert rule.condition is condition
        assert rule.action is action
        assert rule.priority == 100
        assert rule.cooldown_seconds == 60
        assert rule.enabled is True
        assert rule.last_execution_time is None
        assert rule.execution_count == 0
    
    @pytest.mark.asyncio
    async def test_rule_evaluate_and_execute(self):
        """Test rule evaluation and execution."""
        # Create a mock condition and action
        condition = AsyncMock()
        condition.evaluate.return_value = True
        
        action = AsyncMock()
        action.execute.return_value = True
        
        # Create a rule
        rule = Rule(
            rule_id="test_rule_123",
            name="Test Rule",
            description="A rule for testing",
            condition=condition,
            action=action
        )
        
        # Create a context
        context = {"test_key": "test_value"}
        
        # Test rule evaluation and execution
        result = await rule.evaluate_and_execute(context)
        
        # Verify rule evaluation and execution
        assert result is True
        condition.evaluate.assert_called_once_with(context)
        action.execute.assert_called_once_with(context)
        assert rule.last_execution_time is not None
        assert rule.execution_count == 1
    
    @pytest.mark.asyncio
    async def test_rule_cooldown(self):
        """Test rule cooldown period."""
        # Create a mock condition and action
        condition = AsyncMock()
        condition.evaluate.return_value = True
        
        action = AsyncMock()
        action.execute.return_value = True
        
        # Create a rule with a cooldown period
        rule = Rule(
            rule_id="test_rule_123",
            name="Test Rule",
            description="A rule for testing",
            condition=condition,
            action=action,
            cooldown_seconds=60  # 60 second cooldown
        )
        
        # Create a context
        context = {"test_key": "test_value"}
        
        # Execute the rule once
        await rule.evaluate_and_execute(context)
        assert rule.execution_count == 1
        
        # Try to execute again immediately (should be on cooldown)
        result = await rule.evaluate_and_execute(context)
        assert result is False  # Rule did not execute due to cooldown
        assert rule.execution_count == 1  # Count did not increase
        
        # Fast-forward time by setting last_execution_time in the past
        rule.last_execution_time = datetime.now() - timedelta(seconds=120)
        
        # Try to execute again after cooldown period
        result = await rule.evaluate_and_execute(context)
        assert result is True  # Rule executed
        assert rule.execution_count == 2  # Count increased


class TestRuleEngine:
    """Tests for the Rule Engine."""
    
    def test_rule_engine_initialization(self, event_bus):
        """Test rule engine initialization."""
        engine = RuleEngine(event_bus)
        
        assert engine.event_bus is event_bus
        assert len(engine.rules) == 0
        assert engine.running is False
    
    @pytest.mark.asyncio
    async def test_register_and_unregister_rule(self, rule_engine):
        """Test registering and unregistering rules."""
        # Create a mock rule
        rule = MagicMock()
        rule.rule_id = "test_rule_123"
        
        # Register the rule
        result = rule_engine.register_rule(rule)
        assert result is True
        assert "test_rule_123" in rule_engine.rules
        assert rule_engine.rules["test_rule_123"] is rule
        
        # Unregister the rule
        result = rule_engine.unregister_rule("test_rule_123")
        assert result is True
        assert "test_rule_123" not in rule_engine.rules
        
        # Try to unregister a non-existent rule
        result = rule_engine.unregister_rule("non_existent_rule")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_enable_disable_rule(self, rule_engine):
        """Test enabling and disabling rules."""
        # Create a mock rule
        rule = MagicMock()
        rule.rule_id = "test_rule_123"
        rule.enabled = True
        
        # Register the rule
        rule_engine.register_rule(rule)
        
        # Disable the rule
        result = rule_engine.disable_rule("test_rule_123")
        assert result is True
        assert rule.enabled is False
        
        # Enable the rule
        result = rule_engine.enable_rule("test_rule_123")
        assert result is True
        assert rule.enabled is True
        
        # Try to enable/disable a non-existent rule
        assert rule_engine.enable_rule("non_existent_rule") is False
        assert rule_engine.disable_rule("non_existent_rule") is False
    
    @pytest.mark.asyncio
    async def test_rule_engine_context(self, rule_engine):
        """Test rule engine context management."""
        # Set individual context values
        rule_engine.set_context("key1", "value1")
        assert rule_engine.context["key1"] == "value1"
        
        # Update multiple context values
        rule_engine.update_context({"key2": "value2", "key3": "value3"})
        assert rule_engine.context["key1"] == "value1"
        assert rule_engine.context["key2"] == "value2"
        assert rule_engine.context["key3"] == "value3"
    
    @pytest.mark.asyncio
    async def test_rule_engine_event_handling(self, rule_engine, event_bus):
        """Test rule engine handling events."""
        # Create a rule with a mock condition and action
        condition = AsyncMock()
        condition.evaluate.return_value = True
        
        action = AsyncMock()
        action.execute.return_value = True
        
        rule = Rule(
            rule_id="test_rule_123",
            name="Test Rule",
            description="A rule for testing",
            condition=condition,
            action=action,
            enabled=True
        )
        
        # Register the rule
        rule_engine.register_rule(rule)

        # Skip evaluation loop for testing to prevent duplicate calls
        rule_engine.set_context("_skip_evaluation_loop_for_testing", True)

        # Start the rule engine
        await rule_engine.start()
        assert rule_engine.running is True
        
        # Create an event
        event = PriceEvent(symbol="AAPL", price=150.0)
        
        # Emit the event
        await event_bus.emit(event)
        
        # Wait for async processing
        await asyncio.sleep(0.1)
        
        # Verify the rule was evaluated
        condition.evaluate.assert_called_once()
        assert "event" in condition.evaluate.call_args[0][0]
        assert condition.evaluate.call_args[0][0]["event"] is event
        
        # Verify the action was executed
        action.execute.assert_called_once()
        
        # Stop the rule engine
        await rule_engine.stop()
        assert rule_engine.running is False
    
    @pytest.mark.asyncio
    async def test_rule_engine_rule_prioritization(self, rule_engine):
        """Test rule engine prioritizing rules by priority."""
        # Create rules with different priorities
        execution_order = []
        
        async def mock_action(context):
            execution_order.append(context["rule_id"])
            return True
        
        # Mock condition that always evaluates to true
        condition = AsyncMock()
        condition.evaluate.return_value = True
        
        # Create rules with different priorities
        high_priority_rule = Rule(
            rule_id="high_priority",
            name="High Priority Rule",
            description="A rule with high priority",
            condition=condition,
            action=AsyncMock(execute=lambda ctx: mock_action({"rule_id": "high_priority"})),
            priority=100,
            enabled=True
        )
        
        medium_priority_rule = Rule(
            rule_id="medium_priority",
            name="Medium Priority Rule",
            description="A rule with medium priority",
            condition=condition,
            action=AsyncMock(execute=lambda ctx: mock_action({"rule_id": "medium_priority"})),
            priority=50,
            enabled=True
        )
        
        low_priority_rule = Rule(
            rule_id="low_priority",
            name="Low Priority Rule",
            description="A rule with low priority",
            condition=condition,
            action=AsyncMock(execute=lambda ctx: mock_action({"rule_id": "low_priority"})),
            priority=10,
            enabled=True
        )
        
        # Register the rules (in reverse priority order)
        rule_engine.register_rule(low_priority_rule)
        rule_engine.register_rule(medium_priority_rule)
        rule_engine.register_rule(high_priority_rule)
        
        # Evaluate all rules
        await rule_engine._evaluate_all_rules()
        
        # Verify execution order based on priority (highest first)
        assert execution_order[0] == "high_priority"
        assert execution_order[1] == "medium_priority"
        assert execution_order[2] == "low_priority"
    
    @pytest.mark.asyncio
    async def test_real_world_rule_scenario(self, rule_engine, event_bus, position_tracker, order_manager):
        """Test a more realistic rule scenario."""
        # Create the position tracker
        position_tracker.has_position = AsyncMock(return_value=False)
        position_tracker.create_stock_position.return_value = MagicMock(position_id="new_position_123")
        
        # Register a rule to buy AAPL when price is above 150
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
        
        # Register the rule
        rule_engine.register_rule(buy_rule)

        # Skip evaluation loop for testing to prevent duplicate calls
        rule_engine.set_context("_skip_evaluation_loop_for_testing", True)

        # Start the rule engine
        await rule_engine.start()
        
        # Create a price event
        price_event = PriceEvent(symbol="AAPL", price=152.0)
        
        # Emit the event
        await event_bus.emit(price_event)
        
        # Wait for async processing
        await asyncio.sleep(0.1)
        
        # Verify the position was created
        position_tracker.create_stock_position.assert_called_once_with(
            symbol="AAPL",
            quantity=100,
            stop_loss_pct=0.03,
            take_profit_pct=0.09
        )
        
        # Stop the rule engine
        await rule_engine.stop()