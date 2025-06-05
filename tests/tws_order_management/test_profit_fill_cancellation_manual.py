#!/usr/bin/env python3
"""
Test Profit Target Fill Order Cancellation with Manual Fill
==========================================================

This test verifies that when a profit target fills, all remaining orders
(stop loss and double down) are properly cancelled.

We create REAL orders with profit target 1 ATR away, then manually emit
a FillEvent to test the cancellation logic.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.event.order import FillEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderConclusionManager
)
from src.rule.base import Rule
from src.order import OrderType, OrderStatus
from src.order.base import OrderSide
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.sizer import PositionSizer
from src.price.service import PriceService
from src.indicators.manager import IndicatorManager
from src.trade_tracker import TradeTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_profit_fill_cancellation_manual.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce IB API noise
logging.getLogger('ibapi').setLevel(logging.WARNING)
logging.getLogger('ibapi.client').setLevel(logging.WARNING)
logging.getLogger('ibapi.wrapper').setLevel(logging.WARNING)


async def main():
    """Test profit target fill order cancellation with manual fill."""
    logger.info("=" * 80)
    logger.info("PROFIT TARGET FILL CANCELLATION TEST (MANUAL FILL)")
    logger.info("=" * 80)
    
    # Initialize components
    event_bus = EventBus()
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws_connection.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return
    logger.info("✅ Connected to TWS")
    
    # Initialize managers
    order_manager = OrderManager(event_bus, tws_connection)
    position_tracker = PositionTracker(event_bus)
    rule_engine = RuleEngine(event_bus)
    
    # Initialize services
    indicator_manager = IndicatorManager(minute_data_manager=tws_connection.minute_bar_manager)
    price_service = PriceService(tws_connection)
    position_sizer = PositionSizer(min_shares=1, max_shares=10000)
    
    await order_manager.initialize()
    await position_tracker.initialize()
    
    # Setup rule engine context
    rule_engine.update_context({
        "order_manager": order_manager,
        "position_tracker": position_tracker,
        "indicator_manager": indicator_manager,
        "price_service": price_service,
        "position_sizer": position_sizer,
        "account": {"equity": 100000},
        "prices": {}
    })
    
    # Initialize LinkedOrderConclusionManager
    conclusion_manager = LinkedOrderConclusionManager(
        context=rule_engine.context,
        event_bus=event_bus
    )
    await conclusion_manager.initialize()
    
    # Create buy rule for GLD with profit target 1 ATR away
    buy_condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": "GLD",
            "signal": "BUY"
        }
    )
    
    buy_action = LinkedCreateOrderAction(
        symbol="GLD",
        quantity=100,  # Small quantity for testing
        side="BUY",
        order_type=OrderType.MARKET,
        auto_create_stops=True,
        atr_stop_multiplier=6.0,
        atr_target_multiplier=1.0  # Set target 1 ATR above current price
    )
    
    buy_rule = Rule(
        rule_id="gld_test_buy",
        name="GLD Test Buy",
        description="Test buy rule for GLD with 1 ATR profit target",
        condition=buy_condition,
        action=buy_action,
        priority=100
    )
    
    rule_engine.register_rule(buy_rule)
    await rule_engine.start()
    
    # Trigger buy signal
    logger.info("\n" + "="*60)
    logger.info("STEP 1: Creating position with stop, target, and double down orders")
    logger.info("="*60)
    
    buy_signal = PredictionSignalEvent(
        symbol="GLD",
        signal="BUY",
        confidence=0.9,
        timestamp=datetime.now()
    )
    await event_bus.emit(buy_signal)
    
    # Wait for orders to be created
    await asyncio.sleep(10)
    
    # Check what orders were created
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Checking created orders")
    logger.info("="*60)
    
    # Get all orders for GLD from OrderManager
    gld_orders = await order_manager.get_orders_for_symbol("GLD")
    
    logger.info(f"Found {len(gld_orders)} orders for GLD")
    
    # Categorize orders by type
    main_orders = []
    stop_orders = []
    target_orders = []
    doubledown_orders = []
    
    for order in gld_orders:
        logger.info(f"Order {order.order_id}: {order.order_type.value} {order.side.value} {order.quantity} @ {order.limit_price or order.stop_price or 'MARKET'} - Status: {order.status.value}")
        
        if order.order_type == OrderType.MARKET and order.side == OrderSide.BUY:
            main_orders.append(order)
        elif order.order_type == OrderType.STOP:
            stop_orders.append(order)
        elif order.order_type == OrderType.LIMIT and order.side == OrderSide.SELL:
            target_orders.append(order)
        elif order.order_type == OrderType.LIMIT and order.side == OrderSide.BUY and order.is_active:
            doubledown_orders.append(order)
    
    logger.info(f"\nMain orders: {len(main_orders)}")
    logger.info(f"Stop orders: {len(stop_orders)}")
    logger.info(f"Target orders: {len(target_orders)}")
    logger.info(f"Double down orders: {len(doubledown_orders)}")
    
    if not target_orders:
        logger.error("❌ No target orders found!")
        await cleanup(tws_connection, rule_engine)
        return
    
    # Get the target order
    target_order = target_orders[0]
    
    logger.info(f"\nTarget order details:")
    logger.info(f"  ID: {target_order.order_id}")
    logger.info(f"  Status: {target_order.status.value}")
    logger.info(f"  Limit price: {target_order.limit_price}")
    
    # Count active orders before manual fill
    active_orders_before = len([o for o in gld_orders if o.is_active])
    logger.info(f"\nActive orders before manual fill: {active_orders_before}")
    
    # Verify target order is still active (not filled)
    if target_order.is_filled:
        logger.warning("⚠️ Target order already filled! This test expects it to be unfilled.")
    else:
        logger.info("✅ Target order is active and unfilled (as expected)")
    
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Manually emitting FillEvent for profit target")
    logger.info("="*60)
    
    # Create a manual fill event for the target order
    logger.info(f"Creating manual FillEvent for target order {target_order.order_id}")
    
    fill_event = FillEvent(
        order_id=target_order.order_id,
        symbol="GLD",
        fill_price=target_order.limit_price or 311.50,  # Use actual limit price
        fill_quantity=100,
        cumulative_quantity=100,
        remaining_quantity=0,
        fill_time=datetime.now()
    )
    
    logger.info(f"Emitting FillEvent: order_id={fill_event.order_id}, price=${fill_event.fill_price}")
    await event_bus.emit(fill_event)
    
    # Give LinkedOrderConclusionManager time to process the fill
    logger.info("Waiting for LinkedOrderConclusionManager to process the fill...")
    await asyncio.sleep(5)
    
    logger.info("\n" + "="*60)
    logger.info("STEP 4: Checking if stop and double down orders were cancelled")
    logger.info("="*60)
    
    # Check order statuses
    cancelled_count = 0
    
    for order in stop_orders:
        order = await order_manager.get_order(order.order_id)  # Refresh order status
        if order:
            logger.info(f"Stop order {order.order_id} status: {order.status.value}")
            if order.status.value == "cancelled" or order.status.value == "pending_cancel":
                logger.info("✅ Stop order was cancelled!")
                cancelled_count += 1
            else:
                logger.error(f"❌ Stop order is still {order.status.value}")
    
    for order in doubledown_orders:
        order = await order_manager.get_order(order.order_id)  # Refresh order status
        if order:
            logger.info(f"Double down order {order.order_id} status: {order.status.value}")
            if order.status.value == "cancelled" or order.status.value == "pending_cancel":
                logger.info("✅ Double down order was cancelled!")
                cancelled_count += 1
            else:
                logger.error(f"❌ Double down order is still {order.status.value}")
    
    # Count active orders after
    gld_orders_after = await order_manager.get_orders_for_symbol("GLD")
    active_orders_after = len([o for o in gld_orders_after if o.is_active])
    logger.info(f"\nActive orders after manual fill: {active_orders_after}")
    logger.info(f"Orders cancelled: {cancelled_count}")
    
    # Check if TradeTracker was updated
    trade_tracker = TradeTracker()
    gld_trade = trade_tracker.get_active_trade("GLD")
    if gld_trade:
        logger.error("❌ TradeTracker still shows active trade for GLD")
    else:
        logger.info("✅ TradeTracker correctly shows no active trade for GLD")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    if cancelled_count == len(stop_orders) + len(doubledown_orders) and not gld_trade:
        logger.info("✅ TEST PASSED: All protective orders were cancelled after manual fill")
    else:
        logger.error("❌ TEST FAILED: Some orders were not cancelled properly")
    
    logger.info("\n" + "="*60)
    logger.info("TEST COMPLETE")
    logger.info("="*60)
    
    # Cancel all remaining orders for cleanup
    logger.info("\nCancelling all remaining orders for cleanup...")
    cancelled = await order_manager.cancel_all_orders("GLD", "Test cleanup")
    logger.info(f"Cancelled {cancelled} orders")
    
    await cleanup(tws_connection, rule_engine)


async def cleanup(tws_connection, rule_engine):
    """Clean up resources."""
    logger.info("\nCleaning up...")
    await rule_engine.stop()
    if tws_connection.is_connected():
        tws_connection.disconnect()
    logger.info("✅ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main()) 