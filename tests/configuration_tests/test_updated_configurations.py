#!/usr/bin/env python3
"""
Test Updated Configurations
============================

Tests for verifying the updated system configurations:
1. Confidence threshold set to 0.5
2. Cooldown time set to 3 minutes
3. New ticker list: CVNA, UVXY, SOXL, SOXS, TQQQ, SQQQ, GLD, SLV
4. Cooldown reset when stop loss is hit
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.event.order import FillEvent
from src.rule.engine import RuleEngine
from src.rule.linked_order_actions import CooldownResetManager
from src.rule.base import Rule
from src.rule.condition import EventCondition
from src.rule.action import CreateOrderAction
from main_trading_app import TradingApplication


class TestUpdatedConfigurations:
    """Test updated system configurations."""
    
    @pytest.fixture
    def trading_app(self):
        """Create trading application for testing."""
        app = TradingApplication()
        # Mock the TWS connection to avoid real connection
        app.tws_connection = AsyncMock()
        app.tws_connection.connect.return_value = True
        return app
    
    def test_confidence_threshold_updated(self, trading_app):
        """Test that confidence threshold is set to 0.5 for all tickers."""
        # Get the strategies from setup_strategies method
        trading_app.rule_engine = MagicMock()
        trading_app.rule_engine.register_rule = MagicMock()
        
        # Call setup_strategies
        trading_app.setup_strategies()
        
        # Check that rules were registered
        assert trading_app.rule_engine.register_rule.called
        
        # Get all registered rule calls
        rule_calls = trading_app.rule_engine.register_rule.call_args_list
        
        # Filter for buy rules (ignore EOD rules)
        buy_rules = []
        for call in rule_calls:
            rule = call[0][0]
            if "buy_rule" in rule.rule_id:
                buy_rules.append(rule)
        
        # Verify confidence thresholds
        for rule in buy_rules:
            # Extract condition from the rule
            condition = rule.condition
            # Confidence threshold should be 0.5
            assert hasattr(condition, 'field_conditions')
            confidence_check = condition.field_conditions.get('confidence')
            if callable(confidence_check):
                # Test with 0.5 - should return True
                assert confidence_check(0.5) == True
                # Test with 0.49 - should return False  
                assert confidence_check(0.49) == False
    
    def test_cooldown_time_updated(self, trading_app):
        """Test that cooldown time is set to 3 minutes for all tickers."""
        trading_app.rule_engine = MagicMock()
        trading_app.rule_engine.register_rule = MagicMock()
        
        trading_app.setup_strategies()
        
        rule_calls = trading_app.rule_engine.register_rule.call_args_list
        
        # Filter for buy/sell rules (ignore EOD rules)
        trading_rules = []
        for call in rule_calls:
            rule = call[0][0]
            if "buy_rule" in rule.rule_id or "sell_rule" in rule.rule_id:
                trading_rules.append(rule)
        
        # Check cooldown for trading rules (should be 180 seconds = 3 minutes)
        for rule in trading_rules:
            assert rule.cooldown_seconds == 180  # 3 minutes
    
    def test_new_ticker_list(self, trading_app):
        """Test that the new ticker list is being used."""
        expected_tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]
        
        trading_app.rule_engine = MagicMock()
        trading_app.rule_engine.register_rule = MagicMock()
        
        trading_app.setup_strategies()
        
        rule_calls = trading_app.rule_engine.register_rule.call_args_list
        
        # Get unique tickers from buy/sell rule IDs
        registered_tickers = set()
        for call in rule_calls:
            rule = call[0][0]
            rule_id = rule.rule_id
            # Extract ticker from rule ID (format: "ticker_buy_rule" or "ticker_sell_rule")
            if "buy_rule" in rule_id or "sell_rule" in rule_id:
                ticker = rule_id.split('_')[0].upper()
                registered_tickers.add(ticker)
        
        # Verify all expected tickers are present
        assert registered_tickers == set(expected_tickers)
    
    @pytest.mark.asyncio
    async def test_cooldown_reset_functionality(self):
        """Test that cooldown reset works when stop loss is hit."""
        # Setup components
        event_bus = EventBus()
        rule_engine = RuleEngine(event_bus)
        
        # Create a test rule with cooldown
        test_rule = Rule(
            rule_id="test_cvna_buy_rule",
            name="Test CVNA Buy Rule",
            condition=EventCondition(
                event_type=PredictionSignalEvent,
                field_conditions={"symbol": "CVNA", "signal": "BUY"}
            ),
            action=CreateOrderAction(symbol="CVNA", quantity=100),
            cooldown_seconds=180  # 3 minutes
        )
        
        # Register rule and set it as executed (on cooldown)
        rule_engine.register_rule(test_rule)
        test_rule.last_execution_time = datetime.now() - timedelta(seconds=60)  # 1 minute ago
        
        # Verify rule is on cooldown
        assert test_rule.last_execution_time is not None
        
        # Setup cooldown reset manager
        cooldown_manager = CooldownResetManager(rule_engine, event_bus)
        await cooldown_manager.initialize()
        
        # Set up context to simulate a position with stop orders
        rule_engine.context["CVNA"] = {
            "side": "BUY",
            "stop_orders": ["12345"],  # Order ID that will be "filled"
            "target_orders": ["12346"]
        }
        
        # Create and emit a fill event for the stop loss order
        fill_event = FillEvent(
            symbol="CVNA",
            order_id="12345",  # This matches the stop order ID
            quantity=100,
            fill_price=95.0,
            timestamp=datetime.now()
        )
        
        await event_bus.emit(fill_event)
        
        # Give the event handler time to process
        await asyncio.sleep(0.1)
        
        # Verify that the rule's cooldown was reset
        assert test_rule.last_execution_time is None
    
    @pytest.mark.asyncio
    async def test_cooldown_not_reset_for_profit_target(self):
        """Test that cooldown is NOT reset when profit target is hit."""
        # Setup components
        event_bus = EventBus()
        rule_engine = RuleEngine(event_bus)
        
        # Create a test rule with cooldown
        test_rule = Rule(
            rule_id="test_uvxy_buy_rule",
            name="Test UVXY Buy Rule",
            condition=EventCondition(
                event_type=PredictionSignalEvent,
                field_conditions={"symbol": "UVXY", "signal": "BUY"}
            ),
            action=CreateOrderAction(symbol="UVXY", quantity=100),
            cooldown_seconds=180
        )
        
        # Register rule and set it as executed (on cooldown)
        rule_engine.register_rule(test_rule)
        original_execution_time = datetime.now() - timedelta(seconds=60)
        test_rule.last_execution_time = original_execution_time
        
        # Setup cooldown reset manager
        cooldown_manager = CooldownResetManager(rule_engine, event_bus)
        await cooldown_manager.initialize()
        
        # Set up context to simulate a position with stop and target orders
        rule_engine.context["UVXY"] = {
            "side": "BUY",
            "stop_orders": ["12347"],
            "target_orders": ["12348"]  # Order ID that will be "filled"
        }
        
        # Create and emit a fill event for the profit target order (not stop loss)
        fill_event = FillEvent(
            symbol="UVXY",
            order_id="12348",  # This matches the target order ID
            quantity=100,
            fill_price=108.0,
            timestamp=datetime.now()
        )
        
        await event_bus.emit(fill_event)
        
        # Give the event handler time to process
        await asyncio.sleep(0.1)
        
        # Verify that the rule's cooldown was NOT reset (still has original time)
        assert test_rule.last_execution_time == original_execution_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 