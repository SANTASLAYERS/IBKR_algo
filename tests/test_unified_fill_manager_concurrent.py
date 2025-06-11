"""
Test concurrent fill handling in UnifiedFillManager.

This test verifies that the UnifiedFillManager correctly handles
concurrent fills for the same symbol without race conditions.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.event.order import FillEvent
from src.event.bus import EventBus
from src.rule.unified_fill_manager import UnifiedFillManager
from src.order.base import OrderStatus, OrderType
from src.position.position_manager import Position, PositionStatus


class TestUnifiedFillManagerConcurrent:
    """Test concurrent fill handling."""
    
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
            "position_tracker": position_tracker
        }
        
        # Cleanup
        await fill_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_concurrent_fills_same_symbol(self, setup):
        """Test that concurrent fills for the same symbol are serialized."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Track order of operations
        operations = []
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position with orders
            position = Position(
                symbol="AAPL",
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main1"}
            position.doubledown_orders = {"dd1", "dd2"}
            position.stop_orders = {"stop1"}
            position.target_orders = {"target1"}
            
            mock_pm.get_position.return_value = position
            
            # Mock orders
            async def get_order_side_effect(order_id):
                await asyncio.sleep(0.01)  # Simulate some processing time
                operations.append(f"get_order_{order_id}")
                
                if order_id == "main1":
                    order = MagicMock()
                    order.quantity = 1000
                    order.filled_quantity = 1000
                    order.status.value = "filled"
                    return order
                elif order_id in ["dd1", "dd2"]:
                    order = MagicMock()
                    order.quantity = 500
                    order.filled_quantity = 500
                    order.status.value = "filled"
                    return order
                elif order_id == "stop1":
                    order = MagicMock()
                    order.quantity = -2000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.stop_price = 100.0
                    return order
                elif order_id == "target1":
                    order = MagicMock()
                    order.quantity = -2000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.limit_price = 110.0
                    return order
                return None
            
            order_manager.get_order.side_effect = get_order_side_effect
            
            # Mock order cancellation and creation
            async def cancel_order_side_effect(order_id, reason):
                await asyncio.sleep(0.01)  # Simulate API call
                operations.append(f"cancel_{order_id}")
                return True
            
            async def create_order_side_effect(**kwargs):
                await asyncio.sleep(0.01)  # Simulate API call
                operations.append(f"create_{kwargs.get('order_type', 'unknown')}")
                new_order = MagicMock()
                new_order.order_id = f"new_{kwargs.get('order_type', 'unknown')}"
                return new_order
            
            order_manager.cancel_order.side_effect = cancel_order_side_effect
            order_manager.create_order.side_effect = create_order_side_effect
            
            # Create concurrent fill events
            fill_events = [
                FillEvent(
                    order_id="dd1",
                    symbol="AAPL",
                    status=OrderStatus.FILLED,
                    fill_price=105.0,
                    fill_quantity=500,
                    cumulative_quantity=500,
                    remaining_quantity=0,
                    fill_time=datetime.now()
                ),
                FillEvent(
                    order_id="dd2",
                    symbol="AAPL",
                    status=OrderStatus.FILLED,
                    fill_price=105.5,
                    fill_quantity=500,
                    cumulative_quantity=500,
                    remaining_quantity=0,
                    fill_time=datetime.now()
                )
            ]
            
            # Emit fills concurrently
            tasks = []
            for event in fill_events:
                tasks.append(event_bus.emit(event))
            
            await asyncio.gather(*tasks)
            
            # Wait for processing to complete
            await asyncio.sleep(0.5)
            
            # Verify operations were serialized
            # Should see dd1 processing complete before dd2 starts
            dd1_ops = [op for op in operations if "dd1" in op]
            dd2_ops = [op for op in operations if "dd2" in op]
            
            # Find indices of first operation for each fill
            dd1_start = operations.index("get_order_dd1")
            dd2_start = operations.index("get_order_dd2")
            
            # All dd1 operations should complete before dd2 operations start
            # (due to symbol lock serialization)
            assert dd1_start < dd2_start, f"Operations not serialized: {operations}"
            
            # Verify protective orders were updated
            cancel_ops = [op for op in operations if op.startswith("cancel_")]
            create_ops = [op for op in operations if op.startswith("create_")]
            
            # Should have cancelled and recreated protective orders
            assert len(cancel_ops) >= 2  # At least stop and target
            assert len(create_ops) >= 2  # At least stop and target
    
    @pytest.mark.asyncio
    async def test_concurrent_fills_different_symbols(self, setup):
        """Test that fills for different symbols can process concurrently."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Track timing of operations
        operation_times = {}
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create positions for two symbols
            def get_position_side_effect(symbol):
                position = Position(
                    symbol=symbol,
                    side="BUY",
                    entry_time=datetime.now()
                )
                position.main_orders = {f"main_{symbol}"}
                position.doubledown_orders = {f"dd_{symbol}"}
                position.stop_orders = {f"stop_{symbol}"}
                position.target_orders = {f"target_{symbol}"}
                return position
            
            mock_pm.get_position.side_effect = get_position_side_effect
            
            # Mock orders with timing tracking
            async def get_order_side_effect(order_id):
                start_time = asyncio.get_event_loop().time()
                await asyncio.sleep(0.1)  # Simulate significant processing time
                operation_times[f"get_order_{order_id}"] = {
                    "start": start_time,
                    "end": asyncio.get_event_loop().time()
                }
                
                order = MagicMock()
                order.quantity = 1000
                order.filled_quantity = 1000
                order.status.value = "filled"
                return order
            
            order_manager.get_order.side_effect = get_order_side_effect
            
            # Create fill events for different symbols
            symbols = ["AAPL", "GOOGL", "MSFT"]
            fill_events = []
            
            for symbol in symbols:
                event = FillEvent(
                    order_id=f"dd_{symbol}",
                    symbol=symbol,
                    status=OrderStatus.FILLED,
                    fill_price=100.0,
                    fill_quantity=1000,
                    cumulative_quantity=1000,
                    remaining_quantity=0,
                    fill_time=datetime.now()
                )
                fill_events.append(event)
            
            # Emit all fills at once
            start_time = asyncio.get_event_loop().time()
            tasks = []
            for event in fill_events:
                tasks.append(event_bus.emit(event))
            
            await asyncio.gather(*tasks)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Verify concurrent processing
            # Operations for different symbols should overlap in time
            overlaps = 0
            for symbol1 in symbols:
                for symbol2 in symbols:
                    if symbol1 != symbol2:
                        key1 = f"get_order_dd_{symbol1}"
                        key2 = f"get_order_dd_{symbol2}"
                        
                        if key1 in operation_times and key2 in operation_times:
                            # Check if operations overlapped
                            if (operation_times[key1]["start"] < operation_times[key2]["end"] and
                                operation_times[key2]["start"] < operation_times[key1]["end"]):
                                overlaps += 1
            
            # Should see overlapping operations for different symbols
            assert overlaps > 0, "Different symbols did not process concurrently"
    
    @pytest.mark.asyncio
    async def test_queue_processing_order(self, setup):
        """Test that order operations are processed in FIFO order."""
        fill_manager = setup["fill_manager"]
        
        # Track operations
        executed_operations = []
        
        # Mock the execute methods
        async def mock_execute_replace(symbol, old_id, qty, order_type, price):
            executed_operations.append(("replace", order_type, old_id))
            await asyncio.sleep(0.01)
        
        async def mock_execute_cancel_all(symbol, reason):
            executed_operations.append(("cancel_all", symbol))
            await asyncio.sleep(0.01)
        
        fill_manager._execute_replace_order = mock_execute_replace
        fill_manager._execute_cancel_all_orders = mock_execute_cancel_all
        
        # Get queue for a symbol
        queue = await fill_manager._get_order_queue("AAPL")
        
        # Add multiple operations
        from src.rule.unified_fill_manager import OrderOperation, OrderOperationType
        
        operations = [
            OrderOperation(
                operation_type=OrderOperationType.REPLACE_STOP,
                symbol="AAPL",
                old_order_id="stop1",
                new_quantity=-1000,
                price=100.0
            ),
            OrderOperation(
                operation_type=OrderOperationType.REPLACE_TARGET,
                symbol="AAPL",
                old_order_id="target1",
                new_quantity=-1000,
                price=110.0
            ),
            OrderOperation(
                operation_type=OrderOperationType.CANCEL_ALL,
                symbol="AAPL",
                reason="Test"
            )
        ]
        
        # Queue all operations
        for op in operations:
            await queue.put(op)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify FIFO order
        assert len(executed_operations) == 3
        assert executed_operations[0] == ("replace", "stop", "stop1")
        assert executed_operations[1] == ("replace", "target", "target1")
        assert executed_operations[2] == ("cancel_all", "AAPL")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 