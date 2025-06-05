"""
Test double down fill with manual fill simulation.

This test creates a position with stop and target orders,
then manually simulates a double down fill to verify that
protective orders are updated correctly.
"""

import asyncio
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress some noisy loggers
logging.getLogger('ibapi.client').setLevel(logging.WARNING)
logging.getLogger('ibapi.wrapper').setLevel(logging.WARNING)


async def main():
    """Run the double down fill manual test."""
    
    logger.info("=" * 80)
    logger.info("DOUBLE DOWN FILL MANUAL TEST")
    logger.info("=" * 80)
    
    # Import required modules
    from src.tws_connection import TWSConnection
    from src.tws_config import TWSConfig
    from src.event.bus import EventBus
    from src.event.order import FillEvent
    from src.order.manager import OrderManager
    from src.position.tracker import PositionTracker
    from src.rule.engine import RuleEngine
    from src.rule.linked_order_actions import (
        LinkedCreateOrderAction, 
        LinkedOrderConclusionManager,
        LinkedDoubleDownAction,
        LinkedDoubleDownFillManager
    )
    from src.position.position_manager import PositionManager
    from src.indicators.manager import IndicatorManager
    
    # Create event bus
    event_bus = EventBus()
    
    # Create TWS connection
    config = TWSConfig(
        host="127.0.0.1",
        port=7497,
        client_id=int(os.getenv("TWS_CLIENT_ID", "8"))
    )
    
    tws = TWSConnection(config)
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return
    
    logger.info("✅ Connected to TWS")
    
    # Create managers
    order_manager = OrderManager(event_bus, tws)
    await order_manager.initialize()
    
    position_tracker = PositionTracker(event_bus)
    await position_tracker.initialize()
    
    # Create rule engine with context
    rule_engine = RuleEngine(event_bus)
    rule_engine.context.update({
        "order_manager": order_manager,
        "position_tracker": position_tracker,
        "prices": {"GLD": 308.50}  # Current price
    })
    
    # Add indicator manager for ATR calculation
    indicator_manager = IndicatorManager(minute_data_manager=tws.minute_bar_manager)
    rule_engine.context["indicator_manager"] = indicator_manager
    
    # Initialize LinkedOrderConclusionManager
    conclusion_manager = LinkedOrderConclusionManager(rule_engine.context, event_bus)
    await conclusion_manager.initialize()
    
    # Initialize LinkedDoubleDownFillManager
    dd_fill_manager = LinkedDoubleDownFillManager(rule_engine.context, event_bus)
    await dd_fill_manager.initialize()
    
    # Start rule engine
    await rule_engine.start()
    
    try:
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: Creating position with stop and target orders")
        logger.info("=" * 60)
        
        # Create main position with normal ATR-based stops
        create_action = LinkedCreateOrderAction(
            symbol="GLD",
            quantity=100,
            side="BUY",
            auto_create_stops=True,
            atr_stop_multiplier=6.0,      # Stop at 6 ATR
            atr_target_multiplier=10.0    # Target at 10 ATR (far away)
        )
        
        success = await create_action.execute(rule_engine.context)
        if not success:
            logger.error("Failed to create position")
            return
        
        # Wait for all orders to be created
        await asyncio.sleep(10)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Creating double down order")
        logger.info("=" * 60)
        
        # Create double down order manually
        dd_action = LinkedDoubleDownAction(
            symbol="GLD",
            distance_to_stop_multiplier=0.5,  # Halfway to stop
            quantity_multiplier=1.0,          # Same size as original
            level_name="doubledown1"
        )
        
        success = await dd_action.execute(rule_engine.context)
        if not success:
            logger.error("Failed to create double down order")
            return
        
        # Wait for double down to be created
        await asyncio.sleep(2)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Checking created orders")
        logger.info("=" * 60)
        
        # Get all orders for the symbol
        all_orders = await order_manager.get_orders_for_symbol("GLD")
        logger.info(f"Found {len(all_orders)} orders for GLD")
        
        # Categorize orders
        main_order = None
        stop_order = None
        target_order = None
        dd_order = None
        
        for order in all_orders:
            logger.info(f"Order {order.order_id}: {order.order_type.value} {order.side.value} "
                       f"{abs(order.quantity)} @ "
                       f"{order.limit_price or order.stop_price or 'MARKET'} - "
                       f"Status: {order.status.value}")
            
            if order.order_type.value == "market" and order.side.value == "buy":
                main_order = order
            elif order.order_type.value == "stop":
                stop_order = order
            elif order.order_type.value == "limit" and order.side.value == "sell":
                target_order = order
            elif order.order_type.value == "limit" and order.side.value == "buy" and order.status.value in ["submitted", "accepted"]:
                dd_order = order
        
        # Verify we have all orders
        if not all([main_order, stop_order, target_order, dd_order]):
            logger.error("Missing some orders!")
            return
        
        # Store original stop/target info
        original_stop_id = stop_order.order_id
        original_target_id = target_order.order_id
        original_stop_quantity = abs(stop_order.quantity)
        original_target_quantity = abs(target_order.quantity)
        
        logger.info(f"\nOriginal orders:")
        logger.info(f"  Stop: {original_stop_quantity} shares @ ${stop_order.stop_price:.2f}")
        logger.info(f"  Target: {original_target_quantity} shares @ ${target_order.limit_price:.2f}")
        logger.info(f"  Double down: {abs(dd_order.quantity)} shares @ ${dd_order.limit_price:.2f}")
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Manually simulating double down fill")
        logger.info("=" * 60)
        
        # Manually emit a FillEvent for the double down order
        dd_fill_event = FillEvent(
            order_id=dd_order.order_id,
            symbol="GLD",
            status=dd_order.status,
            fill_price=dd_order.limit_price,  # Fill at limit price
            fill_quantity=dd_order.quantity,
            cumulative_quantity=dd_order.quantity,
            remaining_quantity=0,
            fill_time=datetime.now()
        )
        
        logger.info(f"Emitting manual fill event for double down order {dd_order.order_id}")
        await event_bus.emit(dd_fill_event)
        
        # Wait for LinkedDoubleDownFillManager to process
        logger.info("Waiting for protective orders to be updated...")
        await asyncio.sleep(5)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 5: Checking if stop and target orders were updated")
        logger.info("=" * 60)
        
        # Get updated orders
        all_orders = await order_manager.get_orders_for_symbol("GLD")
        
        # Find new stop and target orders
        new_stop_order = None
        new_target_order = None
        
        for order in all_orders:
            if order.order_type.value == "stop" and order.status.value in ["submitted", "accepted"]:
                new_stop_order = order
            elif order.order_type.value == "limit" and order.side.value == "sell" and order.status.value in ["submitted", "accepted"]:
                new_target_order = order
        
        # Check if old orders were cancelled
        logger.info(f"\nOriginal stop order {original_stop_id} status: {stop_order.status.value}")
        logger.info(f"Original target order {original_target_id} status: {target_order.status.value}")
        
        # Check new orders
        if new_stop_order and new_stop_order.order_id != original_stop_id:
            logger.info(f"\n✅ New stop order created: {new_stop_order.order_id}")
            logger.info(f"  Quantity: {abs(new_stop_order.quantity)} shares (was {original_stop_quantity})")
            logger.info(f"  Stop price: ${new_stop_order.stop_price:.2f}")
            
            if abs(new_stop_order.quantity) == 200:
                logger.info("  ✅ Quantity correctly doubled to 200 shares")
        
        if new_target_order and new_target_order.order_id != original_target_id:
            logger.info(f"\n✅ New target order created: {new_target_order.order_id}")
            logger.info(f"  Quantity: {abs(new_target_order.quantity)} shares (was {original_target_quantity})")
            logger.info(f"  Limit price: ${new_target_order.limit_price:.2f}")
            
            if abs(new_target_order.quantity) == 200:
                logger.info("  ✅ Quantity correctly doubled to 200 shares")
        
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        # Determine if test passed
        test_passed = (
            stop_order.status.value == "cancelled" and
            target_order.status.value == "cancelled" and
            new_stop_order is not None and
            new_target_order is not None and
            abs(new_stop_order.quantity) == 200 and
            abs(new_target_order.quantity) == 200
        )
        
        if test_passed:
            logger.info("✅ TEST PASSED: Protective orders were correctly updated after manual double down fill")
        else:
            logger.error("❌ TEST FAILED: Protective orders were not properly updated")
            if stop_order.status.value != "cancelled":
                logger.error("  - Original stop order not cancelled")
            if target_order.status.value != "cancelled":
                logger.error("  - Original target order not cancelled")
            if not new_stop_order:
                logger.error("  - No new stop order found")
            if not new_target_order:
                logger.error("  - No new target order found")
        
    finally:
        logger.info("\n" + "=" * 60)
        logger.info("TEST COMPLETE")
        logger.info("=" * 60)
        
        # Cancel all remaining orders
        logger.info("\nCancelling all remaining orders for cleanup...")
        cancelled = await order_manager.cancel_all_orders("GLD", "Test cleanup")
        logger.info(f"Cancelled {cancelled} orders")
        
        # Cleanup
        logger.info("\nCleaning up...")
        await rule_engine.stop()
        tws.disconnect()
        logger.info("✅ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main()) 