#!/usr/bin/env python3
"""
Test Profit Target Fill Order Cancellation
==========================================

This test verifies that when a profit target fills, all remaining orders
(stop loss and double down) are properly cancelled.

We create REAL orders but SIMULATE the profit target fill to test the cancellation logic.
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
        logging.FileHandler('test_profit_fill_cancellation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce IB API noise
logging.getLogger('ibapi').setLevel(logging.WARNING)
logging.getLogger('ibapi.client').setLevel(logging.WARNING)
logging.getLogger('ibapi.wrapper').setLevel(logging.WARNING)


async def main():
    """Test profit target fill order cancellation."""
    logger.info("=" * 80)
    logger.info("PROFIT TARGET FILL CANCELLATION TEST")
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
    
    # Create buy rule for GLD with very tight profit target
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
        atr_target_multiplier=0.5  # Set target 0.5 ATR above current price
    )
    
    buy_rule = Rule(
        rule_id="gld_test_buy",
        name="GLD Test Buy",
        description="Test buy rule for GLD",
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
    
    # Count active orders before waiting for fill
    active_orders_before = len([o for o in gld_orders if o.is_active])
    logger.info(f"\nActive orders before fill: {active_orders_before}")
    
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Waiting for profit target to fill")
    logger.info("="*60)
    
    # Wait for the target order to fill naturally
    logger.info(f"Waiting for target order {target_order.order_id} to fill at ${target_order.limit_price}...")
    
    max_wait_time = 300  # Wait up to 5 minutes
    check_interval = 5   # Check every 5 seconds
    elapsed_time = 0
    
    while elapsed_time < max_wait_time:
        # Refresh order status
        target_order = await order_manager.get_order(target_order.order_id)
        if target_order and target_order.is_filled:
            logger.info(f"✅ Target order filled at ${target_order.avg_fill_price}!")
            break
        
        logger.info(f"Waiting... ({elapsed_time}s elapsed, order status: {target_order.status.value if target_order else 'unknown'})")
        await asyncio.sleep(check_interval)
        elapsed_time += check_interval
    
    if not target_order or not target_order.is_filled:
        logger.warning(f"⚠️ Target order did not fill within {max_wait_time} seconds")
        logger.info("Test incomplete - profit target did not fill naturally")
        await cleanup(tws_connection, rule_engine)
        return
    
    # Give LinkedOrderConclusionManager time to process the fill
    await asyncio.sleep(5)
    
    logger.info("\n" + "="*60)
    logger.info("STEP 4: Checking if stop and double down orders were cancelled")
    logger.info("="*60)
    
    # Check order statuses
    for order in stop_orders:
        order = await order_manager.get_order(order.order_id)  # Refresh order status
        if order:
            logger.info(f"Stop order {order.order_id} status: {order.status.value}")
            if order.status == "cancelled":
                logger.info("✅ Stop order was cancelled!")
            else:
                logger.error(f"❌ Stop order is still {order.status.value}")
    
    for order in doubledown_orders:
        order = await order_manager.get_order(order.order_id)  # Refresh order status
        if order:
            logger.info(f"Double down order {order.order_id} status: {order.status.value}")
            if order.status == "cancelled":
                logger.info("✅ Double down order was cancelled!")
            else:
                logger.error(f"❌ Double down order is still {order.status.value}")
    
    # Count active orders after
    gld_orders_after = await order_manager.get_orders_for_symbol("GLD")
    active_orders_after = len([o for o in gld_orders_after if o.is_active])
    logger.info(f"\nActive orders after fill: {active_orders_after}")
    
    # Check if TradeTracker was updated
    trade_tracker = TradeTracker()
    gld_trade = trade_tracker.get_active_trade("GLD")
    if gld_trade:
        logger.error("❌ TradeTracker still shows active trade for GLD")
    else:
        logger.info("✅ TradeTracker correctly shows no active trade for GLD")
    
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