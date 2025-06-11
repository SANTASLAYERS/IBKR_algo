"""
Test suite for UnifiedFillManager.

Tests the centralized fill handling and protective order updates.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

from src.rule.unified_fill_manager import UnifiedFillManager
from src.event.bus import EventBus
from src.event.order import FillEvent
from src.position.position_manager import PositionManager
from src.order.base import OrderType, OrderStatus, Order


class TestUnifiedFillManager:
    """Test cases for UnifiedFillManager."""
    
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
    async def test_initialization(self, setup):
        """Test manager initialization."""
        manager = setup["manager"]
        event_bus = setup["event_bus"]
        
        # Initialize manager
        await manager.initialize()
        
        # Verify subscription to FillEvent
        assert len(event_bus._subscribers.get(FillEvent, [])) == 1
    
    @pytest.mark.asyncio
    async def test_main_order_fill(self, setup):
        """Test handling of main order fill (market order)."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        
        # Setup position
        position_manager.open_position("AAPL", "BUY")
        position = position_manager.get_position("AAPL")
        position.main_orders = ["order_123"]
        position.current_quantity = 100
        
        # Mock order
        main_order = Mock()
        main_order.order_id = "order_123"
        main_order.quantity = 100
        main_order.status = Mock(value="filled")
        order_manager.get_order.return_value = main_order
        
        # Create fill event
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="order_123",
            fill_quantity=100,
            fill_price=150.00,
            timestamp=datetime.now()
        )
        
        # Process fill
        await manager.on_order_fill(fill_event)
        
        # Verify no protective order updates for main order
        order_manager.cancel_order.assert_not_called()
        order_manager.create_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_double_down_fill_updates_protective_orders(self, setup):
        """Test that double down fills trigger protective order updates."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        
        # Setup position with orders
        position_manager.open_position("AAPL", "BUY")
        position = position_manager.get_position("AAPL")
        position.main_orders = ["main_123"]
        position.doubledown_orders = ["dd_456"]
        position.stop_orders = ["stop_789"]
        position.target_orders = ["target_012"]
        position.current_quantity = 100
        
        # Mock orders
        main_order = Mock()
        main_order.order_id = "main_123"
        main_order.quantity = 100
        main_order.filled_quantity = 100
        
        dd_order = Mock()
        dd_order.order_id = "dd_456"
        dd_order.quantity = 100
        dd_order.filled_quantity = 100
        dd_order.status = Mock(value="filled")
        
        stop_order = Mock()
        stop_order.order_id = "stop_789"
        stop_order.quantity = -100
        stop_order.filled_quantity = 0
        stop_order.stop_price = 145.00
        stop_order.status = Mock(value="working")
        
        target_order = Mock()
        target_order.order_id = "target_012"
        target_order.quantity = -100
        target_order.filled_quantity = 0
        target_order.limit_price = 160.00
        target_order.status = Mock(value="working")
        
        # Setup order manager mock
        order_manager.get_order.side_effect = lambda order_id: {
            "main_123": main_order,
            "dd_456": dd_order,
            "stop_789": stop_order,
            "target_012": target_order
        }.get(order_id)
        
        # Mock order creation
        new_stop = Mock()
        new_stop.order_id = "new_stop_123"
        new_target = Mock()
        new_target.order_id = "new_target_456"
        
        order_manager.create_order.side_effect = [new_stop, new_target]
        
        # Create double down fill event
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="dd_456",
            fill_quantity=100,
            fill_price=147.50,
            timestamp=datetime.now()
        )
        
        # Process fill
        await manager.on_order_fill(fill_event)
        
        # Verify protective orders were cancelled
        assert order_manager.cancel_order.call_count == 2
        order_manager.cancel_order.assert_any_call("stop_789", "Updating quantity to -200")
        order_manager.cancel_order.assert_any_call("target_012", "Updating quantity to -200")
        
        # Verify new protective orders created with updated quantity
        assert order_manager.create_order.call_count == 2
        
        # Check stop order creation
        stop_call = order_manager.create_order.call_args_list[0]
        assert stop_call.kwargs["symbol"] == "AAPL"
        assert stop_call.kwargs["quantity"] == -200  # Updated quantity
        assert stop_call.kwargs["order_type"] == OrderType.STOP
        assert stop_call.kwargs["stop_price"] == 145.00
        
        # Check target order creation
        target_call = order_manager.create_order.call_args_list[1]
        assert target_call.kwargs["symbol"] == "AAPL"
        assert target_call.kwargs["quantity"] == -200  # Updated quantity
        assert target_call.kwargs["order_type"] == OrderType.LIMIT
        assert target_call.kwargs["limit_price"] == 160.00
    
    @pytest.mark.asyncio
    async def test_protective_partial_fill_updates_other_protective(self, setup):
        """Test that partial fill of one protective order updates the other."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        
        # Setup position
        position_manager.open_position("AAPL", "BUY")
        position = position_manager.get_position("AAPL")
        position.main_orders = ["main_123"]
        position.stop_orders = ["stop_789"]
        position.target_orders = ["target_012"]
        position.current_quantity = 200
        
        # Mock orders
        main_order = Mock()
        main_order.quantity = 200
        main_order.filled_quantity = 200
        
        stop_order = Mock()
        stop_order.order_id = "stop_789"
        stop_order.quantity = -200
        stop_order.filled_quantity = -50  # Partial fill
        stop_order.stop_price = 145.00
        stop_order.status = Mock(value="partially_filled")
        
        target_order = Mock()
        target_order.order_id = "target_012"
        target_order.quantity = -200
        target_order.filled_quantity = 0
        target_order.limit_price = 160.00
        target_order.status = Mock(value="working")
        
        # Setup order manager mock
        order_manager.get_order.side_effect = lambda order_id: {
            "main_123": main_order,
            "stop_789": stop_order,
            "target_012": target_order
        }.get(order_id)
        
        # Mock new target order
        new_target = Mock()
        new_target.order_id = "new_target_789"
        order_manager.create_order.return_value = new_target
        
        # Create partial fill event for stop order
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="stop_789",
            fill_quantity=-50,
            fill_price=145.00,
            timestamp=datetime.now()
        )
        
        # Process fill
        await manager.on_order_fill(fill_event)
        
        # Verify only target order was updated (not the partially filled stop)
        assert order_manager.cancel_order.call_count == 1
        order_manager.cancel_order.assert_called_with("target_012", "Updating quantity to -150")
        
        # Verify new target order created with remaining quantity
        order_manager.create_order.assert_called_once()
        target_call = order_manager.create_order.call_args
        assert target_call.kwargs["quantity"] == -150  # Remaining position
        assert target_call.kwargs["order_type"] == OrderType.LIMIT
        assert target_call.kwargs["limit_price"] == 160.00
    
    @pytest.mark.asyncio
    async def test_protective_full_fill_closes_position(self, setup):
        """Test that full fill of protective order closes the position."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        position_tracker = setup["position_tracker"]
        
        # Setup position
        position_manager.open_position("AAPL", "BUY")
        position = position_manager.get_position("AAPL")
        position.main_orders = ["main_123"]
        position.stop_orders = ["stop_789"]
        position.target_orders = ["target_012"]
        position.doubledown_orders = ["dd_456"]
        
        # Mock orders
        stop_order = Mock()
        stop_order.order_id = "stop_789"
        stop_order.status = Mock(value="filled")  # Fully filled
        stop_order.is_active = False
        
        target_order = Mock()
        target_order.order_id = "target_012"
        target_order.is_active = True
        
        dd_order = Mock()
        dd_order.order_id = "dd_456"
        dd_order.is_active = True
        
        # Setup order manager mock
        order_manager.get_order.side_effect = lambda order_id: {
            "stop_789": stop_order,
            "target_012": target_order,
            "dd_456": dd_order
        }.get(order_id)
        
        # Mock position tracker positions
        mock_position = Mock()
        mock_position.position_id = "pos_123"
        position_tracker.get_positions_for_symbol.return_value = [mock_position]
        
        # Create full fill event for stop order
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="stop_789",
            fill_quantity=-100,
            fill_price=145.00,
            timestamp=datetime.now()
        )
        
        # Process fill
        await manager.on_order_fill(fill_event)
        
        # Verify all remaining orders cancelled
        assert order_manager.cancel_order.call_count >= 2
        order_manager.cancel_order.assert_any_call("target_012", "Position closed: Stop order fully filled")
        order_manager.cancel_order.assert_any_call("dd_456", "Position closed: Stop order fully filled")
        
        # Verify position closed
        assert position.status == "CLOSED"
        position_tracker.close_position.assert_called_with("pos_123", "Stop order fully filled")
    
    @pytest.mark.asyncio
    async def test_position_flat_after_double_down(self, setup):
        """Test handling when position becomes flat after double down."""
        manager = setup["manager"]
        position_manager = setup["position_manager"]
        order_manager = setup["order_manager"]
        
        # Setup short position
        position_manager.open_position("AAPL", "SELL")
        position = position_manager.get_position("AAPL")
        position.main_orders = ["main_123"]
        position.doubledown_orders = ["dd_456"]
        position.current_quantity = -100
        
        # Mock orders - position will be flat after double down
        main_order = Mock()
        main_order.quantity = -100
        main_order.filled_quantity = -100
        
        dd_order = Mock()
        dd_order.order_id = "dd_456"
        dd_order.quantity = 100  # Opposite side, will flatten position
        dd_order.filled_quantity = 100
        dd_order.status = Mock(value="filled")
        
        # Setup order manager mock
        order_manager.get_order.side_effect = lambda order_id: {
            "main_123": main_order,
            "dd_456": dd_order
        }.get(order_id)
        
        # Create fill event
        fill_event = FillEvent(
            symbol="AAPL",
            order_id="dd_456",
            fill_quantity=100,
            fill_price=150.00,
            timestamp=datetime.now()
        )
        
        # Process fill
        await manager.on_order_fill(fill_event)
        
        # Verify position closed due to being flat
        assert position.status == "CLOSED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 