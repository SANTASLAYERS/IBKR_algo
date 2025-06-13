"""
Test concurrent fills across multiple symbols to verify thread safety.

This test simulates a real-world scenario where multiple symbols receive
fills simultaneously, ensuring the UnifiedFillManager correctly handles
concurrent processing while maintaining data integrity.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import logging
from typing import Dict, List, Set

from src.event.order import FillEvent
from src.event.bus import EventBus
from src.rule.unified_fill_manager import UnifiedFillManager
from src.order.base import OrderStatus, OrderType
from src.position.position_manager import Position, PositionStatus

# Enable debug logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMultiSymbolConcurrentFills:
    """Test concurrent fills across multiple symbols."""
    
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
    async def test_concurrent_fills_multiple_symbols(self, setup):
        """Test 5 concurrent fills on 5 different stocks."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Test symbols
        symbols = ["CVNA", "GLD", "SOXL", "SOXS", "TQQQ"]
        
        # Track all operations for verification
        operations_log = []
        operation_timestamps = {}
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create positions for each symbol
            positions = {}
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
            
            # Mock orders with tracking
            async def get_order_mock(order_id):
                start_time = asyncio.get_event_loop().time()
                operations_log.append(("get_order", order_id, start_time))
                
                # Simulate API latency
                await asyncio.sleep(0.01)
                
                order = MagicMock()
                
                # Parse symbol from order_id
                for symbol in symbols:
                    if symbol in order_id:
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
                            order.stop_price = 100.0
                        elif order_id.startswith("target_"):
                            order.quantity = -1000
                            order.filled_quantity = 0
                            order.status.value = "working"
                            order.limit_price = 110.0
                        break
                
                end_time = asyncio.get_event_loop().time()
                operation_timestamps[f"get_order_{order_id}"] = {
                    "start": start_time,
                    "end": end_time,
                    "duration": end_time - start_time
                }
                
                return order
            
            order_manager.get_order.side_effect = get_order_mock
            
            # Mock order operations
            async def cancel_order_mock(order_id, reason):
                start_time = asyncio.get_event_loop().time()
                operations_log.append(("cancel", order_id, start_time))
                await asyncio.sleep(0.01)  # Simulate API latency
                return True
            
            async def create_order_mock(**kwargs):
                start_time = asyncio.get_event_loop().time()
                symbol = kwargs.get('symbol')
                quantity = kwargs.get('quantity')
                order_type = kwargs.get('order_type')
                
                operations_log.append(("create", symbol, quantity, order_type, start_time))
                await asyncio.sleep(0.01)  # Simulate API latency
                
                order = MagicMock()
                order.order_id = f"new_{symbol}_{order_type}_{len(operations_log)}"
                return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
            # Create concurrent fill events - all at the same time
            fill_events = []
            for symbol in symbols:
                # Double down fill that should trigger protective order updates
                fill_event = FillEvent(
                    order_id=f"dd_{symbol}",
                    symbol=symbol,
                    status=OrderStatus.FILLED,
                    fill_price=105.0,
                    fill_quantity=500,
                    cumulative_quantity=500,
                    remaining_quantity=0,
                    fill_time=datetime.now()
                )
                fill_events.append(fill_event)
            
            # Record start time
            start_time = asyncio.get_event_loop().time()
            
            # Fire all events concurrently
            tasks = []
            for event in fill_events:
                tasks.append(event_bus.emit(event))
            
            await asyncio.gather(*tasks)
            
            # Wait for all processing to complete
            await asyncio.sleep(1.0)
            
            # Record end time
            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time
            
            logger.info(f"\n{'='*60}")
            logger.info(f"CONCURRENT FILL TEST RESULTS")
            logger.info(f"{'='*60}")
            logger.info(f"Total processing time: {total_time:.3f} seconds")
            logger.info(f"Total operations: {len(operations_log)}")
            
            # Analyze operations by symbol
            symbol_operations = {symbol: [] for symbol in symbols}
            for op in operations_log:
                for symbol in symbols:
                    if symbol in str(op):
                        symbol_operations[symbol].append(op)
                        break
            
            # Verify each symbol was processed correctly
            for symbol in symbols:
                ops = symbol_operations[symbol]
                logger.info(f"\n{symbol} operations: {len(ops)}")
                
                # Each symbol should have:
                # - 1 get_order for double down
                # - 1 get_order for main order (position calculation)
                # - 2 get_order for protective orders
                # - 2 cancel operations (stop and target)
                # - 2 create operations (new stop and target)
                
                get_ops = [op for op in ops if op[0] == "get_order"]
                cancel_ops = [op for op in ops if op[0] == "cancel"]
                create_ops = [op for op in ops if op[0] == "create"]
                
                assert len(get_ops) >= 4, f"{symbol}: Expected at least 4 get operations, got {len(get_ops)}"
                assert len(cancel_ops) == 2, f"{symbol}: Expected 2 cancel operations, got {len(cancel_ops)}"
                assert len(create_ops) == 2, f"{symbol}: Expected 2 create operations, got {len(create_ops)}"
                
                # Verify new quantities are correct (-1500 for long position)
                for op in create_ops:
                    _, symbol_in_op, quantity, order_type, _ = op
                    assert quantity == -1500, f"{symbol}: Expected quantity -1500, got {quantity}"
            
            # Analyze concurrency - check for overlapping operations
            overlaps = 0
            for symbol1 in symbols:
                for symbol2 in symbols:
                    if symbol1 != symbol2:
                        # Check if any operations overlapped
                        for key1, times1 in operation_timestamps.items():
                            if symbol1 in key1:
                                for key2, times2 in operation_timestamps.items():
                                    if symbol2 in key2:
                                        # Check for time overlap
                                        if (times1["start"] < times2["end"] and 
                                            times2["start"] < times1["end"]):
                                            overlaps += 1
            
            logger.info(f"\nConcurrency Analysis:")
            logger.info(f"Overlapping operations: {overlaps}")
            logger.info(f"Average operations per symbol: {len(operations_log) / len(symbols):.1f}")
            
            # Verify significant overlap occurred (proving concurrent processing)
            assert overlaps > 0, "No concurrent processing detected - operations were sequential"
            
            # Verify all operations completed successfully
            assert order_manager.cancel_order.call_count == len(symbols) * 2
            assert order_manager.create_order.call_count == len(symbols) * 2
    
    @pytest.mark.asyncio
    async def test_rapid_fire_fills_same_symbol(self, setup):
        """Test rapid consecutive fills on the same symbol to verify serialization."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        symbol = "CVNA"
        
        # Track operation order
        operation_sequence = []
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create position
            position = Position(
                symbol=symbol,
                side="BUY",
                entry_time=datetime.now()
            )
            position.main_orders = {"main_CVNA"}
            position.stop_orders = {"stop_CVNA"}
            position.target_orders = {"target_CVNA"}
            position.doubledown_orders = {"dd_CVNA_1", "dd_CVNA_2", "dd_CVNA_3"}
            
            mock_pm.get_position.return_value = position
            
            # Track order states
            order_quantities = {
                "main_CVNA": 1000,
                "dd_CVNA_1": 200,
                "dd_CVNA_2": 300,
                "dd_CVNA_3": 500
            }
            
            # Mock orders
            async def get_order_mock(order_id):
                operation_sequence.append(f"get_{order_id}")
                await asyncio.sleep(0.005)  # Small delay
                
                order = MagicMock()
                if order_id in order_quantities:
                    order.quantity = order_quantities[order_id]
                    order.filled_quantity = order_quantities[order_id]
                    order.status.value = "filled"
                elif order_id == "stop_CVNA":
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.stop_price = 50.0
                elif order_id == "target_CVNA":
                    order.quantity = -1000
                    order.filled_quantity = 0
                    order.status.value = "working"
                    order.limit_price = 60.0
                
                return order
            
            order_manager.get_order.side_effect = get_order_mock
            
            # Mock order operations
            async def cancel_order_mock(order_id, reason):
                operation_sequence.append(f"cancel_{order_id}")
                return True
            
            async def create_order_mock(**kwargs):
                operation_sequence.append(f"create_{kwargs.get('order_type')}_{kwargs.get('quantity')}")
                order = MagicMock()
                order.order_id = f"new_order_{len(operation_sequence)}"
                return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
            # Fire multiple fills rapidly
            fill_tasks = []
            for i in range(1, 4):
                fill_event = FillEvent(
                    order_id=f"dd_CVNA_{i}",
                    symbol=symbol,
                    status=OrderStatus.FILLED,
                    fill_price=55.0 + i,
                    fill_quantity=order_quantities[f"dd_CVNA_{i}"],
                    cumulative_quantity=order_quantities[f"dd_CVNA_{i}"],
                    remaining_quantity=0,
                    fill_time=datetime.now()
                )
                fill_tasks.append(event_bus.emit(fill_event))
            
            # Execute all fills at once
            await asyncio.gather(*fill_tasks)
            
            # Wait for processing
            await asyncio.sleep(1.0)
            
            logger.info(f"\nOperation sequence for {symbol}:")
            for i, op in enumerate(operation_sequence):
                logger.info(f"{i+1}. {op}")
            
            # Verify fills were processed in order (serialized)
            # Each fill should complete before the next starts
            dd1_ops = [i for i, op in enumerate(operation_sequence) if "dd_CVNA_1" in op]
            dd2_ops = [i for i, op in enumerate(operation_sequence) if "dd_CVNA_2" in op]
            dd3_ops = [i for i, op in enumerate(operation_sequence) if "dd_CVNA_3" in op]
            
            # Verify dd1 operations complete before dd2 starts
            if dd1_ops and dd2_ops:
                assert max(dd1_ops) < min(dd2_ops), "DD1 operations should complete before DD2 starts"
            
            # Verify dd2 operations complete before dd3 starts
            if dd2_ops and dd3_ops:
                assert max(dd2_ops) < min(dd3_ops), "DD2 operations should complete before DD3 starts"
            
            # Verify final position size is correct
            # Should be 1000 + 200 + 300 + 500 = 2000
            final_creates = [op for op in operation_sequence if op.startswith("create_")]
            last_create = final_creates[-1] if final_creates else None
            
            if last_create:
                # Extract quantity from create operation
                parts = last_create.split("_")
                quantity = int(parts[-1])
                assert quantity == -2000, f"Final protective order quantity should be -2000, got {quantity}"
    
    @pytest.mark.asyncio
    async def test_mixed_operations_multiple_symbols(self, setup):
        """Test mixed operations (fills, partial fills, cancellations) across symbols."""
        event_bus = setup["event_bus"]
        order_manager = setup["order_manager"]
        
        # Test different scenarios for each symbol
        test_scenarios = {
            "CVNA": "double_down",
            "GLD": "partial_target_fill",
            "SOXL": "full_stop_fill",
            "SOXS": "partial_stop_fill",
            "TQQQ": "double_down"
        }
        
        # Track results
        results = {symbol: {"operations": [], "final_state": None} for symbol in test_scenarios}
        
        # Mock PositionManager
        with patch('src.rule.unified_fill_manager.PositionManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # Create positions
            positions = {}
            for symbol in test_scenarios:
                position = Position(
                    symbol=symbol,
                    side="BUY",
                    entry_time=datetime.now()
                )
                position.main_orders = {f"main_{symbol}"}
                position.stop_orders = {f"stop_{symbol}"}
                position.target_orders = {f"target_{symbol}"}
                position.doubledown_orders = {f"dd_{symbol}"} if "double_down" in test_scenarios[symbol] else set()
                positions[symbol] = position
            
            def get_position_mock(symbol):
                return positions.get(symbol)
            
            mock_pm.get_position.side_effect = get_position_mock
            
            # Mock orders based on scenario
            async def get_order_mock(order_id):
                await asyncio.sleep(0.005)
                order = MagicMock()
                
                # Determine symbol and type
                for symbol in test_scenarios:
                    if symbol in order_id:
                        scenario = test_scenarios[symbol]
                        
                        if order_id.startswith("main_"):
                            order.quantity = 1000
                            order.filled_quantity = 1000
                            order.status.value = "filled"
                        elif order_id.startswith("dd_"):
                            order.quantity = 500
                            order.filled_quantity = 500
                            order.status.value = "filled"
                        elif order_id.startswith("stop_"):
                            if scenario == "full_stop_fill":
                                order.quantity = -1000
                                order.filled_quantity = -1000
                                order.status.value = "filled"
                            elif scenario == "partial_stop_fill":
                                order.quantity = -1000
                                order.filled_quantity = -400
                                order.status.value = "working"
                            else:
                                order.quantity = -1000
                                order.filled_quantity = 0
                                order.status.value = "working"
                            order.stop_price = 95.0
                        elif order_id.startswith("target_"):
                            if scenario == "partial_target_fill":
                                order.quantity = -1000
                                order.filled_quantity = -300
                                order.status.value = "working"
                            else:
                                order.quantity = -1000
                                order.filled_quantity = 0
                                order.status.value = "working"
                            order.limit_price = 115.0
                        
                        results[symbol]["operations"].append(f"get_order_{order_id}")
                        break
                
                return order
            
            order_manager.get_order.side_effect = get_order_mock
            
            # Mock order operations
            async def cancel_order_mock(order_id, reason):
                for symbol in test_scenarios:
                    if symbol in order_id:
                        results[symbol]["operations"].append(f"cancel_{order_id}")
                        break
                return True
            
            async def create_order_mock(**kwargs):
                symbol = kwargs.get('symbol')
                if symbol:
                    results[symbol]["operations"].append(
                        f"create_{kwargs.get('order_type')}_{kwargs.get('quantity')}"
                    )
                order = MagicMock()
                order.order_id = f"new_order_{symbol}"
                return order
            
            order_manager.cancel_order.side_effect = cancel_order_mock
            order_manager.create_order.side_effect = create_order_mock
            
            # Mock position tracker for closure scenarios
            position_tracker = setup["position_tracker"]
            position_tracker.get_positions_for_symbol.return_value = [MagicMock(position_id="pos1")]
            
            # Create fill events based on scenarios
            fill_events = []
            
            for symbol, scenario in test_scenarios.items():
                if scenario == "double_down":
                    event = FillEvent(
                        order_id=f"dd_{symbol}",
                        symbol=symbol,
                        status=OrderStatus.FILLED,
                        fill_price=105.0,
                        fill_quantity=500,
                        cumulative_quantity=500,
                        remaining_quantity=0,
                        fill_time=datetime.now()
                    )
                elif scenario == "partial_target_fill":
                    event = FillEvent(
                        order_id=f"target_{symbol}",
                        symbol=symbol,
                        status=OrderStatus.PARTIALLY_FILLED,
                        fill_price=115.0,
                        fill_quantity=-300,
                        cumulative_quantity=-300,
                        remaining_quantity=-700,
                        fill_time=datetime.now()
                    )
                elif scenario == "full_stop_fill":
                    event = FillEvent(
                        order_id=f"stop_{symbol}",
                        symbol=symbol,
                        status=OrderStatus.FILLED,
                        fill_price=95.0,
                        fill_quantity=-1000,
                        cumulative_quantity=-1000,
                        remaining_quantity=0,
                        fill_time=datetime.now()
                    )
                elif scenario == "partial_stop_fill":
                    event = FillEvent(
                        order_id=f"stop_{symbol}",
                        symbol=symbol,
                        status=OrderStatus.PARTIALLY_FILLED,
                        fill_price=95.0,
                        fill_quantity=-400,
                        cumulative_quantity=-400,
                        remaining_quantity=-600,
                        fill_time=datetime.now()
                    )
                
                fill_events.append(event)
            
            # Fire all events concurrently
            tasks = [event_bus.emit(event) for event in fill_events]
            await asyncio.gather(*tasks)
            
            # Wait for processing
            await asyncio.sleep(1.5)
            
            # Analyze results
            logger.info(f"\n{'='*60}")
            logger.info("MIXED OPERATIONS TEST RESULTS")
            logger.info(f"{'='*60}")
            
            for symbol, scenario in test_scenarios.items():
                ops = results[symbol]["operations"]
                logger.info(f"\n{symbol} ({scenario}): {len(ops)} operations")
                
                if scenario == "double_down":
                    # Should update both protective orders
                    cancel_ops = [op for op in ops if "cancel" in op]
                    create_ops = [op for op in ops if "create" in op]
                    assert len(cancel_ops) == 2, f"{symbol}: Expected 2 cancels"
                    assert len(create_ops) == 2, f"{symbol}: Expected 2 creates"
                    
                elif scenario == "partial_target_fill":
                    # Should update only stop order
                    cancel_ops = [op for op in ops if "cancel_stop" in op]
                    create_ops = [op for op in ops if "create_OrderType.STOP" in op]
                    assert len(cancel_ops) == 1, f"{symbol}: Expected 1 stop cancel"
                    assert len(create_ops) == 1, f"{symbol}: Expected 1 stop create"
                    
                elif scenario == "full_stop_fill":
                    # Should close position
                    cancel_ops = [op for op in ops if "cancel" in op]
                    assert len(cancel_ops) >= 1, f"{symbol}: Expected order cancellations"
                    
                elif scenario == "partial_stop_fill":
                    # Should update only target order
                    cancel_ops = [op for op in ops if "cancel_target" in op]
                    create_ops = [op for op in ops if "create_OrderType.LIMIT" in op]
                    assert len(cancel_ops) == 1, f"{symbol}: Expected 1 target cancel"
                    assert len(create_ops) == 1, f"{symbol}: Expected 1 target create"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
 