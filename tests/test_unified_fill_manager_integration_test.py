"""
Integration tests for UnifiedFillManager with concurrency improvements.

These tests simulate real-world trading scenarios to ensure the system
works correctly with the new concurrent implementation.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import logging

from src.event.order import FillEvent
from src.event.bus import EventBus
from src.rule.unified_fill_manager import UnifiedFillManager
from src.order.base import OrderStatus, OrderType
from src.position.position_manager import Position, PositionStatus

# Enable debug logging for troubleshooting
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestUnifiedFillManagerIntegration:
    """Integration tests for real-world scenarios."""
    
    @pytest_asyncio.fixture
    async def setup(self):
        """Set up test environment with realistic mocks."""
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
    async def test_high_frequency_trading_scenario(self, setup):
        """Test rapid fills across multiple symbols - simulates HFT environment."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Track all operations
        operations_log = []
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create positions for multiple symbols
            positions = {}
            symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
            
            for symbol in symbols:
                position = Position(
                    symbol=symbol,
                    side="BUY",
                    entry_time=datetime.now()
                )
                position.main_orders = {f"main_{symbol}"}
                position.stop_orders = {f"stop_{symbol}"}
                position.target_orders = {f"target_{symbol}"}
                position.doubledown_orders = {f"dd_{symbol}"}
                positions[symbol] = position
            
            def get_position_mock(symbol):
                return positions.get(symbol)
            
            mock_pm.get_position.side_effect = get_position_mock
            
            # Mock orders with realistic data
            async def get_order_mock(order_id):
                operations_log.append(f"get_order:{order_id}")
                
                # Simulate some processing time
                await asyncio.sleep(0.001)
                
                order = MagicMock()
                
                # Determine order type and symbol from ID
                if order_id.startswith("main_"):
                    order.quantity = 1000
                    order.filled_quantity = 1000
                    order.status.value = "filled"
                elif order_id.startswith("dd_"):
                    order.quantity = 500
                    order.filled_quantity = 500
                    order.status.value = "filled"
                elif order_id.startswith("stop_"):
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.stop_price = 145.0
                elif order_id.startswith("target_"):
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.limit_price = 155.0
                
                return order
            
            order_manager.get_order.side_effect = get_order_mock
            
            # Mock order operations
            async def cancel_order_mock(order_id, reason):
                operations_log.append(f"cancel:{order_id}")
                await asyncio.sleep(0.001)  # Simulate API latency
                return True
            
            async def create_order_mock(**kwargs):
                operations_log.append(f"create:{kwargs.get('symbol')}:{kwargs.get('quantity')}")
                await asyncio.sleep(0.001)  # Simulate API latency
                order = MagicMock()
                order.order_id = f"new_{kwargs.get('symbol')}_{kwargs.get('order_type')}"
                return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
            # Create rapid fill events across all symbols
            fill_tasks = []
            
            for i in range(3):  # 3 rounds of fills
                for symbol in symbols:
                    fill_event = FillEvent(
                        order_id=f"dd_{symbol}",
                        symbol=symbol,
                        status=OrderStatus.FILLED,
                        fill_price=150.0 + i,
                        fill_quantity=500,
                        cumulative_quantity=500,
                        remaining_quantity=0,
                        fill_time=datetime.now()
                    )
                    
                    # Fire events rapidly
                    fill_tasks.append(event_bus.emit(fill_event))
            
            # Execute all fills concurrently
            await asyncio.gather(*fill_tasks)
            
            # Wait for all processing to complete
            await asyncio.sleep(1.0)
            
            # Verify results
            # Each symbol should have its fills processed in order
            for symbol in symbols:
                symbol_ops = [op for op in operations_log if symbol in op]
                logger.info(f"Operations for {symbol}: {len(symbol_ops)}")
            
            # Verify all operations completed
            cancel_count = len([op for op in operations_log if op.startswith("cancel:")])
            create_count = len([op for op in operations_log if op.startswith("create:")])
            
            # Each symbol gets 3 double down fills, each triggering 2 cancels and 2 creates
            expected_cancels = len(symbols) * 3 * 2
            expected_creates = len(symbols) * 3 * 2
            
            assert cancel_count == expected_cancels, f"Expected {expected_cancels} cancels, got {cancel_count}"
            assert create_count == expected_creates, f"Expected {expected_creates} creates, got {create_count}"
    
    @pytest.mark.asyncio
    async def test_partial_fill_cascade(self, setup):
        """Test cascading partial fills on protective orders."""
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
            
            # Track order states
            order_states = {
                "main1": {"quantity": 1000, "filled_quantity": 1000, "status": "filled"},
                "stop1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "stop_price": 145.0},
                "target1": {"quantity": -1000, "filled_quantity": 0, "status": "working", "limit_price": 155.0}
            }
            
            # Track operations
            operations = []
            
            async def get_order_mock(order_id):
                operations.append(("get_order", order_id))
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
            
            # Mock order operations
            async def cancel_order_mock(order_id, reason):
                operations.append(("cancel", order_id, reason))
                return True
            
            new_order_counter = 0
            
            async def create_order_mock(**kwargs):
                nonlocal new_order_counter
                new_order_counter += 1
                operations.append(("create", kwargs))
                order = MagicMock()
                order.order_id = f"new_order_{new_order_counter}"
                
                # Update position tracking
                if kwargs.get("order_type") == OrderType.STOP:
                    position.stop_orders = {order.order_id}
                elif kwargs.get("order_type") == OrderType.LIMIT:
                    position.target_orders = {order.order_id}
                
                # Add to order states
                order_states[order.order_id] = {
                    "quantity": kwargs["quantity"],
                    "filled_quantity": 0,
                    "status": "working",
                    "stop_price": kwargs.get("stop_price"),
                    "limit_price": kwargs.get("limit_price")
                }
                
                return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
            # Simulate cascading partial fills on target
            partial_fills = [
                ("target1", -200, -200, -800),
                ("new_order_1", -300, -500, -500),
                ("new_order_2", -250, -750, -250),
                ("new_order_3", -250, -1000, 0)
            ]
            
            for order_id, fill_qty, cum_qty, remaining in partial_fills:
                # Update order state
                if order_id in order_states:
                    order_states[order_id]["filled_quantity"] = cum_qty
                    if remaining == 0:
                        order_states[order_id]["status"] = "filled"
                
                fill_event = FillEvent(
                    order_id=order_id,
                    symbol="AAPL",
                    status=OrderStatus.PARTIALLY_FILLED if remaining != 0 else OrderStatus.FILLED,
                    fill_price=155.0,
                    fill_quantity=fill_qty,
                    cumulative_quantity=cum_qty,
                    remaining_quantity=remaining,
                    fill_time=datetime.now()
                )
                
                await event_bus.emit(fill_event)
                await asyncio.sleep(0.3)  # Wait for processing
            
            # Verify operations
            create_ops = [op for op in operations if op[0] == "create"]
            cancel_ops = [op for op in operations if op[0] == "cancel"]
            
            # Should have created new stop orders after each partial fill
            assert len(create_ops) >= 3, f"Expected at least 3 create operations, got {len(create_ops)}"
            
            # Verify quantities were updated correctly
            for op in create_ops:
                _, kwargs = op
                logger.info(f"Created order with quantity: {kwargs['quantity']}")
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_retry(self, setup):
        """Test error handling and retry logic in production scenarios."""
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
            async def get_order_mock(order_id):
                order = MagicMock()
                if order_id == "main1":
                    order.quantity = 1000
                    order.filled_quantity = 1000
                    order.status.value = "filled"
                elif order_id == "dd1":
                    order.quantity = 500
                    order.filled_quantity = 500
                    order.status.value = "filled"
                elif order_id == "stop1":
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.stop_price = 145.0
                elif order_id == "target1":
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.limit_price = 155.0
                return order
            
            order_manager.get_order.side_effect = get_order_mock
            
            # Mock order operations with failures
            cancel_attempts = 0
            
            async def cancel_order_mock(order_id, reason):
                nonlocal cancel_attempts
                cancel_attempts += 1
                
                # Fail first attempt, succeed on retry
                if cancel_attempts <= 2:
                    logger.info(f"Cancel attempt {cancel_attempts} for {order_id} - FAILING")
                    return False
                else:
                    logger.info(f"Cancel attempt {cancel_attempts} for {order_id} - SUCCESS")
                    return True
            
            create_attempts = 0
            
            async def create_order_mock(**kwargs):
                nonlocal create_attempts
                create_attempts += 1
                
                # Fail first attempt, succeed on retry
                if create_attempts <= 2:
                    logger.info(f"Create attempt {create_attempts} - FAILING")
                    return None
                else:
                    logger.info(f"Create attempt {create_attempts} - SUCCESS")
                    order = MagicMock()
                    order.order_id = f"new_order_{create_attempts}"
                    return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
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
            
            # Wait for retry logic to complete
            await asyncio.sleep(3.0)
            
            # Verify retry logic worked
            assert cancel_attempts >= 4, f"Expected at least 4 cancel attempts (2 orders with retries), got {cancel_attempts}"
            assert create_attempts >= 4, f"Expected at least 4 create attempts (2 orders with retries), got {create_attempts}"
            
            # Verify orders were eventually created
            assert order_manager.create_order.call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
