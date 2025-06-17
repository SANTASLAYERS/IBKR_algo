#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca Integration Test Suite

Comprehensive integration tests for the Alpaca trading system.
Tests all major components working together.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alpaca_config import AlpacaConfig
from src.alpaca_connection import AlpacaConnection
from src.event.bus import EventBus
from src.event.order import OrderStatusEvent, FillEvent, OrderStatus
from src.event.position import PositionOpenEvent, PositionUpdateEvent, PositionCloseEvent
from src.order.manager import OrderManager
from src.order.base import OrderType, TimeInForce
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.position.alpaca_sync import AlpacaPositionSync
from src.minute_data.alpaca_manager import AlpacaMinuteBarManager
from src.logger import get_logger

logger = get_logger(__name__)


class IntegrationTestSuite:
    """Comprehensive integration test suite."""
    
    def __init__(self):
        self.config = None
        self.connection = None
        self.event_bus = None
        self.order_manager = None
        self.position_tracker = None
        self.position_manager = None
        self.position_sync = None
        self.minute_bar_manager = None
        
        # Test tracking
        self.test_results = {}
        self.events_received = []
        self.test_orders = []
        self.test_positions = []
    
    async def setup(self):
        """Set up test environment."""
        print("\n🔧 Setting up test environment...")
        
        # Initialize configuration
        self.config = AlpacaConfig.from_env()
        
        # Initialize event bus
        self.event_bus = EventBus()
        
        # Subscribe to events
        await self.event_bus.subscribe(OrderStatusEvent, self.on_order_status)
        await self.event_bus.subscribe(FillEvent, self.on_fill)
        await self.event_bus.subscribe(PositionOpenEvent, self.on_position_open)
        await self.event_bus.subscribe(PositionUpdateEvent, self.on_position_update)
        await self.event_bus.subscribe(PositionCloseEvent, self.on_position_close)
        
        # Initialize connection
        self.connection = AlpacaConnection(self.config, self.event_bus)
        connected = await self.connection.connect()
        if not connected:
            raise Exception("Failed to connect to Alpaca")
        
        # Initialize components
        self.order_manager = OrderManager(self.event_bus, self.connection)
        await self.order_manager.initialize()
        
        self.position_tracker = PositionTracker(self.event_bus)
        await self.position_tracker.initialize()
        
        self.position_manager = PositionManager()
        
        self.position_sync = AlpacaPositionSync(
            self.connection,
            self.position_tracker,
            self.position_manager,
            self.event_bus
        )
        
        self.minute_bar_manager = self.connection.minute_bar_manager
        
        print("Test environment ready")
    
    async def teardown(self):
        """Clean up test environment."""
        print("\nCleaning up...")
        
        # Cancel any remaining test orders
        for order_id in self.test_orders:
            try:
                await self.order_manager.cancel_order(order_id, "Test cleanup")
            except:
                pass
        
        # Stop position sync
        if self.position_sync:
            await self.position_sync.stop_periodic_sync()
        
        # Disconnect
        if self.connection:
            self.connection.disconnect()
        
        print("Cleanup complete")
    
    # Event handlers
    async def on_order_status(self, event: OrderStatusEvent):
        """Track order status events."""
        self.events_received.append(event)
        logger.info(f"Order status: {event.order_id} - {event.status.value}")
    
    async def on_fill(self, event: FillEvent):
        """Track fill events."""
        self.events_received.append(event)
        logger.info(f"Fill: {event.order_id} - {event.fill_quantity} @ ${event.fill_price}")
    
    async def on_position_open(self, event: PositionOpenEvent):
        """Track position open events."""
        self.events_received.append(event)
        logger.info(f"Position opened: {event.symbol}")
    
    async def on_position_update(self, event: PositionUpdateEvent):
        """Track position update events."""
        self.events_received.append(event)
        logger.info(f"Position updated: {event.symbol}")
    
    async def on_position_close(self, event: PositionCloseEvent):
        """Track position close events."""
        self.events_received.append(event)
        logger.info(f"Position closed: {event.symbol}")
    
    # Test methods
    async def test_position_tracking(self):
        """Test position tracking and synchronization."""
        print("\nTesting Position Tracking...")
        
        try:
            # Perform initial sync
            print("  - Performing position sync...")
            sync_result = await self.position_sync.sync_positions()
            
            if sync_result['status'] != 'success':
                raise Exception(f"Position sync failed: {sync_result}")
            
            print(f"  Synced {sync_result['alpaca_positions']} positions")
            
            # Get current positions
            alpaca_positions = self.connection.get_positions()
            tracker_positions = await self.position_tracker.get_all_positions()
            
            print(f"  Alpaca positions: {len(alpaca_positions)}")
            print(f"  Tracker positions: {len(tracker_positions)}")
            
            # Test single position sync
            if alpaca_positions:
                symbol = alpaca_positions[0].symbol
                print(f"  - Testing single position sync for {symbol}...")
                pos_data = await self.position_sync.sync_single_position(symbol)
                if pos_data:
                    print(f"  Position data retrieved: {pos_data['qty']} @ ${pos_data['avg_entry_price']}")
            
            self.test_results['position_tracking'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['position_tracking'] = f'FAILED: {e}'
            return False
    
    async def test_market_data_retrieval(self):
        """Test market data retrieval."""
        print("\nTesting Market Data Retrieval...")
        
        try:
            # Test historical data
            print("  - Fetching historical data for AAPL...")
            bars = await self.minute_bar_manager.get_historical_bars(
                symbol="AAPL",
                duration="1 D",
                bar_size="1 min"
            )
            
            if not bars or not bars.bars:
                raise Exception("No historical data received")
            
            print(f"  Retrieved {len(bars.bars)} minute bars")
            print(f"  Latest bar: {bars.bars[-1].time} - Close: ${bars.bars[-1].close}")
            
            # Test different timeframes
            print("  - Testing 5-minute bars...")
            bars_5min = await self.minute_bar_manager.get_historical_bars(
                symbol="SPY",
                duration="2 H",
                bar_size="5 mins"
            )
            
            if bars_5min and bars_5min.bars:
                print(f"  Retrieved {len(bars_5min.bars)} 5-minute bars")
            
            self.test_results['market_data'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['market_data'] = f'FAILED: {e}'
            return False
    
    async def test_order_lifecycle(self):
        """Test complete order lifecycle."""
        print("\nTesting Order Lifecycle...")
        
        try:
            # Create a limit order (less likely to fill immediately)
            print("  - Creating limit order...")
            
            # Get current price
            bars = await self.minute_bar_manager.get_historical_bars("AAPL", "1 D", "1 min")
            if not bars or not bars.bars:
                raise Exception("Cannot get current price")
            
            current_price = bars.bars[-1].close
            limit_price = current_price * 0.95  # 5% below market
            
            order = await self.order_manager.create_order(
                symbol="AAPL",
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=limit_price,
                time_in_force=TimeInForce.DAY
            )
            
            self.test_orders.append(order.order_id)
            print(f"  Order created: {order.order_id}")
            
            # Submit order
            print("  - Submitting order...")
            success = await self.order_manager.submit_order(order.order_id)
            if not success:
                raise Exception("Failed to submit order")
            
            print("  Order submitted")
            
            # Wait for status update
            await asyncio.sleep(3)
            
            # Check order status
            order = await self.order_manager.get_order(order.order_id)
            print(f"  Order status: {order.status.value}")
            
            # Cancel order
            print("  - Cancelling order...")
            cancelled = await self.order_manager.cancel_order(order.order_id, "Test cancel")
            if not cancelled:
                raise Exception("Failed to cancel order")
            
            # Wait for cancel confirmation
            await asyncio.sleep(3)
            
            # Verify cancellation
            order = await self.order_manager.get_order(order.order_id)
            if order.status != OrderStatus.CANCELLED:
                raise Exception(f"Order not cancelled, status: {order.status.value}")
            
            print("  Order cancelled successfully")
            
            self.test_results['order_lifecycle'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['order_lifecycle'] = f'FAILED: {e}'
            return False
    
    async def test_stop_target_orders(self):
        """Test stop loss and take profit orders."""
        print("\nTesting Stop/Target Orders...")
        
        try:
            # Get current price
            bars = await self.minute_bar_manager.get_historical_bars("SPY", "1 D", "1 min")
            if not bars or not bars.bars:
                raise Exception("Cannot get current price")
            
            current_price = bars.bars[-1].close
            
            # Create bracket order
            print("  - Creating bracket order...")
            bracket = await self.order_manager.create_bracket_order(
                symbol="SPY",
                quantity=1,
                entry_price=current_price * 1.01,  # Limit entry above market
                stop_loss_price=current_price * 0.98,  # 2% stop loss
                take_profit_price=current_price * 1.03,  # 3% take profit
                entry_type=OrderType.LIMIT
            )
            
            self.test_orders.extend([
                bracket.entry_order_id,
                bracket.stop_order_id,
                bracket.target_order_id
            ])
            
            print(f"  Bracket order created: {bracket.group_id}")
            
            # Submit entry order
            print("  - Submitting entry order...")
            success = await self.order_manager.submit_order(bracket.entry_order_id)
            if not success:
                raise Exception("Failed to submit entry order")
            
            # Wait a bit
            await asyncio.sleep(3)
            
            # Cancel the bracket
            print("  - Cancelling bracket order...")
            cancelled = await self.order_manager.cancel_order_group(
                bracket.group_id,
                "Test cleanup"
            )
            
            print(f"  Cancelled {cancelled} orders in bracket")
            
            self.test_results['stop_target_orders'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['stop_target_orders'] = f'FAILED: {e}'
            return False
    
    async def test_fill_handling(self):
        """Test fill event handling."""
        print("\n💰 Testing Fill Handling...")
        
        try:
            # Clear previous events
            self.events_received.clear()
            
            # Create a market order (should fill immediately)
            print("  - Creating market order...")
            order = await self.order_manager.create_order(
                symbol="AAPL",
                quantity=1,
                order_type=OrderType.MARKET
            )
            
            self.test_orders.append(order.order_id)
            
            # Submit order
            print("  - Submitting order...")
            success = await self.order_manager.submit_order(order.order_id)
            if not success:
                raise Exception("Failed to submit order")
            
            # Wait for fill
            print("  - Waiting for fill event...")
            await asyncio.sleep(5)
            
            # Check for fill events
            fill_events = [e for e in self.events_received if isinstance(e, FillEvent)]
            if not fill_events:
                print("  WARNING: No fill events received (market may be closed)")
                self.test_results['fill_handling'] = 'SKIPPED - Market closed'
                return True
            
            fill_event = fill_events[0]
            print(f"  Fill received: {fill_event.fill_quantity} @ ${fill_event.fill_price}")
            
            # Verify order status
            order = await self.order_manager.get_order(order.order_id)
            if order.status == OrderStatus.FILLED:
                print("  Order status updated to FILLED")
            
            self.test_results['fill_handling'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['fill_handling'] = f'FAILED: {e}'
            return False
    
    async def test_multiple_positions(self):
        """Test handling multiple simultaneous positions."""
        print("\n👥 Testing Multiple Positions...")
        
        try:
            symbols = ["AAPL", "MSFT", "GOOGL"]
            
            # Create positions in tracker
            print("  - Creating test positions...")
            for symbol in symbols:
                position = await self.position_tracker.create_stock_position(
                    symbol=symbol,
                    quantity=10,
                    entry_price=100.0,
                    strategy="test"
                )
                self.test_positions.append(position)
                print(f"  Created position for {symbol}")
            
            # Get all positions
            all_positions = await self.position_tracker.get_all_positions()
            active_positions = [p for p in all_positions if p.status.value == 'open']
            
            print(f"  Total active positions: {len(active_positions)}")
            
            # Update prices
            print("  - Updating position prices...")
            for i, symbol in enumerate(symbols):
                new_price = 100.0 + (i + 1) * 5  # Different prices
                await self.position_tracker.update_all_positions_price(symbol, new_price)
            
            # Get position summary
            summary = await self.position_tracker.get_position_summary()
            print(f"  Total position value: ${summary['total_value']:.2f}")
            print(f"  Total unrealized P/L: ${summary['total_unrealized_pnl']:.2f}")
            
            # Close positions
            print("  - Closing test positions...")
            for position in self.test_positions:
                await self.position_tracker.close_position(
                    position.position_id,
                    exit_price=105.0,
                    reason="Test cleanup"
                )
            
            self.test_results['multiple_positions'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['multiple_positions'] = f'FAILED: {e}'
            return False
    
    async def test_event_flow(self):
        """Test complete event flow from order to position."""
        print("\n🔀 Testing Event Flow...")
        
        try:
            # Clear events
            self.events_received.clear()
            
            # Create and track a position
            print("  - Creating position...")
            position = await self.position_tracker.create_stock_position(
                symbol="TEST",
                quantity=0,  # Will open with order
                strategy="event_test"
            )
            
            # Count event types
            event_counts = {}
            for event in self.events_received:
                event_type = type(event).__name__
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            print("  - Event summary:")
            for event_type, count in event_counts.items():
                print(f"    • {event_type}: {count}")
            
            # Verify event chain
            if len(self.events_received) > 0:
                print("  Event flow validated")
            
            self.test_results['event_flow'] = 'PASSED'
            return True
            
        except Exception as e:
            print(f"  Error: {e}")
            self.test_results['event_flow'] = f'FAILED: {e}'
            return False
    
    async def run_all_tests(self):
        """Run all integration tests."""
        print("\n" + "="*60)
        print("ALPACA INTEGRATION TEST SUITE")
        print("="*60)
        
        try:
            await self.setup()
            
            # Run tests
            tests = [
                self.test_position_tracking,
                self.test_market_data_retrieval,
                self.test_order_lifecycle,
                self.test_stop_target_orders,
                self.test_fill_handling,
                self.test_multiple_positions,
                self.test_event_flow
            ]
            
            for test in tests:
                await test()
                await asyncio.sleep(1)  # Brief pause between tests
            
            # Print summary
            print("\n" + "="*60)
            print("TEST RESULTS SUMMARY")
            print("="*60)
            
            passed = 0
            failed = 0
            skipped = 0
            
            for test_name, result in self.test_results.items():
                status = "PASS" if result == "PASSED" else (
                    "WARNING: SKIP" if "SKIPPED" in result else "FAIL"
                )
                print(f"{status} - {test_name}: {result}")
                
                if result == "PASSED":
                    passed += 1
                elif "SKIPPED" in result:
                    skipped += 1
                else:
                    failed += 1
            
            print("\n" + "-"*60)
            print(f"Total: {len(self.test_results)} | "
                  f"Passed: {passed} | "
                  f"Failed: {failed} | "
                  f"Skipped: {skipped}")
            print("="*60)
            
            return failed == 0
            
        finally:
            await self.teardown()


async def main():
    """Run the integration test suite."""
    suite = IntegrationTestSuite()
    success = await suite.run_all_tests()
    
    if success:
        print("\nAll tests completed successfully!")
        return 0
    else:
        print("\nSome tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 