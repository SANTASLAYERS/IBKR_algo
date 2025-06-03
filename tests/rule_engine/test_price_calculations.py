"""
Price Calculation and Detailed BUY/SELL Tests
=============================================

Additional tests focusing on:
- Stop/target price calculations for both long and short positions
- Scale-in price adjustments
- EOD closure scenarios
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.rule.templates import create_buy_rule, create_short_rule, create_scale_in_rule
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedScaleInAction, LinkedCloseAllAction
from src.order import OrderType
from src.event.position import PositionStatus


# ===== STOP/TARGET PRICE CALCULATION TESTS =====

class TestPriceCalculations:
    """Test 6: Stop/target price calculations."""
    
    @pytest.mark.asyncio
    async def test_6_1_long_position_protective_orders(self):
        """Test 6.1: Long Position Protective Orders"""
        # Setup context with $150 current price
        context = {
            "order_manager": AsyncMock(),
            "prices": {"AAPL": 150.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        
        # Create long position with 3% stop, 8% target
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        await action.execute(context)
        
        # Check all order creation calls
        order_calls = context["order_manager"].create_order.call_args_list
        
        # Find stop loss order (should be below entry)
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        stop_call = stop_calls[0]
        assert stop_call[1]["stop_price"] == 145.50  # 150 * (1 - 0.03)
        assert stop_call[1]["quantity"] == -100  # Negative to close long position
        
        # Find take profit order (should be above entry)
        limit_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(limit_calls) == 1
        target_call = limit_calls[0]
        assert target_call[1]["limit_price"] == 162.00  # 150 * (1 + 0.08)
        assert target_call[1]["quantity"] == -100  # Negative to close long position
    
    @pytest.mark.asyncio
    async def test_6_2_short_position_protective_orders(self):
        """Test 6.2: Short Position Protective Orders"""
        # Setup context with $150 current price
        context = {
            "order_manager": AsyncMock(),
            "prices": {"AAPL": 150.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        
        # Create short position with 3% stop, 8% target
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="SELL",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        await action.execute(context)
        
        # Check all order creation calls
        order_calls = context["order_manager"].create_order.call_args_list
        
        # Find stop loss order (should be above entry for shorts)
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        stop_call = stop_calls[0]
        assert stop_call[1]["stop_price"] == 154.50  # 150 * (1 + 0.03)
        assert stop_call[1]["quantity"] == 100  # Positive to close short position
        
        # Find take profit order (should be below entry for shorts)
        limit_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(limit_calls) == 1
        target_call = limit_calls[0]
        assert target_call[1]["limit_price"] == 138.00  # 150 * (1 - 0.08)
        assert target_call[1]["quantity"] == 100  # Positive to close short position
    
    @pytest.mark.asyncio
    async def test_6_3_scale_in_price_adjustments(self):
        """Test 6.3: Scale-In Price Adjustments"""
        # Setup context with existing position
        context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "prices": {"AAPL": 155.0}  # Price moved up
        }
        
        # Mock existing profitable position
        mock_position = Mock()
        mock_position.quantity = 100
        mock_position.entry_price = 150.0
        mock_position.current_price = 155.0
        mock_position.unrealized_pnl_pct = 0.033  # 3.3% profit
        mock_position.status = PositionStatus.OPEN
        mock_position.is_long = True
        
        context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
        
        mock_order = Mock()
        mock_order.order_id = "SCALE123"
        mock_order.quantity = 50
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        context["order_manager"].cancel_order.return_value = True
        
        # Setup existing context
        context["AAPL"] = {
            "side": "BUY",
            "main_orders": ["ORDER123"],
            "stop_orders": ["STOP123"],
            "target_orders": ["TARGET123"],
            "scale_orders": [],
            "status": "active"
        }
        
        # Execute scale-in
        scale_action = LinkedScaleInAction(
            symbol="AAPL",
            scale_quantity=50,
            trigger_profit_pct=0.02
        )
        
        result = await scale_action.execute(context)
        assert result is True
        
        # Verify scale-in order placed
        scale_call = context["order_manager"].create_and_submit_order.call_args
        assert scale_call[1]["quantity"] == 50  # Positive for long scale-in
        
        # Verify stop/target orders were updated (cancelled and recreated)
        assert context["order_manager"].cancel_order.call_count >= 2  # Stop and target


# ===== EOD CLOSURE TESTS =====

class TestEODClosure:
    """Test 5: End-of-Day closure scenarios."""
    
    @pytest.mark.asyncio
    async def test_5_1_mixed_long_short_eod(self):
        """Test 5.1: Mixed Long/Short EOD"""
        # Setup context with both long and short positions
        context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock()
        }
        
        # Setup AAPL long position
        context["AAPL"] = {
            "side": "BUY",
            "main_orders": ["AAPL_MAIN"],
            "stop_orders": ["AAPL_STOP"],
            "target_orders": ["AAPL_TARGET"],
            "scale_orders": [],
            "status": "active"
        }
        
        # Setup MSFT short position
        context["MSFT"] = {
            "side": "SELL",
            "main_orders": ["MSFT_MAIN"],
            "stop_orders": ["MSFT_STOP"],
            "target_orders": ["MSFT_TARGET"],
            "scale_orders": ["MSFT_SCALE"],
            "status": "active"
        }
        
        context["order_manager"].cancel_order.return_value = True
        
        # Execute EOD closure for both symbols
        aapl_close = LinkedCloseAllAction(symbol="AAPL", reason="EOD closure")
        msft_close = LinkedCloseAllAction(symbol="MSFT", reason="EOD closure")
        
        aapl_result = await aapl_close.execute(context)
        msft_result = await msft_close.execute(context)
        
        # Verify both positions closed
        assert aapl_result is True
        assert msft_result is True
        
        # Verify all orders were cancelled
        cancel_calls = context["order_manager"].cancel_order.call_args_list
        assert len(cancel_calls) >= 6  # 3 AAPL orders + 4 MSFT orders (including scale)
        
        # Verify contexts were deleted (not just marked as closed)
        assert "AAPL" not in context
        assert "MSFT" not in context


# ===== INTEGRATION TESTS =====

class TestIntegrationScenarios:
    """Integration tests for complete trading scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_long_trade_lifecycle(self):
        """Test complete long trade from entry to exit."""
        # Setup
        context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "event_bus": AsyncMock(),
            "prices": {"AAPL": 150.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        
        # 1. Create buy rule and execute
        buy_rule = create_buy_rule(
            symbol="AAPL",
            quantity=100,
            confidence_threshold=0.80,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        # Mock prediction signal
        from src.event.api import PredictionSignalEvent
        buy_event = PredictionSignalEvent(
            symbol="AAPL",
            signal="BUY",
            confidence=0.85,
            timestamp=datetime(2024, 1, 1, 9, 30, 0)
        )
        context["event"] = buy_event
        
        # Execute buy rule
        buy_condition = await buy_rule.condition.evaluate(context)
        assert buy_condition is True
        
        buy_result = await buy_rule.action.execute(context)
        assert buy_result is True
        
        # Verify initial setup
        assert context["AAPL"]["side"] == "BUY"
        assert len(context["AAPL"]["main_orders"]) == 1
        
        # 2. Test scale-in rule execution
        scale_rule = create_scale_in_rule("AAPL", scale_quantity=50, price_offset=0.02)
        
        # Scale-in should trigger on same BUY signal with lower priority
        scale_result = await scale_rule.action.execute(context)
        assert scale_result is True
        
        # Verify scale-in order placed below current price
        scale_call = context["order_manager"].create_and_submit_order.call_args
        assert scale_call[1]["limit_price"] == 147.0  # 150 * (1 - 0.02)
        assert scale_call[1]["quantity"] == 50
    
    @pytest.mark.asyncio
    async def test_complete_short_trade_lifecycle(self):
        """Test complete short trade from entry to exit."""
        # Setup
        context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "event_bus": AsyncMock(),
            "prices": {"AAPL": 150.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        
        # 1. Create short rule and execute
        short_rule = create_short_rule(
            symbol="AAPL",
            quantity=100,
            confidence_threshold=0.80,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        # Mock prediction signal
        from src.event.api import PredictionSignalEvent
        short_event = PredictionSignalEvent(
            symbol="AAPL",
            signal="SHORT",
            confidence=0.85,
            timestamp=datetime(2024, 1, 1, 9, 30, 0)
        )
        context["event"] = short_event
        
        # Execute short rule
        short_condition = await short_rule.condition.evaluate(context)
        assert short_condition is True
        
        short_result = await short_rule.action.execute(context)
        assert short_result is True
        
        # Verify initial setup
        assert context["AAPL"]["side"] == "SELL"
        assert len(context["AAPL"]["main_orders"]) == 1
        
        # Verify short order quantity is negative
        main_call = context["order_manager"].create_and_submit_order.call_args
        assert main_call[1]["quantity"] == -100  # Negative for short
        
        # 2. Test scale-in for short position
        scale_rule = create_scale_in_rule("AAPL", scale_quantity=50, price_offset=0.02)
        
        scale_result = await scale_rule.action.execute(context)
        assert scale_result is True
        
        # Verify scale-in order placed above current price for shorts
        scale_call = context["order_manager"].create_and_submit_order.call_args
        assert scale_call[1]["limit_price"] == 153.0  # 150 * (1 + 0.02)
        assert scale_call[1]["quantity"] == -50  # Negative for additional short
    
    @pytest.mark.asyncio
    async def test_multi_symbol_portfolio(self):
        """Test multi-symbol portfolio with mixed long/short positions."""
        # Setup
        context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "event_bus": AsyncMock(),
            "prices": {"AAPL": 150.0, "MSFT": 350.0, "TSLA": 200.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        context["order_manager"].create_order.return_value = mock_order
        
        # Create rules for multiple symbols
        symbols_and_sides = [
            ("AAPL", "BUY", 100),
            ("MSFT", "SELL", 50),
            ("TSLA", "BUY", 75)
        ]
        
        from src.event.api import PredictionSignalEvent
        
        for symbol, signal, quantity in symbols_and_sides:
            # Create appropriate rule
            if signal == "BUY":
                rule = create_buy_rule(symbol, quantity=quantity)
                signal_type = "BUY"
            else:
                rule = create_short_rule(symbol, quantity=quantity)
                signal_type = "SHORT"
            
            # Create and execute event
            event = PredictionSignalEvent(
                symbol=symbol,
                signal=signal_type,
                confidence=0.85,
                timestamp=datetime(2024, 1, 1, 9, 30, 0)
            )
            context["event"] = event
            
            # Execute rule
            condition_result = await rule.condition.evaluate(context)
            assert condition_result is True
            
            action_result = await rule.action.execute(context)
            assert action_result is True
            
            # Verify context created with correct side
            expected_side = "BUY" if signal == "BUY" else "SELL"
            assert context[symbol]["side"] == expected_side
            assert context[symbol]["status"] == "active"
        
        # Verify all three positions exist independently
        assert "AAPL" in context and context["AAPL"]["side"] == "BUY"
        assert "MSFT" in context and context["MSFT"]["side"] == "SELL"
        assert "TSLA" in context and context["TSLA"]["side"] == "BUY"


# ===== EDGE CASE TESTS =====

class TestEdgeCases:
    """Additional edge case testing."""
    
    @pytest.mark.asyncio
    async def test_zero_price_handling(self):
        """Test handling of zero or invalid prices."""
        context = {
            "order_manager": AsyncMock(),
            "prices": {"AAPL": 0.0}  # Invalid price
        }
        
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="BUY",
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        # Should handle gracefully - protective orders won't be created
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        
        result = await action.execute(context)
        # Main order should still be created, but protective orders may not
        assert result is True
    
    @pytest.mark.asyncio
    async def test_negative_quantity_input(self):
        """Test handling of negative quantity inputs."""
        context = {
            "order_manager": AsyncMock(),
            "prices": {"AAPL": 150.0}
        }
        
        mock_order = Mock()
        mock_order.order_id = "ORDER123"
        context["order_manager"].create_and_submit_order.return_value = mock_order
        
        # Test BUY with negative input - should become positive
        buy_action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=-100,  # Negative input
            side="BUY"
        )
        
        await buy_action.execute(context)
        
        # Should convert to positive for BUY
        call_args = context["order_manager"].create_and_submit_order.call_args
        assert call_args[1]["quantity"] == 100  # Should be positive
        
        # Reset for next test
        context["order_manager"].reset_mock()
        del context["AAPL"]  # Clear context
        
        # Test SELL with negative input - should become negative
        sell_action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=-100,  # Negative input
            side="SELL"
        )
        
        await sell_action.execute(context)
        
        # Should remain negative for SELL
        call_args = context["order_manager"].create_and_submit_order.call_args
        assert call_args[1]["quantity"] == -100  # Should be negative


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 