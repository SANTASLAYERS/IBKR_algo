#!/usr/bin/env python3
"""
Unit Test for UnifiedFillManager Double Down Scenario
=====================================================

This test specifically verifies the fix for the set concatenation error
and ensures protective orders are updated correctly after double down fills.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rule.unified_fill_manager import UnifiedFillManager
from src.event.bus import EventBus
from src.event.order import FillEvent
from src.position.position_manager import PositionManager
from src.order.base import OrderType, OrderStatus, Order


class TestUnifiedFillManagerDoubleDown:
    """Test the specific double down scenario that was failing."""
    
    @pytest.fixture
    def setup(self):
        """Setup test environment."""
        # Create event bus
        event_bus = EventBus()
        
        # Create mock context
        order_manager = AsyncMock()
        position_tracker = AsyncMock()
        
        context = {
            "order_manager": order_manager,
            "position_tracker": position_tracker
        }
        
        # Create manager
        manager = UnifiedFillManager(context, event_bus)
        
        # Setup PositionManager singleton
        position_manager = PositionManager()
        position_manager.clear_all()  # Clear any existing data
        
        return {
            "manager": manager,
            "event_bus": event_bus,
            "order_manager": order_manager,
            "position_tracker": position_tracker,
            "position_manager": position_manager,
            "context": context
        }
    
    @pytest.mark.asyncio
    async def test_double_down_fill_with_set_union(self, setup):
        """Test that double down fills work with the set union fix."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        event_bus = setup["event_bus"]
        
        # Initialize manager to subscribe to events
        await manager.initialize()
        
        # Setup position with 5000 shares
        position_manager.open_position("SLV", "BUY")
        position = position_manager.get_position("SLV")
        
        # Use sets for order collections (this was the issue)
        position.main_orders = {"main_123"}
        position.doubledown_orders = {"dd_456"}
        position.stop_orders = {"stop_789"}
        position.target_orders = {"target_012"}
        position.current_quantity = 5000
        
        # Mock orders - initial position of 5000 shares
        main_order = Mock()
        main_order.order_id = "main_123"
        main_order.quantity = 5000
        main_order.filled_quantity = 5000
        
        # Double down order for another 5000 shares
        dd_order = Mock()
        dd_order.order_id = "dd_456"
        dd_order.quantity = 5000
        dd_order.filled_quantity = 5000
        dd_order.status = Mock(value="filled")
        
        # Protective orders initially for -5000 shares
        stop_order = Mock()
        stop_order.order_id = "stop_789"
        stop_order.quantity = -5000
        stop_order.filled_quantity = 0
        stop_order.stop_price = 32.00
        stop_order.status = Mock(value="working")
        
        target_order = Mock()
        target_order.order_id = "target_012"
        target_order.quantity = -5000
        target_order.filled_quantity = 0
        target_order.limit_price = 34.00
        target_order.status = Mock(value="working")
        
        # Setup order manager mock
        order_manager.get_order.side_effect = lambda order_id: {
            "main_123": main_order,
            "dd_456": dd_order,
            "stop_789": stop_order,
            "target_012": target_order
        }.get(order_id)
        
        # Mock order creation for updated protective orders
        new_stop = Mock()
        new_stop.order_id = "new_stop_123"
        new_target = Mock()
        new_target.order_id = "new_target_456"
        
        order_manager.create_order.side_effect = [new_stop, new_target]
        
        # Create double down fill event
        fill_event = FillEvent(
            symbol="SLV",
            order_id="dd_456",
            fill_quantity=5000,
            fill_price=32.50,
            timestamp=datetime.now()
        )
        
        # Process fill through event bus (simulates real flow)
        await event_bus.emit(fill_event)
        
        # Give async processing time to complete
        await asyncio.sleep(0.1)
        
        # Verify protective orders were cancelled
        assert order_manager.cancel_order.call_count == 2
        order_manager.cancel_order.assert_any_call("stop_789", "Updating quantity to -10000.0")
        order_manager.cancel_order.assert_any_call("target_012", "Updating quantity to -10000.0")
        
        # Verify new protective orders created with updated quantity (10000 shares)
        assert order_manager.create_order.call_count == 2
        
        # Check stop order creation
        stop_call = order_manager.create_order.call_args_list[0]
        assert stop_call.kwargs["symbol"] == "SLV"
        assert stop_call.kwargs["quantity"] == -10000  # Updated to total position
        assert stop_call.kwargs["order_type"] == OrderType.STOP
        assert stop_call.kwargs["stop_price"] == 32.00
        
        # Check target order creation
        target_call = order_manager.create_order.call_args_list[1]
        assert target_call.kwargs["symbol"] == "SLV"
        assert target_call.kwargs["quantity"] == -10000  # Updated to total position
        assert target_call.kwargs["order_type"] == OrderType.LIMIT
        assert target_call.kwargs["limit_price"] == 34.00
        
        print("✅ Double down fill test PASSED - protective orders updated from -5000 to -10000")
    
    @pytest.mark.asyncio
    async def test_position_calculation_with_sets(self, setup):
        """Test that position calculation works correctly with set union."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        
        # Setup position
        position_manager.open_position("SLV", "BUY")
        position = position_manager.get_position("SLV")
        
        # Use sets (this tests the fix)
        position.main_orders = {"main_1", "main_2"}
        position.doubledown_orders = {"dd_1"}
        position.stop_orders = {"stop_1", "stop_2"}
        position.target_orders = {"target_1", "target_2"}
        
        # Mock orders
        orders = {
            "main_1": Mock(quantity=3000, filled_quantity=3000),
            "main_2": Mock(quantity=2000, filled_quantity=2000),
            "dd_1": Mock(quantity=5000, filled_quantity=5000),
            "stop_1": Mock(quantity=-5000, filled_quantity=-1000),  # Partial fill
            "stop_2": Mock(quantity=-5000, filled_quantity=0),
            "target_1": Mock(quantity=-5000, filled_quantity=0),
            "target_2": Mock(quantity=-5000, filled_quantity=0)
        }
        
        order_manager.get_order.side_effect = lambda order_id: orders.get(order_id)
        
        # Calculate position
        position_size = await manager._calculate_current_position_size("SLV")
        
        # Should be: 3000 + 2000 + 5000 - 1000 = 9000
        assert position_size == 9000
        print(f"✅ Position calculation test PASSED - calculated position: {position_size}")
    
    @pytest.mark.asyncio
    async def test_error_handling_with_missing_position(self, setup):
        """Test that manager handles missing position gracefully."""
        manager = setup["manager"]
        event_bus = setup["event_bus"]
        
        await manager.initialize()
        
        # Create fill event for non-existent position
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="fake_123",
            fill_quantity=100,
            fill_price=150.00,
            timestamp=datetime.now()
        )
        
        # Should not raise exception
        await event_bus.emit(fill_event)
        await asyncio.sleep(0.1)
        
        print("✅ Error handling test PASSED - no exception on missing position")


def run_tests():
    """Run the tests."""
    test = TestUnifiedFillManagerDoubleDown()
    
    # Create mock setup
    class MockSetup:
        pass
    
    setup_obj = MockSetup()
    
    # Run each test
    print("\n" + "="*80)
    print("UNIFIED FILL MANAGER DOUBLE DOWN TESTS")
    print("="*80)
    
    # Get event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test 1
        print("\nTest 1: Double down fill with set union fix")
        setup_data = test.setup()
        loop.run_until_complete(test.test_double_down_fill_with_set_union(setup_data))
        
        # Test 2
        print("\nTest 2: Position calculation with sets")
        setup_data = test.setup()
        loop.run_until_complete(test.test_position_calculation_with_sets(setup_data))
        
        # Test 3
        print("\nTest 3: Error handling")
        setup_data = test.setup()
        loop.run_until_complete(test.test_error_handling_with_missing_position(setup_data))
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()


if __name__ == "__main__":
    # Run with pytest if available, otherwise run directly
    try:
        import pytest
        pytest.main([__file__, "-v", "-s"])
    except ImportError:
        run_tests() 