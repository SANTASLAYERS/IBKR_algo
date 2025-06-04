#!/usr/bin/env python3
"""
Test ATR-Based Stops and Targets
==================================

Tests for verifying that the LinkedCreateOrderAction correctly uses ATR-based
stop losses and profit targets with 10-second bars instead of percentage-based ones.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.rule.linked_order_actions import LinkedCreateOrderAction
from src.indicators.manager import IndicatorManager
from src.minute_data.models import MinuteBar
from src.order import OrderType


class TestATRStops:
    """Test ATR-based stop losses and profit targets."""
    
    @pytest.fixture
    def mock_minute_data_manager(self):
        """Create a mock minute data manager with realistic price data."""
        manager = AsyncMock()
        
        # Create realistic 10-second bars for AAPL (simulating some volatility)
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        bars = []
        
        # Generate 100 bars with realistic volatility
        base_price = 150.0
        for i in range(100):
            timestamp = base_time + timedelta(seconds=i * 10)
            
            # Create some price movement
            price_variation = (i % 10) * 0.05  # Small variations
            volatility = 0.20 + (i % 5) * 0.05  # Varying volatility
            
            current_price = base_price + price_variation
            
            bar = MinuteBar(
                symbol="AAPL",
                timestamp=timestamp,
                open_price=current_price,
                high_price=current_price + volatility,
                low_price=current_price - volatility,
                close_price=current_price + (volatility * 0.1),  # Small net movement
                volume=1000 + i * 10
            )
            bars.append(bar)
        
        manager.get_historical_data.return_value = bars
        return manager
    
    @pytest.fixture
    def indicator_manager(self, mock_minute_data_manager):
        """Create an indicator manager with the mock data manager."""
        return IndicatorManager(mock_minute_data_manager)
    
    @pytest.fixture
    def base_context(self):
        """Create base context with all required components."""
        order_manager = AsyncMock()
        mock_order = MagicMock()
        mock_order.order_id = "ORDER123"
        order_manager.create_and_submit_order.return_value = mock_order
        order_manager.create_order.return_value = mock_order
        
        # Create a proper mock for indicator manager
        indicator_manager = AsyncMock()
        # Mock the get_atr method to return a realistic ATR value
        indicator_manager.get_atr.return_value = 1.5  # Typical ATR value
        
        return {
            "order_manager": order_manager,
            "indicator_manager": indicator_manager,
            "prices": {"AAPL": 150.0}
        }
    
    @pytest.mark.asyncio
    async def test_atr_based_long_position_stops(self, base_context):
        """Test ATR-based stops for long positions."""
        # Create action with ATR multipliers
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,  # ATR * 6 for stop loss
            atr_target_multiplier=3.0  # ATR * 3 for profit target
        )
        
        # Execute the action
        result = await action.execute(base_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify indicator manager was called to get ATR
        base_context["indicator_manager"].get_atr.assert_called_once_with(
            symbol="AAPL",
            period=14,
            days=1,
            bar_size="10 secs"
        )
        
        # Verify orders were created
        order_calls = base_context["order_manager"].create_order.call_args_list
        
        # Should have created stop and target orders
        assert len(order_calls) >= 2
        
        # Find stop loss order
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        
        stop_call = stop_calls[0]
        stop_price = stop_call[1]["stop_price"]
        stop_quantity = stop_call[1]["quantity"]
        
        # Verify stop loss is below entry price and uses ATR
        assert stop_price < 150.0  # Below entry price for long position
        assert stop_quantity == -100  # Negative to close long position
        
        # Find profit target order
        target_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        
        target_call = target_calls[0]
        target_price = target_call[1]["limit_price"]
        target_quantity = target_call[1]["quantity"]
        
        # Verify target is above entry price and uses ATR
        assert target_price > 150.0  # Above entry price for long position
        assert target_quantity == -100  # Negative to close long position
        
        # Verify ATR-based distances
        # The exact distances depend on the calculated ATR, but we can check they're reasonable
        stop_distance = 150.0 - stop_price
        target_distance = target_price - 150.0
        
        # Stop distance should be larger than target (6x vs 3x ATR)
        assert stop_distance > target_distance
        
        print(f"Long position - Entry: $150.00")
        print(f"Stop loss: ${stop_price:.2f} (distance: ${stop_distance:.2f})")
        print(f"Profit target: ${target_price:.2f} (distance: ${target_distance:.2f})")
        print(f"Risk/Reward ratio: {stop_distance/target_distance:.2f}:1")
    
    @pytest.mark.asyncio
    async def test_atr_based_short_position_stops(self, base_context):
        """Test ATR-based stops for short positions."""
        # Create short action with ATR multipliers
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="SELL",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0
        )
        
        # Execute the action
        result = await action.execute(base_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify orders were created
        order_calls = base_context["order_manager"].create_order.call_args_list
        
        # Find stop loss order
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        
        stop_call = stop_calls[0]
        stop_price = stop_call[1]["stop_price"]
        stop_quantity = stop_call[1]["quantity"]
        
        # Verify stop loss is above entry price for short position
        assert stop_price > 150.0  # Above entry price for short position
        assert stop_quantity == 100  # Positive to close short position
        
        # Find profit target order
        target_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        
        target_call = target_calls[0]
        target_price = target_call[1]["limit_price"]
        target_quantity = target_call[1]["quantity"]
        
        # Verify target is below entry price for short position
        assert target_price < 150.0  # Below entry price for short position
        assert target_quantity == 100  # Positive to close short position
        
        # Verify ATR-based distances
        stop_distance = stop_price - 150.0
        target_distance = 150.0 - target_price
        
        # Stop distance should be larger than target (6x vs 3x ATR)
        assert stop_distance > target_distance
        
        print(f"Short position - Entry: $150.00")
        print(f"Stop loss: ${stop_price:.2f} (distance: ${stop_distance:.2f})")
        print(f"Profit target: ${target_price:.2f} (distance: ${target_distance:.2f})")
        print(f"Risk/Reward ratio: {stop_distance/target_distance:.2f}:1")
    
    @pytest.mark.asyncio
    async def test_atr_fallback_to_percentage(self, base_context):
        """Test fallback to percentage-based stops when ATR fails."""
        # Mock indicator manager to return None (ATR calculation failed)
        base_context["indicator_manager"].get_atr.return_value = None
        
        # Create action with both ATR and percentage parameters
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0,
            stop_loss_pct=0.03,  # 3% fallback
            take_profit_pct=0.08  # 8% fallback
        )
        
        # Execute the action
        result = await action.execute(base_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify indicator manager was called but failed
        base_context["indicator_manager"].get_atr.assert_called_once()
        
        # Verify orders were created using percentage fallback
        order_calls = base_context["order_manager"].create_order.call_args_list
        
        # Find stop loss order
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        
        stop_call = stop_calls[0]
        stop_price = stop_call[1]["stop_price"]
        
        # Should use percentage calculation: 150 * (1 - 0.03) = 145.50
        assert stop_price == 145.50
        
        # Find profit target order
        target_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        
        target_call = target_calls[0]
        target_price = target_call[1]["limit_price"]
        
        # Should use percentage calculation: 150 * (1 + 0.08) = 162.00
        assert target_price == 162.00
        
        print("ATR calculation failed, successfully fell back to percentage-based stops")
        print(f"Stop loss: ${stop_price:.2f} (3%)")
        print(f"Profit target: ${target_price:.2f} (8%)")
    
    @pytest.mark.asyncio
    async def test_no_indicator_manager_fallback(self, base_context):
        """Test behavior when no indicator manager is available."""
        # Remove indicator manager from context
        del base_context["indicator_manager"]
        
        # Create action with ATR multipliers and percentage fallback
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=100,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0,
            stop_loss_pct=0.03,
            take_profit_pct=0.08
        )
        
        # Execute the action
        result = await action.execute(base_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify orders were created using percentage fallback
        order_calls = base_context["order_manager"].create_order.call_args_list
        
        # Should fall back to percentage-based calculations
        stop_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        assert stop_calls[0][1]["stop_price"] == 145.50  # 150 * 0.97
        
        target_calls = [call for call in order_calls if call[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        assert target_calls[0][1]["limit_price"] == 162.00  # 150 * 1.08
        
        print("No indicator manager available, successfully fell back to percentage-based stops")


if __name__ == "__main__":
    # Run a simple test
    async def main():
        print("Testing ATR-based stops...")
        
        # Create mock data similar to the test fixture
        mock_manager = AsyncMock()
        
        # Create realistic bars with some volatility
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        bars = []
        
        for i in range(50):
            timestamp = base_time + timedelta(seconds=i * 10)
            
            # Create realistic OHLC data with ATR around 1.5-2.0
            base_price = 150.0
            volatility = 1.8  # Typical ATR value
            
            bar = MinuteBar(
                symbol="AAPL",
                timestamp=timestamp,
                open_price=base_price,
                high_price=base_price + volatility,
                low_price=base_price - volatility,
                close_price=base_price + 0.1,
                volume=1000
            )
            bars.append(bar)
        
        mock_manager.get_historical_data.return_value = bars
        
        # Test ATR calculation
        indicator_manager = IndicatorManager(mock_manager)
        atr = await indicator_manager.get_atr("AAPL", bar_size="10 secs", period=14)
        
        print(f"Calculated ATR: {atr:.4f}")
        print(f"Stop distance (ATR * 6): {atr * 6:.2f}")
        print(f"Target distance (ATR * 3): {atr * 3:.2f}")
        print(f"Risk/Reward ratio: {6/3:.1f}:1")
        print("✅ ATR calculation test completed successfully!")
    
    asyncio.run(main()) 