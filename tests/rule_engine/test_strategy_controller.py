#!/usr/bin/env python3
"""
Integration tests for the Strategy Controller.

These tests verify the integration between the Rule Engine,
ATR Calculator, and other components of the system.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, List, Any, Optional

# Import the modules that don't exist yet
from src.strategy.controller import StrategyController
from src.indicators.manager import IndicatorManager
from src.indicators.atr import ATRCalculator
from src.rule.engine import RuleEngine
from src.rule.base import Rule, Condition, Action
from src.event.bus import EventBus
from src.event.market import PriceEvent
from src.position.tracker import PositionTracker
from src.order.manager import OrderManager
from src.minute_data.models import MinuteBar


class MockMinuteDataManager:
    """Mock for the minute data manager."""
    
    async def get_historical_data(self, symbol, start_date=None, end_date=None, days=None):
        """Return mock historical data."""
        base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        data = []
        
        # Generate 20 bars of mock data
        for i in range(20):
            bar = MinuteBar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=100.0 + i * 0.1,
                high_price=105.0 + i * 0.1,
                low_price=95.0 + i * 0.1,
                close_price=102.0 + i * 0.1,
                volume=1000 + i * 100,
                symbol=symbol
            )
            data.append(bar)
            
        return data


class TestCondition(Condition):
    """Test condition for rule testing."""
    
    def __init__(self, should_match=True):
        self.should_match = should_match
        self.last_context = None
        
    async def evaluate(self, context):
        self.last_context = context
        return self.should_match


class TestAction(Action):
    """Test action for rule testing."""
    
    def __init__(self):
        self.executed = False
        self.last_context = None
        
    async def execute(self, context):
        self.executed = True
        self.last_context = context
        return True


@pytest.fixture
def event_bus():
    """Create event bus fixture."""
    return EventBus()


@pytest.fixture
def rule_engine(event_bus):
    """Create rule engine fixture."""
    return RuleEngine(event_bus)


@pytest.fixture
def minute_data_manager():
    """Create mock minute data manager fixture."""
    return MockMinuteDataManager()


@pytest.fixture
def indicator_manager(minute_data_manager):
    """Create indicator manager fixture."""
    return IndicatorManager(minute_data_manager)


@pytest.fixture
def position_tracker():
    """Create mock position tracker fixture."""
    return MagicMock(spec=PositionTracker)


@pytest.fixture
def order_manager():
    """Create mock order manager fixture."""
    return MagicMock(spec=OrderManager)


@pytest.fixture
def strategy_controller(
    event_bus, rule_engine, indicator_manager, position_tracker, order_manager
):
    """Create strategy controller fixture."""
    controller = StrategyController(
        event_bus=event_bus,
        rule_engine=rule_engine,
        indicator_manager=indicator_manager,
        position_tracker=position_tracker,
        order_manager=order_manager
    )
    return controller


@pytest.mark.asyncio
async def test_strategy_controller_initialization(strategy_controller):
    """Test that the strategy controller initializes properly."""
    # Initialize the controller
    await strategy_controller.initialize()
    
    # Verify rule engine context contains required components
    assert strategy_controller.rule_engine.context.get("position_tracker") is not None
    assert strategy_controller.rule_engine.context.get("order_manager") is not None
    assert strategy_controller.rule_engine.context.get("indicators") is not None


@pytest.mark.asyncio
async def test_strategy_controller_atr_update(strategy_controller):
    """Test that the strategy controller updates ATR values."""
    # Initialize the controller
    await strategy_controller.initialize()
    
    # Request ATR calculation for a symbol
    atr_value = await strategy_controller.get_atr("AAPL")
    
    # Verify ATR is a positive float
    assert atr_value > 0
    assert isinstance(atr_value, float)
    
    # Verify ATR is in the rule engine context
    indicators = strategy_controller.rule_engine.context.get("indicators", {})
    assert "AAPL" in indicators
    assert "ATR" in indicators["AAPL"]
    assert indicators["AAPL"]["ATR"] == atr_value


@pytest.mark.asyncio
async def test_strategy_controller_rule_integration(strategy_controller):
    """Test integration of rules with the strategy controller."""
    # Create test condition and action
    test_condition = TestCondition(should_match=True)
    test_action = TestAction()
    
    # Create rule
    rule = Rule(
        rule_id="test_rule",
        name="Test Rule",
        description="Rule for testing strategy controller integration",
        condition=test_condition,
        action=test_action
    )
    
    # Register rule with rule engine
    strategy_controller.rule_engine.register_rule(rule)
    
    # Initialize the controller
    await strategy_controller.initialize()
    
    # Calculate ATR for a symbol
    atr_value = await strategy_controller.get_atr("AAPL")
    
    # Evaluate rules manually to trigger our test rule
    await strategy_controller.rule_engine._evaluate_all_rules()
    
    # Verify action was executed
    assert test_action.executed
    
    # Verify context contained ATR value
    assert test_action.last_context is not None
    indicators = test_action.last_context.get("indicators", {})
    assert "AAPL" in indicators
    assert "ATR" in indicators["AAPL"]
    assert indicators["AAPL"]["ATR"] == atr_value


@pytest.mark.asyncio
async def test_strategy_controller_price_event_handling(strategy_controller):
    """Test that the strategy controller handles price events."""
    # Create a test condition that checks for ATR in context
    class ATRCondition(Condition):
        async def evaluate(self, context):
            indicators = context.get("indicators", {})
            symbol_indicators = indicators.get("AAPL", {})
            return "ATR" in symbol_indicators
    
    # Create test action
    test_action = TestAction()
    
    # Create rule
    rule = Rule(
        rule_id="atr_rule",
        name="ATR Rule",
        description="Rule that checks for ATR in context",
        condition=ATRCondition(),
        action=test_action
    )
    
    # Register rule with rule engine
    strategy_controller.rule_engine.register_rule(rule)
    
    # Initialize the controller
    await strategy_controller.initialize()
    
    # Create a price event
    price_event = PriceEvent(
        symbol="AAPL",
        price=150.0,
        change=1.0,
        change_percent=0.01
    )
    
    # Emit the price event
    await strategy_controller.event_bus.emit(price_event)
    
    # Wait a bit for async processing
    await asyncio.sleep(0.1)
    
    # Verify price was updated in context
    prices = strategy_controller.rule_engine.context.get("prices", {})
    assert "AAPL" in prices
    assert prices["AAPL"] == 150.0
    
    # Now manually calculate ATR (as this would typically be done on a schedule)
    atr_value = await strategy_controller.get_atr("AAPL")
    
    # Verify ATR was calculated
    indicators = strategy_controller.rule_engine.context.get("indicators", {})
    assert "AAPL" in indicators
    assert "ATR" in indicators["AAPL"]
    
    # Manually trigger rule evaluation to verify action executes
    await strategy_controller.rule_engine._evaluate_all_rules()
    
    # Verify action was executed
    assert test_action.executed