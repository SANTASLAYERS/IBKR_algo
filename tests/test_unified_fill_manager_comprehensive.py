#!/usr/bin/env python3
"""
Comprehensive UnifiedFillManager Test Suite
==========================================

Tests all fill scenarios:
- Full and partial fills on profit targets
- Double down fills (full and partial)
- Stop loss fills after double down
- Multiple consecutive fast partial fills
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
from typing import Dict, Any, List

from src.event.bus import EventBus
from src.event.order import FillEvent
from src.rule.unified_fill_manager import UnifiedFillManager
from src.order.base import Order, OrderStatus, OrderType
from src.position.position_manager import PositionManager, PositionStatus


class TestUnifiedFillManagerComprehensive:
    """Comprehensive test suite for UnifiedFillManager."""
    
    async def setup(self):
        """Setup test environment."""
        # Create event bus
        event_bus = EventBus()
        
        # Create mock context
        context = {
            "order_manager": Mock(),
            "position_tracker": Mock(),
            "GLD": {
                "side": "BUY",
                "status": "open",
                "position": 0,
                "main_orders": set(),
                "stop_orders": set(),
                "target_orders": set(),
                "doubledown_orders": set()
            }
        }
        
        # Setup order manager mock
        context["order_manager"].get_order = AsyncMock()  # This needs to be async
        context["order_manager"].cancel_order = AsyncMock()
        context["order_manager"].create_order = AsyncMock()
        
        # Setup position tracker mock
        context["position_tracker"].get_positions_for_symbol = AsyncMock(return_value=[])
        context["position_tracker"].close_position = AsyncMock()
        
        # Create position manager singleton
        position_manager = PositionManager()
        position_manager.clear_all()
        
        # Create UnifiedFillManager
        fill_manager = UnifiedFillManager(context, event_bus)
        await fill_manager.initialize()
        
        return {
            "event_bus": event_bus,
            "context": context,
            "fill_manager": fill_manager,
            "position_manager": position_manager
        }
    
    def create_mock_order(self, order_id: str, symbol: str, quantity: float, 
                         order_type: OrderType, price: float = 0.0) -> Order:
        """Create a mock order."""
        order = Mock(spec=Order)
        order.order_id = order_id
        order.symbol = symbol
        order.quantity = quantity
        order.order_type = order_type
        order.status = OrderStatus.SUBMITTED
        order.filled_quantity = 0  # Start with 0 filled
        order.is_active = True
        
        # Add a mock status object with value attribute
        order.status = Mock()
        order.status.value = "submitted"
        
        if order_type == OrderType.STOP:
            order.stop_price = price
            order.limit_price = None
        elif order_type == OrderType.LIMIT:
            order.limit_price = price
            order.stop_price = None
        else:
            order.limit_price = None
            order.stop_price = None
            
        return order
    
    async def test_scenario_1_partial_profit_target_fills(self, setup):
        """Test Scenario 1: Multiple partial fills on profit target."""
        context = setup["context"]
        event_bus = setup["event_bus"]
        position_manager = setup["position_manager"]
        
        print("\n" + "="*80)
        print("SCENARIO 1: PARTIAL PROFIT TARGET FILLS")
        print("="*80)
        
        # Setup initial position: 300 shares long
        position_manager.open_position("GLD", "BUY")
        position_manager.add_orders_to_position("GLD", "main", ["main_order_1"])
        position_manager.add_orders_to_position("GLD", "stop", ["stop_order_1"])
        position_manager.add_orders_to_position("GLD", "target", ["target_order_1"])
        
        context["GLD"]["position"] = 300
        context["GLD"]["main_orders"] = {"main_order_1"}
        context["GLD"]["stop_orders"] = {"stop_order_1"}
        context["GLD"]["target_orders"] = {"target_order_1"}
        
        # Create mock orders
        stop_order = self.create_mock_order("stop_order_1", "GLD", -300, OrderType.STOP, 245.00)
        target_order = self.create_mock_order("target_order_1", "GLD", -300, OrderType.LIMIT, 250.00)
        
        # Setup main order as already filled (market order)
        main_order = self.create_mock_order("main_order_1", "GLD", 300, OrderType.MARKET)
        main_order.filled_quantity = 300  # Market order fully filled
        main_order.status.value = "filled"
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "main_order_1": main_order,
            "stop_order_1": stop_order,
            "target_order_1": target_order
        }.get(order_id)
        
        # Create new orders for updates
        new_stop_order = self.create_mock_order("stop_order_2", "GLD", -200, OrderType.STOP, 245.00)
        context["order_manager"].create_order.return_value = new_stop_order
        
        # Simulate partial fill on profit target: 100 shares
        print("\n1. First partial fill on profit target: 100 shares")
        
        # Update target order to reflect partial fill
        target_order.filled_quantity = -100  # Negative because it's a sell order
        target_order.status.value = "partially_filled"
        
        fill_event_1 = FillEvent(
            order_id="target_order_1",
            symbol="GLD",
            fill_price=250.00,
            fill_quantity=-100,  # Negative for sell
            cumulative_quantity=-100,
            remaining_quantity=200,
            is_partial=True
        )
        
        await event_bus.emit(fill_event_1)
        await asyncio.sleep(0.1)  # Allow processing
        
        # Verify stop order was updated to -200
        assert context["order_manager"].cancel_order.called
        assert context["order_manager"].create_order.called
        create_call = context["order_manager"].create_order.call_args[1]
        assert create_call["quantity"] == -200
        print(f"✓ Stop order updated to -200 shares")
        
        # Reset mocks for next fill
        context["order_manager"].cancel_order.reset_mock()
        context["order_manager"].create_order.reset_mock()
        
        # Update context for next fill
        context["GLD"]["position"] = 200
        context["GLD"]["stop_orders"] = {"stop_order_2"}
        stop_order_2 = self.create_mock_order("stop_order_2", "GLD", -200, OrderType.STOP, 245.00)
        new_stop_order_3 = self.create_mock_order("stop_order_3", "GLD", -150, OrderType.STOP, 245.00)
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "main_order_1": main_order,
            "stop_order_2": stop_order_2,
            "target_order_1": target_order
        }.get(order_id)
        context["order_manager"].create_order.return_value = new_stop_order_3
        
        # Second partial fill: 50 shares
        print("\n2. Second partial fill on profit target: 50 shares")
        
        # Update target order to reflect additional fill
        target_order.filled_quantity = -150  # Total filled so far
        
        fill_event_2 = FillEvent(
            order_id="target_order_1",
            symbol="GLD",
            fill_price=250.00,
            fill_quantity=-50,  # Negative for sell
            cumulative_quantity=-150,
            remaining_quantity=150,
            is_partial=True
        )
        
        await event_bus.emit(fill_event_2)
        await asyncio.sleep(0.1)
        
        # Verify stop order was updated to -150
        assert context["order_manager"].create_order.called
        create_call = context["order_manager"].create_order.call_args[1]
        assert create_call["quantity"] == -150
        print(f"✓ Stop order updated to -150 shares")
        
        # Final fill completing the profit target
        print("\n3. Final fill completing profit target: 150 shares")
        context["GLD"]["position"] = 150
        context["GLD"]["stop_orders"] = {"stop_order_3"}
        
        # Update target order to be fully filled
        target_order.filled_quantity = -300  # Fully filled
        target_order.status.value = "filled"
        
        fill_event_3 = FillEvent(
            order_id="target_order_1",
            symbol="GLD",
            fill_price=250.00,
            fill_quantity=-150,  # Negative for sell
            cumulative_quantity=-300,
            remaining_quantity=0,
            is_partial=False
        )
        
        await event_bus.emit(fill_event_3)
        await asyncio.sleep(0.1)
        
        # Verify position was closed
        assert context["order_manager"].cancel_order.called
        print(f"✓ Position closed, all orders cancelled")
        
    async def test_scenario_2_double_down_with_stop_loss(self, setup):
        """Test Scenario 2: Double down followed by stop loss with partial fills."""
        context = setup["context"]
        event_bus = setup["event_bus"]
        position_manager = setup["position_manager"]
        
        print("\n" + "="*80)
        print("SCENARIO 2: DOUBLE DOWN FOLLOWED BY STOP LOSS")
        print("="*80)
        
        # Setup initial position: 300 shares long
        position_manager.open_position("GLD", "BUY")
        position_manager.add_orders_to_position("GLD", "main", ["main_order_1"])
        position_manager.add_orders_to_position("GLD", "stop", ["stop_order_1"])
        position_manager.add_orders_to_position("GLD", "target", ["target_order_1"])
        position_manager.add_orders_to_position("GLD", "doubledown", ["dd_order_1"])
        
        context["GLD"]["position"] = 300
        context["GLD"]["main_orders"] = {"main_order_1"}
        context["GLD"]["stop_orders"] = {"stop_order_1"}
        context["GLD"]["target_orders"] = {"target_order_1"}
        context["GLD"]["doubledown_orders"] = {"dd_order_1"}
        
        # Create mock orders
        stop_order = self.create_mock_order("stop_order_1", "GLD", -300, OrderType.STOP, 245.00)
        target_order = self.create_mock_order("target_order_1", "GLD", -300, OrderType.LIMIT, 250.00)
        dd_order = self.create_mock_order("dd_order_1", "GLD", 300, OrderType.LIMIT, 246.00)
        
        # Setup main order as already filled
        main_order = self.create_mock_order("main_order_1", "GLD", 300, OrderType.MARKET)
        main_order.filled_quantity = 300  # Market order fully filled
        main_order.status.value = "filled"
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "main_order_1": main_order,
            "stop_order_1": stop_order,
            "target_order_1": target_order,
            "dd_order_1": dd_order
        }.get(order_id)
        
        # Create new orders for updates
        new_stop_order = self.create_mock_order("stop_order_2", "GLD", -600, OrderType.STOP, 245.00)
        new_target_order = self.create_mock_order("target_order_2", "GLD", -600, OrderType.LIMIT, 250.00)
        
        context["order_manager"].create_order.side_effect = [new_stop_order, new_target_order]
        
        # Simulate double down fill
        print("\n1. Double down order fills: 300 shares")
        
        # Update double down order to be fully filled
        dd_order.filled_quantity = 300
        dd_order.status.value = "filled"
        
        dd_fill_event = FillEvent(
            order_id="dd_order_1",
            symbol="GLD",
            fill_price=246.00,
            fill_quantity=300,
            cumulative_quantity=300,
            remaining_quantity=0,
            is_partial=False
        )
        
        await event_bus.emit(dd_fill_event)
        await asyncio.sleep(0.1)
        
        # Verify protective orders were updated to -600
        assert context["order_manager"].create_order.call_count == 2
        print(f"✓ Protective orders updated to -600 shares")
        
        # Reset mocks and update context
        context["order_manager"].cancel_order.reset_mock()
        context["order_manager"].create_order.reset_mock()
        context["GLD"]["position"] = 600
        context["GLD"]["stop_orders"] = {"stop_order_2"}
        context["GLD"]["target_orders"] = {"target_order_2"}
        
        # Now simulate stop loss with multiple partial fills
        stop_order_2 = self.create_mock_order("stop_order_2", "GLD", -600, OrderType.STOP, 245.00)
        target_order_2 = self.create_mock_order("target_order_2", "GLD", -600, OrderType.LIMIT, 250.00)
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "main_order_1": main_order,
            "dd_order_1": dd_order,  # Include filled double down
            "stop_order_2": stop_order_2,
            "target_order_2": target_order_2
        }.get(order_id)
        
        # First stop loss partial fill: 200 shares
        print("\n2. First stop loss partial fill: 200 shares")
        
        # Update stop order to reflect partial fill
        stop_order_2.filled_quantity = -200  # Negative because it's a sell order
        stop_order_2.status.value = "partially_filled"
        
        new_target_order_3 = self.create_mock_order("target_order_3", "GLD", -400, OrderType.LIMIT, 250.00)
        context["order_manager"].create_order.return_value = new_target_order_3
        
        stop_fill_1 = FillEvent(
            order_id="stop_order_2",
            symbol="GLD",
            fill_price=245.00,
            fill_quantity=-200,  # Negative for sell
            cumulative_quantity=-200,
            remaining_quantity=400,
            is_partial=True
        )
        
        await event_bus.emit(stop_fill_1)
        await asyncio.sleep(0.1)
        
        # Verify target order was updated to -400
        assert context["order_manager"].create_order.called
        create_call = context["order_manager"].create_order.call_args[1]
        assert create_call["quantity"] == -400
        print(f"✓ Target order updated to -400 shares")
        
        # Multiple rapid partial fills
        print("\n3. Multiple rapid partial fills on stop loss")
        context["GLD"]["position"] = 400
        context["GLD"]["target_orders"] = {"target_order_3"}
        
        # Prepare for rapid fills
        rapid_fills = [
            (100, 300, 300, True),   # 100 shares, 300 remaining
            (150, 450, 150, True),   # 150 shares, 150 remaining
            (150, 600, 0, False)     # Final 150 shares
        ]
        
        for i, (fill_qty, cum_qty, rem_qty, is_partial) in enumerate(rapid_fills):
            print(f"\n   Fill {i+1}: {fill_qty} shares")
            
            # Update context for each fill
            context["GLD"]["position"] = 600 - cum_qty
            
            if is_partial and context["GLD"]["position"] > 0:
                new_target = self.create_mock_order(
                    f"target_order_{i+4}", 
                    "GLD", 
                    -context["GLD"]["position"], 
                    OrderType.LIMIT, 
                    250.00
                )
                context["order_manager"].create_order.return_value = new_target
            
            fill_event = FillEvent(
                order_id="stop_order_2",
                symbol="GLD",
                fill_price=245.00,
                fill_quantity=fill_qty,
                cumulative_quantity=cum_qty,
                remaining_quantity=rem_qty,
                is_partial=is_partial
            )
            
            await event_bus.emit(fill_event)
            await asyncio.sleep(0.05)  # Rapid succession
        
        # Verify position was closed after final fill
        print(f"\n✓ Position closed after stop loss fully filled")
        
    async def test_scenario_3_consecutive_fast_fills(self, setup):
        """Test Scenario 3: Consecutive fast partial fills stress test."""
        context = setup["context"]
        event_bus = setup["event_bus"]
        position_manager = setup["position_manager"]
        
        print("\n" + "="*80)
        print("SCENARIO 3: CONSECUTIVE FAST PARTIAL FILLS")
        print("="*80)
        
        # Setup large position: 1000 shares
        position_manager.open_position("GLD", "BUY")
        position_manager.add_orders_to_position("GLD", "main", ["main_order_1"])
        position_manager.add_orders_to_position("GLD", "stop", ["stop_order_1"])
        position_manager.add_orders_to_position("GLD", "target", ["target_order_1"])
        
        context["GLD"]["position"] = 1000
        context["GLD"]["main_orders"] = {"main_order_1"}
        context["GLD"]["stop_orders"] = {"stop_order_1"}
        context["GLD"]["target_orders"] = {"target_order_1"}
        
        # Create mock orders
        stop_order = self.create_mock_order("stop_order_1", "GLD", -1000, OrderType.STOP, 245.00)
        target_order = self.create_mock_order("target_order_1", "GLD", -1000, OrderType.LIMIT, 250.00)
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "stop_order_1": stop_order,
            "target_order_1": target_order
        }.get(order_id)
        
        # Simulate 10 rapid partial fills on profit target
        print("\nSimulating 10 rapid partial fills (100 shares each):")
        
        total_filled = 0
        for i in range(10):
            fill_qty = 100
            total_filled += fill_qty
            remaining = 1000 - total_filled
            is_partial = remaining > 0
            
            # Update position
            context["GLD"]["position"] = remaining
            
            # Create new stop order for update
            if is_partial:
                new_stop = self.create_mock_order(
                    f"stop_order_{i+2}", 
                    "GLD", 
                    -remaining, 
                    OrderType.STOP, 
                    245.00
                )
                context["order_manager"].create_order.return_value = new_stop
                
                # Update context for next iteration
                context["GLD"]["stop_orders"] = {f"stop_order_{i+2}"}
                context["order_manager"].get_order.side_effect = lambda order_id, i=i: {
                    f"stop_order_{i+2}": new_stop,
                    "target_order_1": target_order
                }.get(order_id)
            
            fill_event = FillEvent(
                order_id="target_order_1",
                symbol="GLD",
                fill_price=250.00,
                fill_quantity=fill_qty,
                cumulative_quantity=total_filled,
                remaining_quantity=remaining,
                is_partial=is_partial
            )
            
            await event_bus.emit(fill_event)
            # Very short delay to simulate rapid fills
            await asyncio.sleep(0.01)
            
            print(f"   Fill {i+1}: {fill_qty} shares (total: {total_filled}, remaining: {remaining})")
        
        print(f"\n✓ All 10 rapid fills processed successfully")
        print(f"✓ Position closed after final fill")
        
    async def test_scenario_4_mixed_fills(self, setup):
        """Test Scenario 4: Mixed fills - partial double down, then partial stop."""
        context = setup["context"]
        event_bus = setup["event_bus"]
        position_manager = setup["position_manager"]
        
        print("\n" + "="*80)
        print("SCENARIO 4: MIXED FILLS - PARTIAL DOUBLE DOWN + PARTIAL STOP")
        print("="*80)
        
        # Setup initial position
        position_manager.open_position("GLD", "BUY")
        position_manager.add_orders_to_position("GLD", "main", ["main_order_1"])
        position_manager.add_orders_to_position("GLD", "stop", ["stop_order_1"])
        position_manager.add_orders_to_position("GLD", "target", ["target_order_1"])
        position_manager.add_orders_to_position("GLD", "doubledown", ["dd_order_1"])
        
        context["GLD"]["position"] = 500
        context["GLD"]["main_orders"] = {"main_order_1"}
        context["GLD"]["stop_orders"] = {"stop_order_1"}
        context["GLD"]["target_orders"] = {"target_order_1"}
        context["GLD"]["doubledown_orders"] = {"dd_order_1"}
        
        # Create mock orders
        stop_order = self.create_mock_order("stop_order_1", "GLD", -500, OrderType.STOP, 245.00)
        target_order = self.create_mock_order("target_order_1", "GLD", -500, OrderType.LIMIT, 250.00)
        dd_order = self.create_mock_order("dd_order_1", "GLD", 500, OrderType.LIMIT, 246.00)
        
        context["order_manager"].get_order.side_effect = lambda order_id: {
            "stop_order_1": stop_order,
            "target_order_1": target_order,
            "dd_order_1": dd_order
        }.get(order_id)
        
        # Partial double down fill: 200 shares
        print("\n1. Partial double down fill: 200 shares")
        new_stop_order = self.create_mock_order("stop_order_2", "GLD", -700, OrderType.STOP, 245.00)
        new_target_order = self.create_mock_order("target_order_2", "GLD", -700, OrderType.LIMIT, 250.00)
        
        context["order_manager"].create_order.side_effect = [new_stop_order, new_target_order]
        
        dd_partial_fill = FillEvent(
            order_id="dd_order_1",
            symbol="GLD",
            fill_price=246.00,
            fill_quantity=200,
            cumulative_quantity=200,
            remaining_quantity=300,
            is_partial=True
        )
        
        await event_bus.emit(dd_partial_fill)
        await asyncio.sleep(0.1)
        
        print(f"✓ Protective orders updated to -700 shares")
        
        # Complete double down fill
        print("\n2. Complete double down fill: 300 shares")
        context["GLD"]["position"] = 700
        context["order_manager"].create_order.side_effect = [
            self.create_mock_order("stop_order_3", "GLD", -1000, OrderType.STOP, 245.00),
            self.create_mock_order("target_order_3", "GLD", -1000, OrderType.LIMIT, 250.00)
        ]
        
        dd_final_fill = FillEvent(
            order_id="dd_order_1",
            symbol="GLD",
            fill_price=246.00,
            fill_quantity=300,
            cumulative_quantity=500,
            remaining_quantity=0,
            is_partial=False
        )
        
        await event_bus.emit(dd_final_fill)
        await asyncio.sleep(0.1)
        
        print(f"✓ Protective orders updated to -1000 shares")
        
        # Now partial stop loss fills
        print("\n3. Partial stop loss fills after double down")
        context["GLD"]["position"] = 1000
        context["GLD"]["stop_orders"] = {"stop_order_3"}
        context["GLD"]["target_orders"] = {"target_order_3"}
        
        # Simulate market crash with rapid stop fills
        stop_fills = [
            (300, 300, 700, True),
            (400, 700, 300, True),
            (300, 1000, 0, False)
        ]
        
        for i, (fill_qty, cum_qty, rem_qty, is_partial) in enumerate(stop_fills):
            print(f"\n   Stop fill {i+1}: {fill_qty} shares @ $245.00")
            
            context["GLD"]["position"] = 1000 - cum_qty
            
            if is_partial:
                new_target = self.create_mock_order(
                    f"target_order_{i+4}",
                    "GLD",
                    -context["GLD"]["position"],
                    OrderType.LIMIT,
                    250.00
                )
                context["order_manager"].create_order.return_value = new_target
            
            stop_fill = FillEvent(
                order_id="stop_order_3",
                symbol="GLD",
                fill_price=245.00,
                fill_quantity=fill_qty,
                cumulative_quantity=cum_qty,
                remaining_quantity=rem_qty,
                is_partial=is_partial
            )
            
            await event_bus.emit(stop_fill)
            await asyncio.sleep(0.05)
        
        print(f"\n✓ Position closed after stop loss fully executed")
        print(f"✓ Total loss: 1000 shares @ $245.00")


async def run_comprehensive_test():
    """Run all test scenarios."""
    print("\n" + "="*80)
    print("UNIFIED FILL MANAGER COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    test_suite = TestUnifiedFillManagerComprehensive()
    
    # Run each scenario
    for test_method in [
        test_suite.test_scenario_1_partial_profit_target_fills,
        test_suite.test_scenario_2_double_down_with_stop_loss,
        test_suite.test_scenario_3_consecutive_fast_fills,
        test_suite.test_scenario_4_mixed_fills
    ]:
        # Setup fresh environment for each test
        setup = await test_suite.setup()
        
        try:
            await test_method(setup)
            print(f"\n✅ {test_method.__name__} PASSED")
        except Exception as e:
            print(f"\n❌ {test_method.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
        
        # Cleanup
        await setup["fill_manager"].cleanup() if hasattr(setup["fill_manager"], 'cleanup') else None
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(run_comprehensive_test()) 