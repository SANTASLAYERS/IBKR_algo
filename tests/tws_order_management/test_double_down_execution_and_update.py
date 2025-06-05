"""
Test double down execution and protective order updates.

This test:
1. Goes long GLD with 10 ATR profit target and 5 ATR stop
2. Waits for the double down order to fill
3. Verifies that new stop and target orders are created with doubled quantity
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
    """Run the double down execution test."""
    
    logger.info("=" * 80)
    logger.info("DOUBLE DOWN EXECUTION AND UPDATE TEST")
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
        client_id=int(os.getenv("TWS_CLIENT_ID", "10"))
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
        logger.info("STEP 1: Going long GLD with 10 ATR profit and 5 ATR stop")
        logger.info("=" * 60)
        
        # Create long position with specified ATR multipliers
        create_action = LinkedCreateOrderAction(
            symbol="GLD",
            quantity=100,
            side="BUY",
            auto_create_stops=True,
            atr_stop_multiplier=5.0,      # Stop at 5 ATR
            atr_target_multiplier=10.0    # Target at 10 ATR
        )
        
        success = await create_action.execute(rule_engine.context)
        if not success:
            logger.error("Failed to create position")
            return
        
        # Wait for all orders to be created
        logger.info("Waiting for all orders to be created...")
        await asyncio.sleep(10)
        
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
        if not all([main_order, stop_order, target_order]):
            logger.error("Missing some orders!")
            logger.error(f"Main: {main_order is not None}, Stop: {stop_order is not None}, "
                        f"Target: {target_order is not None}")
            return
        
        # Log order details and verify ATR distances
        entry_price = main_order.avg_fill_price
        logger.info(f"\nMain order filled at: ${entry_price:.2f}")
        logger.info(f"Stop order at: ${stop_order.stop_price:.2f}")
        logger.info(f"Target order at: ${target_order.limit_price:.2f}")
        
        # Calculate actual ATR for GLD
        logger.info("\nCalculating actual ATR for GLD...")
        actual_atr = None
        try:
            actual_atr = await indicator_manager.get_atr(
                symbol="GLD",
                period=14,
                days=5,
                bar_size="10 secs"
            )
            if actual_atr:
                logger.info(f"✅ ATR for GLD: {actual_atr:.4f}")
            else:
                logger.warning("Failed to calculate ATR, will estimate from order distances")
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
        
        # Calculate and verify ATR distances
        stop_distance = abs(entry_price - stop_order.stop_price)
        target_distance = abs(target_order.limit_price - entry_price)
        
        if actual_atr:
            # Use actual ATR
            stop_atr_multiple = stop_distance / actual_atr
            target_atr_multiple = target_distance / actual_atr
            
            logger.info(f"\nATR-based distances (actual ATR={actual_atr:.4f}):")
            logger.info(f"  Stop: ${stop_distance:.2f} = {stop_atr_multiple:.1f} ATR")
            logger.info(f"  Target: ${target_distance:.2f} = {target_atr_multiple:.1f} ATR")
            
            # Verify ATR multiples are approximately correct
            if abs(stop_atr_multiple - 5.0) > 1.0:
                logger.warning(f"Stop ATR multiple {stop_atr_multiple:.1f} is not close to 5.0")
            else:
                logger.info("✅ Stop is correctly placed at ~5 ATR")
                
            if abs(target_atr_multiple - 10.0) > 1.0:
                logger.warning(f"Target ATR multiple {target_atr_multiple:.1f} is not close to 10.0")
            else:
                logger.info("✅ Target is correctly placed at ~10 ATR")
        else:
            # Estimate ATR from the stop distance (assuming stop is at 5 ATR)
            estimated_atr = stop_distance / 5.0
            logger.info(f"\nEstimated ATR from stop distance: {estimated_atr:.4f}")
            logger.info(f"  Stop: ${stop_distance:.2f} = 5.0 ATR (by definition)")
            logger.info(f"  Target: ${target_distance:.2f} = {target_distance/estimated_atr:.1f} ATR")
            actual_atr = estimated_atr  # Use for later calculations
        
        # Check if double down was auto-created
        if dd_order:
            logger.info(f"\nDouble down order at: ${dd_order.limit_price:.2f}")
            dd_distance = abs(entry_price - dd_order.limit_price)
            dd_position = dd_distance / stop_distance  # Position between entry and stop
            logger.info(f"Double down is {dd_position:.1%} of the way to stop")
        else:
            logger.info("\nNo double down order auto-created (this is normal)")
        
        # Store original order info
        original_stop_id = stop_order.order_id
        original_target_id = target_order.order_id
        original_stop_price = stop_order.stop_price
        original_target_price = target_order.limit_price
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Waiting for double down to fill")
        logger.info("=" * 60)
        
        if not dd_order:
            logger.info("No double down order found - test cannot continue")
            logger.info("This is expected if double down auto-creation is disabled")
            return
        
        logger.info(f"Waiting for double down at ${dd_order.limit_price:.2f} to fill...")
        logger.info("(In real market conditions, price would need to drop to this level)")
        
        # Wait for double down to fill (max 60 seconds)
        max_wait = 60
        start_time = asyncio.get_event_loop().time()
        while dd_order.status.value not in ["filled", "cancelled", "rejected"]:
            await asyncio.sleep(1)
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait:
                logger.warning(f"Double down didn't fill within {max_wait} seconds")
                logger.info("In a real test, you would need the market to move to the double down price")
                break
            
            # Log progress every 10 seconds
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                logger.info(f"Still waiting... ({int(elapsed)}s elapsed)")
        
        if dd_order.status.value != "filled":
            logger.info(f"Double down order status: {dd_order.status.value}")
            logger.info("Test incomplete - double down did not fill")
            return
        
        logger.info(f"✅ Double down filled at ${dd_order.avg_fill_price:.2f}!")
        
        # Wait for protective orders to be updated
        logger.info("\nWaiting for protective orders to be updated...")
        await asyncio.sleep(5)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Verifying protective orders were updated")
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
        
        # Verify old orders were cancelled
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
        
        # Verify new orders exist with correct quantities
        if new_stop_order and new_stop_order.order_id != original_stop_id:
            logger.info(f"\n✅ New stop order created: {new_stop_order.order_id}")
            logger.info(f"  Quantity: {abs(new_stop_order.quantity)} shares")
            logger.info(f"  Stop price: ${new_stop_order.stop_price:.2f}")
            
            # Verify quantity is doubled (200 shares)
            if abs(new_stop_order.quantity) == 200:
                logger.info("  ✅ Stop quantity correctly updated to 200 shares")
            else:
                logger.error(f"  ❌ Stop quantity is {abs(new_stop_order.quantity)}, expected 200")
        else:
            logger.error("❌ No new stop order found")
        
        if new_target_order and new_target_order.order_id != original_target_id:
            logger.info(f"\n✅ New target order created: {new_target_order.order_id}")
            logger.info(f"  Quantity: {abs(new_target_order.quantity)} shares")
            logger.info(f"  Limit price: ${new_target_order.limit_price:.2f}")
            
            # Verify quantity is doubled (200 shares)
            if abs(new_target_order.quantity) == 200:
                logger.info("  ✅ Target quantity correctly updated to 200 shares")
            else:
                logger.error(f"  ❌ Target quantity is {abs(new_target_order.quantity)}, expected 200")
        else:
            logger.error("❌ No new target order found")
        
        # Calculate and display new average price
        if dd_order.status.value == "filled":
            new_avg_price = (entry_price * 100 + dd_order.avg_fill_price * 100) / 200
            logger.info(f"\nNew average entry price: ${new_avg_price:.2f}")
            logger.info(f"  Original entry: ${entry_price:.2f} x 100 shares")
            logger.info(f"  Double down: ${dd_order.avg_fill_price:.2f} x 100 shares")
            
            # Verify stop/target distances are maintained
            if new_stop_order:
                new_stop_distance = abs(new_avg_price - new_stop_order.stop_price)
                new_stop_atr = new_stop_distance / actual_atr
                logger.info(f"\nNew stop distance: ${new_stop_distance:.2f} = {new_stop_atr:.1f} ATR")
            
            if new_target_order:
                new_target_distance = abs(new_target_order.limit_price - new_avg_price)
                new_target_atr = new_target_distance / actual_atr
                logger.info(f"New target distance: ${new_target_distance:.2f} = {new_target_atr:.1f} ATR")
        
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
            logger.info("✅ TEST PASSED: Protective orders were correctly updated with doubled quantities")
        else:
            logger.error("❌ TEST FAILED: Issues with protective order updates")
        
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