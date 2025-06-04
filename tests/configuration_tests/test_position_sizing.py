#!/usr/bin/env python3
"""
Test Position Sizing System
============================

Tests for verifying that the new price service and position sizer
correctly calculate position sizes based on $10K allocations.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
import logging

from src.price.service import PriceService
from src.position.sizer import PositionSizer
from src.rule.linked_order_actions import LinkedCreateOrderAction
from src.order import OrderType


class TestPositionSizing:
    """Test the complete position sizing system."""
    
    @pytest.fixture
    def mock_tws_connection(self):
        """Create a mock TWS connection."""
        connection = MagicMock()
        connection.is_connected.return_value = True
        connection.reqMktData = MagicMock()
        connection.cancelMktData = MagicMock()
        
        # Mock the callback methods that will be temporarily overridden
        connection.tickPrice = MagicMock()
        connection.error = MagicMock()
        
        return connection
    
    @pytest.fixture
    def price_service(self, mock_tws_connection):
        """Create a price service with mock TWS connection."""
        return PriceService(mock_tws_connection)
    
    @pytest.fixture
    def position_sizer(self):
        """Create a position sizer."""
        return PositionSizer(min_shares=1, max_shares=10000)
    
    @pytest.fixture
    def trading_context(self, price_service, position_sizer):
        """Create a complete trading context with all required services."""
        order_manager = AsyncMock()
        mock_order = MagicMock()
        mock_order.order_id = "ORDER123"
        order_manager.create_and_submit_order.return_value = mock_order
        order_manager.create_order.return_value = mock_order
        
        # Create a properly mocked price service
        mock_price_service = MagicMock()
        mock_price_service.get_price = AsyncMock()
        
        return {
            "order_manager": order_manager,
            "price_service": mock_price_service,
            "position_sizer": position_sizer,
            "indicator_manager": AsyncMock(),  # Mock for ATR calculations
            "prices": {}
        }
    
    def test_position_sizer_basic_calculations(self, position_sizer):
        """Test basic position size calculations."""
        # Test with $10K allocation and $100 stock price
        shares = position_sizer.calculate_shares(
            allocation=10000,
            price=100.0,
            side="BUY"
        )
        assert shares == 100  # 10000 / 100 = 100 shares
        
        # Test with $10K allocation and $50 stock price
        shares = position_sizer.calculate_shares(
            allocation=10000,
            price=50.0,
            side="BUY"
        )
        assert shares == 200  # 10000 / 50 = 200 shares
        
        # Test with expensive stock ($500 per share)
        shares = position_sizer.calculate_shares(
            allocation=10000,
            price=500.0,
            side="BUY"
        )
        assert shares == 20  # 10000 / 500 = 20 shares
        
        # Test with very expensive stock ($15000 per share) - should get minimum
        shares = position_sizer.calculate_shares(
            allocation=10000,
            price=15000.0,
            side="BUY"
        )
        assert shares is None  # Less than 1 share, should return None
    
    def test_position_sizer_edge_cases(self, position_sizer):
        """Test edge cases for position sizing."""
        # Test with invalid price
        shares = position_sizer.calculate_shares(10000, 0, "BUY")
        assert shares is None
        
        shares = position_sizer.calculate_shares(10000, -10, "BUY")
        assert shares is None
        
        # Test with invalid allocation
        shares = position_sizer.calculate_shares(0, 100, "BUY")
        assert shares is None
        
        shares = position_sizer.calculate_shares(-5000, 100, "BUY")
        assert shares is None
        
        # Test maximum share limit
        shares = position_sizer.calculate_shares(
            allocation=100000,  # Large allocation
            price=5.0,          # Cheap stock  
            side="BUY"
        )
        # Should be limited to max_shares (10000)
        assert shares == 10000
    
    def test_allocation_efficiency(self, position_sizer):
        """Test allocation efficiency calculations."""
        # Perfect efficiency case
        efficiency = position_sizer.calculate_allocation_efficiency(
            shares=100, 
            price=100.0, 
            target_allocation=10000
        )
        assert efficiency == 100.0
        
        # Less than perfect efficiency due to rounding
        efficiency = position_sizer.calculate_allocation_efficiency(
            shares=66,    # 66 shares @ $150 = $9900
            price=150.0, 
            target_allocation=10000
        )
        assert efficiency == 99.0  # 9900 / 10000 = 99%
        
        # Get detailed summary
        summary = position_sizer.get_allocation_summary(
            shares=66,
            price=150.0,
            allocation=10000
        )
        
        assert summary["shares"] == 66
        assert summary["price"] == 150.0
        assert summary["target_allocation"] == 10000
        assert summary["actual_cost"] == 9900
        assert summary["unused_cash"] == 100
        assert summary["efficiency_pct"] == 99.0
    
    @pytest.mark.asyncio
    async def test_linked_order_action_with_allocation(self, trading_context):
        """Test LinkedCreateOrderAction with dollar allocation."""
        # Mock price service to return a realistic price
        trading_context["price_service"].get_price = AsyncMock(return_value=75.0)
        
        # Create action with $10K allocation
        action = LinkedCreateOrderAction(
            symbol="UVXY",
            quantity=10000,  # This will be treated as allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=False  # Simplify test
        )
        
        # Execute the action
        result = await action.execute(trading_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify price was fetched
        trading_context["price_service"].get_price.assert_called_once_with("UVXY")
        
        # Verify order was created with correct quantity
        order_calls = trading_context["order_manager"].create_and_submit_order.call_args_list
        assert len(order_calls) == 1
        
        call_args = order_calls[0][1]
        quantity = call_args["quantity"]
        
        # Should be 133 shares (10000 / 75 = 133.33, rounded down to 133)
        assert quantity == 133
        assert call_args["symbol"] == "UVXY"
    
    @pytest.mark.asyncio 
    async def test_linked_order_action_with_fixed_shares(self, trading_context):
        """Test LinkedCreateOrderAction with fixed share quantity."""
        # Create action with fixed shares (< 1000)
        action = LinkedCreateOrderAction(
            symbol="AAPL",
            quantity=50,  # This will be treated as fixed shares
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=False
        )
        
        # Execute the action
        result = await action.execute(trading_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify price service was NOT called (fixed shares)
        trading_context["price_service"].get_price.assert_not_called()
        
        # Verify order was created with exact quantity
        order_calls = trading_context["order_manager"].create_and_submit_order.call_args_list
        assert len(order_calls) == 1
        
        call_args = order_calls[0][1]
        quantity = call_args["quantity"]
        
        # Should be exactly 50 shares
        assert quantity == 50
    
    @pytest.mark.asyncio
    async def test_price_service_unavailable_fallback(self, trading_context):
        """Test fallback when price service is unavailable."""
        # Remove price service from context
        del trading_context["price_service"]
        
        # Create action with allocation
        action = LinkedCreateOrderAction(
            symbol="TSLA",
            quantity=10000,  # Allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=False
        )
        
        # Execute the action
        result = await action.execute(trading_context)
        
        # Should still succeed by treating allocation as shares
        assert result is True
        
        # Should use allocation as share count
        order_calls = trading_context["order_manager"].create_and_submit_order.call_args_list
        assert len(order_calls) == 1
        assert order_calls[0][1]["quantity"] == 10000
    
    @pytest.mark.asyncio
    async def test_price_fetch_failure(self, trading_context):
        """Test handling when price fetch fails."""
        # Mock price service to return None (price fetch failed)
        trading_context["price_service"].get_price = AsyncMock(return_value=None)
        
        # Create action with allocation
        action = LinkedCreateOrderAction(
            symbol="BADTICKER",
            quantity=10000,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=False
        )
        
        # Execute the action
        result = await action.execute(trading_context)
        
        # Should fail gracefully
        assert result is False
        
        # No orders should be created
        trading_context["order_manager"].create_and_submit_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_short_position_sizing(self, trading_context):
        """Test position sizing for short positions."""
        # Mock price service
        trading_context["price_service"].get_price = AsyncMock(return_value=200.0)
        
        # Create short action
        action = LinkedCreateOrderAction(
            symbol="SOXL",
            quantity=10000,  # $10K allocation
            side="SELL",     # Short position
            order_type=OrderType.MARKET,
            auto_create_stops=False
        )
        
        # Execute the action
        result = await action.execute(trading_context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify order was created with correct negative quantity for short
        order_calls = trading_context["order_manager"].create_and_submit_order.call_args_list
        assert len(order_calls) == 1
        
        call_args = order_calls[0][1]
        quantity = call_args["quantity"]
        
        # Should be -50 shares (10000 / 200 = 50, negative for short)
        assert quantity == -50


if __name__ == "__main__":
    # Run a simple manual test
    # Setup basic logging to see the position sizer output
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    async def main():
        print("Testing position sizing system...")
        
        # Test position sizer directly
        sizer = PositionSizer()
        
        test_cases = [
            (10000, 100.0, "AAPL"),    # $10K @ $100 = 100 shares
            (10000, 75.0, "UVXY"),     # $10K @ $75 = 133 shares  
            (10000, 500.0, "BRK.A"),   # $10K @ $500 = 20 shares
            (10000, 15.50, "SOXL"),    # $10K @ $15.50 = 645 shares
        ]
        
        print("\nPosition Sizing Results:")
        print("="*60)
        
        for allocation, price, symbol in test_cases:
            shares = sizer.calculate_shares(allocation, price, "BUY")
            if shares is not None:
                actual_cost = shares * price
                efficiency = (actual_cost / allocation * 100)
                print(f"{symbol:8s}: {shares:4d} shares @ ${price:7.2f} = ${actual_cost:8.2f} ({efficiency:5.1f}%)")
            else:
                print(f"{symbol:8s}: Cannot calculate shares for ${allocation:.2f} @ ${price:.2f}")
        
        print("="*60)
        print("✅ Position sizing test completed!")
    
    asyncio.run(main()) 