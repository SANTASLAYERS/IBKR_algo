"""
Test double down fill with protective order updates.

This test creates a position with:
- Double down very close to entry (0.01 ATR)
- Profit target far away (20 ATR)
- Stop loss at normal distance (6 ATR)

Then verifies that when double down fills, the stop and target orders are:
1. Cancelled (old ones)
2. Recreated with new quantities (200 shares instead of 100)
3. At correct prices based on new average entry
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
    """Run the double down fill update test."""
    
    logger.info("=" * 80)
    logger.info("DOUBLE DOWN FILL WITH PROTECTIVE ORDER UPDATE TEST")
    logger.info("=" * 80)
    
    # Import required modules
    from src.tws_connection import TWSConnection
    from src.tws_config import TWSConfig
    from src.event.bus import EventBus
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
        client_id=int(os.getenv("TWS_CLIENT_ID", "4"))
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
        logger.info("STEP 1: Creating position with close double down and far profit target")
        logger.info("=" * 60)
        
        # Create main position with:
        # - Stop at 6 ATR (normal)
        # - Target at 20 ATR (very far)
        # - Double down will be at 0.01 ATR (very close)
        create_action = LinkedCreateOrderAction(
            symbol="GLD",
            quantity=100,
            side="BUY",
            auto_create_stops=True,
            atr_stop_multiplier=6.0,      # Stop at 6 ATR
            atr_target_multiplier=20.0    # Target at 20 ATR (far away)
        )
        
        success = await create_action.execute(rule_engine.context)
        if not success:
            logger.error("Failed to create position")
            return
        
        # Wait for orders to be created
        await asyncio.sleep(5)
        
        # Verify protective orders exist before creating double down
        all_orders = await order_manager.get_orders_for_symbol("GLD")
        has_stop = any(o.order_type.value == "stop" for o in all_orders)
        has_target = any(o.order_type.value == "limit" and o.side.value == "sell" for o in all_orders)
        
        if not has_stop or not has_target:
            logger.error("Protective orders not created yet, waiting longer...")
            await asyncio.sleep(5)
            
            # Check again
            all_orders = await order_manager.get_orders_for_symbol("GLD")
            has_stop = any(o.order_type.value == "stop" for o in all_orders)
            has_target = any(o.order_type.value == "limit" and o.side.value == "sell" for o in all_orders)
            
            if not has_stop or not has_target:
                logger.error("Protective orders still not created!")
                return
        
        logger.info("✅ Protective orders created, proceeding with double down...")
        
        # Now create double down very close to entry
        logger.info("\nCreating double down order very close to entry...")
        dd_action = LinkedDoubleDownAction(
            symbol="GLD",
            distance_to_stop_multiplier=0.01,  # Only 1% of the way to stop (very close)
            quantity_multiplier=1.0,           # Same size as original
            level_name="doubledown1"
        )
        
        success = await dd_action.execute(rule_engine.context)
        if not success:
            logger.error("Failed to create double down order")
            return
        
        # Wait for double down to be created
        await asyncio.sleep(2)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Checking created orders")
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
            logger.error(f"Main: {main_order is not None}, Stop: {stop_order is not None}, "
                        f"Target: {target_order is not None}, DD: {dd_order is not None}")
            return
        
        # Log order details
        logger.info(f"\nMain order filled at: ${main_order.avg_fill_price:.2f}")
        logger.info(f"Stop order at: ${stop_order.stop_price:.2f}")
        logger.info(f"Target order at: ${target_order.limit_price:.2f}")
        logger.info(f"Double down order at: ${dd_order.limit_price:.2f}")
        
        # Calculate distances
        entry_price = main_order.avg_fill_price
        stop_distance = abs(entry_price - stop_order.stop_price)
        target_distance = abs(target_order.limit_price - entry_price)
        dd_distance = abs(entry_price - dd_order.limit_price)
        
        logger.info(f"\nDistances from entry (${entry_price:.2f}):")
        logger.info(f"  Stop: ${stop_distance:.2f} ({stop_distance/0.045:.1f} ATR)")
        logger.info(f"  Target: ${target_distance:.2f} ({target_distance/0.045:.1f} ATR)")
        logger.info(f"  Double down: ${dd_distance:.2f} ({dd_distance/0.045:.1f} ATR)")
        
        # Store original stop/target IDs and prices
        original_stop_id = stop_order.order_id
        original_target_id = target_order.order_id
        original_stop_price = stop_order.stop_price
        original_target_price = target_order.limit_price
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Waiting for double down to fill")
        logger.info("=" * 60)
        
        # Since double down is very close, it should fill quickly
        logger.info(f"Double down order at ${dd_order.limit_price:.2f} should fill soon...")
        
        # Wait for double down to fill
        max_wait = 30
        start_time = asyncio.get_event_loop().time()
        while dd_order.status.value not in ["filled", "cancelled", "rejected"]:
            await asyncio.sleep(0.5)
            if asyncio.get_event_loop().time() - start_time > max_wait:
                logger.warning("Double down didn't fill within 30 seconds")
                break
        
        if dd_order.status.value == "filled":
            logger.info(f"✅ Double down filled at ${dd_order.avg_fill_price:.2f}!")
        else:
            logger.warning(f"Double down status: {dd_order.status.value}")
        
        # Wait for protective orders to be updated
        logger.info("\nWaiting for protective orders to be updated...")
        await asyncio.sleep(5)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Checking if stop and target orders were updated")
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
        
        if stop_order.status.value == "cancelled":
            logger.info("✅ Original stop order was cancelled")
        else:
            logger.error("❌ Original stop order was NOT cancelled")
        
        if target_order.status.value == "cancelled":
            logger.info("✅ Original target order was cancelled")
        else:
            logger.error("❌ Original target order was NOT cancelled")
        
        # Check new orders
        if new_stop_order and new_stop_order.order_id != original_stop_id:
            logger.info(f"\n✅ New stop order created: {new_stop_order.order_id}")
            logger.info(f"  Quantity: {abs(new_stop_order.quantity)} shares")
            logger.info(f"  Stop price: ${new_stop_order.stop_price:.2f}")
            
            # Verify quantity is doubled
            if abs(new_stop_order.quantity) == 200:
                logger.info("  ✅ Quantity correctly updated to 200 shares")
            else:
                logger.error(f"  ❌ Quantity is {abs(new_stop_order.quantity)}, expected 200")
        else:
            logger.error("❌ No new stop order found")
        
        if new_target_order and new_target_order.order_id != original_target_id:
            logger.info(f"\n✅ New target order created: {new_target_order.order_id}")
            logger.info(f"  Quantity: {abs(new_target_order.quantity)} shares")
            logger.info(f"  Limit price: ${new_target_order.limit_price:.2f}")
            
            # Verify quantity is doubled
            if abs(new_target_order.quantity) == 200:
                logger.info("  ✅ Quantity correctly updated to 200 shares")
            else:
                logger.error(f"  ❌ Quantity is {abs(new_target_order.quantity)}, expected 200")
        else:
            logger.error("❌ No new target order found")
        
        # Calculate new average price and verify stop/target distances
        if dd_order.status.value == "filled":
            new_avg_price = (entry_price * 100 + dd_order.avg_fill_price * 100) / 200
            logger.info(f"\nNew average entry price: ${new_avg_price:.2f}")
            
            if new_stop_order:
                new_stop_distance = abs(new_avg_price - new_stop_order.stop_price)
                logger.info(f"New stop distance: ${new_stop_distance:.2f} ({new_stop_distance/0.045:.1f} ATR)")
            
            if new_target_order:
                new_target_distance = abs(new_target_order.limit_price - new_avg_price)
                logger.info(f"New target distance: ${new_target_distance:.2f} ({new_target_distance/0.045:.1f} ATR)")
        
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
            logger.info("✅ TEST PASSED: Protective orders were correctly updated after double down fill")
        else:
            logger.error("❌ TEST FAILED: Protective orders were not properly updated")
        
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