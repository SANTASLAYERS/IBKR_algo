"""
Test backward compatibility of UnifiedFillManager with concurrency improvements.

This test suite ensures that the new concurrent implementation maintains
full backward compatibility with existing downstream applications.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from src.event.order import FillEvent
from src.event.bus import EventBus
from src.rule.unified_fill_manager import UnifiedFillManager
from src.order.base import OrderStatus, OrderType
from src.position.position_manager import Position, PositionStatus


class TestUnifiedFillManagerBackwardCompatibility:
    """Test that new implementation maintains backward compatibility."""
    
    @pytest_asyncio.fixture
    async def setup(self):
        """Set up test environment."""
        # Create event bus
        event_bus = EventBus()
        
        # Create mock context
        order_manager = AsyncMock()
        position_tracker = AsyncMock()
        
        context = {
            "order_manager": order_manager,
            "position_tracker": position_tracker
        }
        
        # Create UnifiedFillManager
        fill_manager = UnifiedFillManager(context, event_bus)
        await fill_manager.initialize()
        
        yield {
            "event_bus": event_bus,
            "fill_manager": fill_manager,
            "order_manager": order_manager,
            "position_tracker": position_tracker,
            "context": context
        }
        
        # Cleanup
        await fill_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_single_main_order_fill(self, setup):
        """Test basic main order fill - most common downstream use case."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            position.doubledown_orders = set()
            
            mock_pm.get_position.return_value = position
            
            # Mock order
            main_order = MagicMock()
            main_order.quantity = 1000
            main_order.filled_quantity = 1000
            main_order.status.value = "filled"
            
            order_manager.get_order.return_value = main_order
            
            # Create fill event
            fill_event = FillEvent(
                order_id="main1",
                symbol="AAPL",
                status=OrderStatus.FILLED,
                fill_price=150.0,
                fill_quantity=1000,
                cumulative_quantity=1000,
                remaining_quantity=0,
                fill_time=datetime.now()
            )
            
            # Emit event
            await event_bus.emit(fill_event)
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Verify behavior matches original implementation
            # Main order fill should not trigger any order updates
            order_manager.cancel_order.assert_not_called()
            order_manager.create_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_double_down_fill_updates_orders(self, setup):
        """Test double down fill updates protective orders - critical for risk management."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            position.doubledown_orders = {"dd1"}
            
            mock_pm.get_position.return_value = position
            
            # Mock orders
            orders = {
                "main1": {"quantity": 1000, "filled_quantity": 1000, "status": "filled"},
                "dd1": {"quantity": 500, "filled_quantity": 500, "status": "filled"},
                "stop1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "stop_price": 145.0},
                "target1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "limit_price": 155.0}
            }
            
            async def get_order_mock(order_id):
                order_data = orders.get(order_id)
                if order_data:
                    order = MagicMock()
                    for key, value in order_data.items():
                        if key == "status":
                            order.status.value = value
                        else:
                            setattr(order, key, value)
                    return order
                return None
            
            order_manager.get_order.side_effect = get_order_mock
            order_manager.cancel_order.return_value = True
            
            # Mock order creation
            new_order = MagicMock()
            new_order.order_id = "new_order_1"
            order_manager.create_order.return_value = new_order
            
            # Create double down fill event
            fill_event = FillEvent(
                order_id="dd1",
                symbol="AAPL",
                status=OrderStatus.FILLED,
                fill_price=148.0,
                fill_quantity=500,
                cumulative_quantity=500,
                remaining_quantity=0,
                fill_time=datetime.now()
            )
            
            # Emit event
            await event_bus.emit(fill_event)
            
            # Wait for queue processing
            await asyncio.sleep(0.2)
            
            # Verify protective orders were updated
            # Should cancel and recreate both stop and target orders
            assert order_manager.cancel_order.call_count == 2
            assert order_manager.create_order.call_count == 2
            
            # Verify new quantities are -1500 (original 1000 + double down 500)
            create_calls = order_manager.create_order.call_args_list
            for call in create_calls:
                assert call.kwargs["quantity"] == -1500
    
    @pytest.mark.asyncio
    async def test_partial_protective_fill(self, setup):
        """Test partial fill on protective order - ensures proper risk management."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            position.doubledown_orders = set()
            
            mock_pm.get_position.return_value = position
            
            # Mock orders
            orders = {
                "main1": {"quantity": 1000, "filled_quantity": 1000, "status": "filled"},
                "stop1": {"quantity": -1000, "filled_quantity": -300, "status": "working", "stop_price": 145.0},
                "target1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "limit_price": 155.0}
            }
            
            async def get_order_mock(order_id):
                order_data = orders.get(order_id)
                if order_data:
                    order = MagicMock()
                    for key, value in order_data.items():
                        if key == "status":
                            order.status.value = value
                        else:
                            setattr(order, key, value)
                    return order
                return None
            
            order_manager.get_order.side_effect = get_order_mock
            order_manager.cancel_order.return_value = True
            
            # Mock order creation
            new_order = MagicMock()
            new_order.order_id = "new_target_1"
            order_manager.create_order.return_value = new_order
            
            # Create partial stop fill event
            fill_event = FillEvent(
                order_id="stop1",
                symbol="AAPL",
                status=OrderStatus.PARTIALLY_FILLED,
                fill_price=145.0,
                fill_quantity=-300,
                cumulative_quantity=-300,
                remaining_quantity=-700,
                fill_time=datetime.now()
            )
            
            # Emit event
            await event_bus.emit(fill_event)
            
            # Wait for queue processing
            await asyncio.sleep(0.2)
            
            # Verify only target order was updated (not the partially filled stop)
            assert order_manager.cancel_order.call_count == 1
            assert order_manager.create_order.call_count == 1
            
            # Verify target was updated to -700 (remaining position)
            create_call = order_manager.create_order.call_args
            assert create_call.kwargs["quantity"] == -700
            assert create_call.kwargs["order_type"] == OrderType.LIMIT
    
    @pytest.mark.asyncio
    async def test_position_closure_on_full_fill(self, setup):
        """Test position closure when protective order fully fills."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        position_tracker = setup["position_tracker"]
        
        # Mock PositionManager and TradeTracker
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class, \
             patch('src.rule.unified_fill_manager.TradeTracker') as mock_tt_class:
            
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            mock_tt = MagicMock()
            mock_tt_class.return_value = mock_tt
            
            # Create position
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            position.doubledown_orders = set()
            
            mock_pm.get_position.return_value = position
            
            # Mock orders
            stop_order = MagicMock()
            stop_order.quantity = -1000
            stop_order.filled_quantity = -1000
            stop_order.status.value = "filled"
            stop_order.is_active = False
            
            target_order = MagicMock()
            target_order.quantity = -1000
            target_order.filled_quantity = 0
            target_order.status.value = "working"
            target_order.is_active = True
            
            async def get_order_mock(order_id):
                if order_id == "stop1":
                    return stop_order
                elif order_id == "target1":
                    return target_order
                return None
            
            order_manager.get_order.side_effect = get_order_mock
            order_manager.cancel_order.return_value = True
            
            # Mock position tracker
            mock_position = MagicMock()
            mock_position.position_id = "pos1"
            position_tracker.get_positions_for_symbol.return_value = [mock_position]
            
            # Create full stop fill event
            fill_event = FillEvent(
                order_id="stop1",
                symbol="AAPL",
                status=OrderStatus.FILLED,
                fill_price=145.0,
                fill_quantity=-1000,
                cumulative_quantity=-1000,
                remaining_quantity=0,
                fill_time=datetime.now()
            )
            
            # Emit event
            await event_bus.emit(fill_event)
            
            # Wait for queue processing
            await asyncio.sleep(0.2)
            
            # Verify position closure actions
            mock_pm.close_position.assert_called_once_with("AAPL")
            mock_tt.close_trade.assert_called_once_with("AAPL")
            position_tracker.close_position.assert_called_once()
            
            # Verify remaining orders were cancelled
            assert order_manager.cancel_order.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_multiple_sequential_fills(self, setup):
        """Test multiple fills in sequence - common trading scenario."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            position.doubledown_orders = {"dd1", "dd2"}
            
            mock_pm.get_position.return_value = position
            
            # Track fill sequence
            fill_sequence = []
            
            # Mock orders with dynamic state
            order_states = {
                "main1": {"quantity": 1000, "filled_quantity": 1000, "status": "filled"},
                "dd1": {"quantity": 500, "filled_quantity": 0, "status": "working"},
                "dd2": {"quantity": 500, "filled_quantity": 0, "status": "working"},
                "stop1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "stop_price": 145.0},
                "target1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "limit_price": 155.0}
            }
            
            async def get_order_mock(order_id):
                fill_sequence.append(f"get_order_{order_id}")
                order_data = order_states.get(order_id)
                if order_data:
                    order = MagicMock()
                    for key, value in order_data.items():
                        if key == "status":
                            order.status.value = value
                        else:
                            setattr(order, key, value)
                    return order
                return None
            
            order_manager.get_order.side_effect = get_order_mock
            order_manager.cancel_order.return_value = True
            
            # Mock order creation
            order_manager.create_order.return_value = MagicMock(order_id="new_order")
            
            # Emit multiple fills in sequence
            fills = [
                ("dd1", 500, "filled"),
                ("dd2", 500, "filled")
            ]
            
            for order_id, quantity, status in fills:
                # Update order state
                order_states[order_id]["filled_quantity"] = quantity
                order_states[order_id]["status"] = status
                
                fill_event = FillEvent(
                    order_id=order_id,
                    symbol="AAPL",
                    status=OrderStatus.FILLED,
                    fill_price=148.0,
                    fill_quantity=quantity,
                    cumulative_quantity=quantity,
                    remaining_quantity=0,
                    fill_time=datetime.now()
                )
                
                await event_bus.emit(fill_event)
                await asyncio.sleep(0.1)  # Allow processing
            
            # Wait for all queue processing
            await asyncio.sleep(0.5)
            
            # Verify fills were processed in order
            assert "get_order_dd1" in fill_sequence
            assert "get_order_dd2" in fill_sequence
            dd1_index = fill_sequence.index("get_order_dd1")
            dd2_index = fill_sequence.index("get_order_dd2")
            assert dd1_index < dd2_index
            
            # Verify protective orders were updated after each fill
            # Each double down should trigger 2 cancels and 2 creates
            assert order_manager.cancel_order.call_count >= 4
            assert order_manager.create_order.call_count >= 4
    
    @pytest.mark.asyncio
    async def test_error_handling_maintains_state(self, setup):
        """Test that errors don't corrupt state - critical for production stability."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        fill_manager = setup["fill_manager"]
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # First fill will error, second should still process
            call_count = 0
            
            def get_position_side_effect(symbol):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Database connection error")
                
                position = Position(
                    symbol=symbol,
                    side="BUY",
                    entry_time=datetime.now()
                )
                position.main_orders = {"main1"}
                position.stop_orders = {"stop1"}
                position.target_orders = {"target1"}
                position.doubledown_orders = {"dd1"}
                return position
            
            mock_pm.get_position.side_effect = get_position_side_effect
            
            # Mock order
            order = MagicMock()
            order.quantity = 500
            order.filled_quantity = 500
            order.status.value = "filled"
            order_manager.get_order.return_value = order
            
            # First fill - will error
            fill_event1 = FillEvent(
                order_id="dd1",
                symbol="AAPL",
                status=OrderStatus.FILLED,
                fill_price=148.0,
                fill_quantity=500,
                cumulative_quantity=500,
                remaining_quantity=0,
                fill_time=datetime.now()
            )
            
            await event_bus.emit(fill_event1)
            await asyncio.sleep(0.1)
            
            # Second fill - should process successfully
            fill_event2 = FillEvent(
                order_id="dd1",
                symbol="AAPL",
                status=OrderStatus.FILLED,
                fill_price=148.0,
                fill_quantity=500,
                cumulative_quantity=500,
                remaining_quantity=0,
                fill_time=datetime.now()
            )
            
            await event_bus.emit(fill_event2)
            await asyncio.sleep(0.2)
            
            # Verify second fill was processed despite first error
            assert order_manager.get_order.called
            
            # Verify manager is still functional
            assert len(fill_manager._symbol_locks) > 0
            assert len(fill_manager._order_queues) > 0
    
    @pytest.mark.asyncio
    async def test_cleanup_cancels_pending_operations(self, setup):
        """Test cleanup properly cancels pending operations."""
        fill_manager = setup["fill_manager"]
        
        # Create some queues and processors
        queue1 = await fill_manager._get_order_queue("AAPL")
        queue2 = await fill_manager._get_order_queue("GOOGL")
        
        # Add some operations to queues
        from src.rule.unified_fill_manager import OrderOperation, OrderOperationType
        
        op1 = OrderOperation(
            operation_type=OrderOperationType.CANCEL_ALL,
            symbol="AAPL",
            reason="Test"
        )
        op2 = OrderOperation(
            operation_type=OrderOperationType.CANCEL_ALL,
            symbol="GOOGL",
            reason="Test"
        )
        
        await queue1.put(op1)
        await queue2.put(op2)
        
        # Verify processors exist
        assert "AAPL" in fill_manager._queue_processors
        assert "GOOGL" in fill_manager._queue_processors
        
        # Call cleanup
        await fill_manager.cleanup()
        
        # Verify everything was cleaned up
        assert len(fill_manager._queue_processors) == 0
        assert len(fill_manager._order_queues) == 0
        assert len(fill_manager._symbol_locks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 