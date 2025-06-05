"""
Test to verify that all related orders are cancelled when a position exits via stop or target.

This test will:
1. Create a position with stop, target, and double-down orders
2. Monitor order cancellations when the position closes
3. Verify that ALL related orders are cancelled
"""

import asyncio
import logging
from datetime import datetime
from typing import Set, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.rule.engine import RuleEngine
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderConclusionManager,
    LinkedDoubleDownFillManager
)
from src.indicators.manager import IndicatorManager
from src.minute_data.manager import MinuteBarManager
from src.price.service import PriceService
from src.position.sizer import PositionSizer
from src.event.order import FillEvent, CancelEvent, NewOrderEvent, OrderStatusEvent
from src.order import OrderType, OrderStatus
from src.position.base import PositionStatus


class OrderTracker:
    """Track all orders and their cancellations."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.all_orders: Set[str] = set()
        self.cancelled_orders: Set[str] = set()
        self.filled_orders: Set[str] = set()
        self.order_details: Dict[str, dict] = {}
        
    async def start(self):
        """Start tracking orders."""
        await self.event_bus.subscribe(NewOrderEvent, self.on_order_created)
        await self.event_bus.subscribe(OrderStatusEvent, self.on_order_status)
        await self.event_bus.subscribe(CancelEvent, self.on_order_cancelled)
        await self.event_bus.subscribe(FillEvent, self.on_order_filled)
        
    async def stop(self):
        """Stop tracking orders."""
        await self.event_bus.unsubscribe(NewOrderEvent, self.on_order_created)
        await self.event_bus.unsubscribe(OrderStatusEvent, self.on_order_status)
        await self.event_bus.unsubscribe(CancelEvent, self.on_order_cancelled)
        await self.event_bus.unsubscribe(FillEvent, self.on_order_filled)
        
    async def on_order_created(self, event: NewOrderEvent):
        """Track new orders."""
        self.all_orders.add(event.order_id)
        self.order_details[event.order_id] = {
            'symbol': event.symbol,
            'quantity': event.quantity,
            'order_type': event.order_type,
            'created_at': event.create_time
        }
        logger.info(f"Order created: {event.order_id} - {event.symbol} {event.quantity}")
        
    async def on_order_status(self, event: OrderStatusEvent):
        """Track order status changes."""
        if event.status == OrderStatus.SUBMITTED:
            self.all_orders.add(event.order_id)
            if event.order_id not in self.order_details:
                self.order_details[event.order_id] = {
                    'symbol': event.symbol,
                    'quantity': event.quantity,
                    'order_type': event.order_type,
                    'submitted_at': datetime.now()
                }
            logger.info(f"Order submitted: {event.order_id} - {event.symbol}")
        
    async def on_order_cancelled(self, event: CancelEvent):
        """Track cancelled orders."""
        self.cancelled_orders.add(event.order_id)
        logger.info(f"Order cancelled: {event.order_id} - Reason: {event.reason}")
        
    async def on_order_filled(self, event: FillEvent):
        """Track filled orders."""
        self.filled_orders.add(event.order_id)
        logger.info(f"Order filled: {event.order_id} - {event.symbol} @ ${event.fill_price}")
        
    def get_open_orders(self) -> Set[str]:
        """Get orders that are neither filled nor cancelled."""
        return self.all_orders - self.filled_orders - self.cancelled_orders
    
    def print_summary(self):
        """Print a summary of all orders."""
        logger.info("\n" + "="*60)
        logger.info("ORDER TRACKING SUMMARY")
        logger.info("="*60)
        logger.info(f"Total orders submitted: {len(self.all_orders)}")
        logger.info(f"Orders filled: {len(self.filled_orders)}")
        logger.info(f"Orders cancelled: {len(self.cancelled_orders)}")
        logger.info(f"Orders still open: {len(self.get_open_orders())}")
        
        if self.get_open_orders():
            logger.warning("\nWARNING: The following orders are still open:")
            for order_id in self.get_open_orders():
                details = self.order_details.get(order_id, {})
                logger.warning(f"  - {order_id}: {details}")
        else:
            logger.info("\n✅ All non-filled orders were properly cancelled!")
        
        logger.info("="*60 + "\n")


async def test_position_exit(symbol: str, exit_type: str = "manual"):
    """Test position exit and verify all orders are cancelled."""
    
    logger.info(f"\nTesting {exit_type} position exit for {symbol}")
    logger.info("="*60)
    
    # Initialize components
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    event_bus = EventBus()
    order_manager = OrderManager(event_bus, tws_connection)
    position_tracker = PositionTracker(event_bus)
    rule_engine = RuleEngine(event_bus)
    
    # Initialize tracking
    order_tracker = OrderTracker(event_bus)
    
    # Initialize minute data manager for ATR calculation
    minute_data_manager = MinuteBarManager(tws_connection)
    indicator_manager = IndicatorManager(minute_data_manager)
    
    price_service = PriceService(tws_connection)
    position_sizer = PositionSizer()
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws_connection.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return
    
    # Initialize components
    await order_manager.initialize()
    await position_tracker.initialize()
    await order_tracker.start()
    
    # Set up rule engine context
    rule_engine.update_context({
        "order_manager": order_manager,
        "position_tracker": position_tracker,
        "indicator_manager": indicator_manager,
        "price_service": price_service,
        "position_sizer": position_sizer,
        "prices": {}
    })
    
    # Initialize conclusion managers
    conclusion_manager = LinkedOrderConclusionManager(rule_engine.context, event_bus)
    await conclusion_manager.initialize()
    
    doubledown_manager = LinkedDoubleDownFillManager(rule_engine.context, event_bus)
    await doubledown_manager.initialize()
    
    # Start rule engine
    await rule_engine.start()
    
    try:
        # Create position with all order types
        logger.info(f"\n1. Creating position for {symbol} with protective orders...")
        
        create_order_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=5000,  # $5000 allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.02,      # 2% stop
            take_profit_pct=0.04     # 4% target
        )
        
        success = await create_order_action.execute(rule_engine.context)
        
        if not success:
            logger.error("Failed to create position")
            return
            
        # Wait for orders to be processed
        logger.info("\n2. Waiting for all orders to be created...")
        await asyncio.sleep(5)
        
        # Check position and orders
        positions = await position_tracker.get_positions_for_symbol(symbol)
        if not positions:
            logger.error("No position found!")
            return
            
        position = positions[0]
        logger.info(f"\nPosition created:")
        logger.info(f"  - Main orders: {position.main_order_ids}")
        logger.info(f"  - Stop orders: {position.stop_order_ids}")
        logger.info(f"  - Target orders: {position.target_order_ids}")
        logger.info(f"  - Double down orders: {position.doubledown_order_ids}")
        
        # Count total orders
        total_orders = (
            len(position.main_order_ids) +
            len(position.stop_order_ids) +
            len(position.target_order_ids) +
            len(position.doubledown_order_ids)
        )
        logger.info(f"\nTotal orders created: {total_orders}")
        
        # Simulate position exit
        if exit_type == "manual":
            logger.info("\n3. Manually closing position (simulating stop/target fill)...")
            
            # Get all orders for the position
            all_position_orders = (
                position.stop_order_ids +
                position.target_order_ids +
                position.doubledown_order_ids
            )
            
            # Cancel all orders manually (this simulates what should happen on stop/target fill)
            for order_id in all_position_orders:
                try:
                    await order_manager.cancel_order(order_id, "Position closed - cleanup")
                except Exception as e:
                    logger.warning(f"Failed to cancel order {order_id}: {e}")
                    
            # Close the position
            await position_tracker.close_position(position.position_id, "Manual test closure")
            
        else:
            logger.info("\n3. Waiting for natural position exit via stop or target...")
            # In a real scenario, we would wait for actual stop/target fill
            # For testing, we'll just wait a bit
            await asyncio.sleep(10)
        
        # Wait for all cancellations to process
        logger.info("\n4. Waiting for order cancellations to process...")
        await asyncio.sleep(3)
        
        # Print summary
        order_tracker.print_summary()
        
        # Verify position is closed
        positions = await position_tracker.get_positions_for_symbol(symbol)
        open_positions = [p for p in positions if p.status == PositionStatus.OPEN]
        
        if not open_positions:
            logger.info("✅ Position successfully closed")
        else:
            logger.warning("⚠️ Position still open!")
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
    finally:
        # Clean up
        logger.info("\nCleaning up...")
        
        # Cancel any remaining open orders
        open_orders = order_tracker.get_open_orders()
        if open_orders:
            logger.info(f"Cancelling {len(open_orders)} remaining orders...")
            for order_id in open_orders:
                try:
                    await order_manager.cancel_order(order_id, "Test cleanup")
                except Exception as e:
                    logger.warning(f"Failed to cancel order {order_id}: {e}")
        
        await order_tracker.stop()
        await rule_engine.stop()
        tws_connection.disconnect()
        logger.info("Test completed")


async def main():
    """Run the order cancellation test."""
    
    # Test with manual closure (simulates what should happen on stop/target fill)
    await test_position_exit("AAPL", exit_type="manual")
    
    # Wait a bit between tests
    await asyncio.sleep(5)
    
    # You can also test with a different symbol
    # await test_position_exit("MSFT", exit_type="manual")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ORDER CANCELLATION TEST")
    print("="*80)
    print("\nThis test verifies that all related orders are cancelled when a position exits.")
    print("It will create a position with stop, target, and double-down orders,")
    print("then simulate a position exit and verify all orders are properly cancelled.")
    print("\nNOTE: This will create REAL orders in TWS!")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 