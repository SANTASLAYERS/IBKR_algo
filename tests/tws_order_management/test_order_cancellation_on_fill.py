#!/usr/bin/env python3
"""
Test Order Cancellation on Stop/Target Fill
===========================================

This test verifies that when a stop or target order fills, all remaining
orders (including double down orders) are properly cancelled.
"""

import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderConclusionManager,
    LinkedDoubleDownFillManager
)
from src.rule.base import Rule
from src.order import OrderType
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.sizer import PositionSizer
from src.price.service import PriceService
from src.indicators.manager import IndicatorManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_order_cancellation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce IB API noise
logging.getLogger('ibapi').setLevel(logging.WARNING)


async def main():
    """Test order cancellation when stop/target fills."""
    logger.info("=" * 80)
    logger.info("Testing Order Cancellation on Stop/Target Fill")
    logger.info("=" * 80)
    
    # Initialize components
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    event_bus = EventBus()
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws_connection.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return
    
    # Initialize managers
    order_manager = OrderManager(event_bus, tws_connection)
    position_tracker = PositionTracker(event_bus)
    rule_engine = RuleEngine(event_bus)
    
    # Initialize additional services
    indicator_manager = IndicatorManager(
        minute_data_manager=tws_connection.minute_bar_manager
    )
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
    
    # Initialize LinkedDoubleDownFillManager
    doubledown_manager = LinkedDoubleDownFillManager(
        context=rule_engine.context,
        event_bus=event_bus
    )
    await doubledown_manager.initialize()
    
    # Create a buy rule for testing
    buy_condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": "SOXS",
            "signal": "BUY",
            "confidence": lambda c: c >= 0.5
        }
    )
    
    buy_action = LinkedCreateOrderAction(
        symbol="SOXS",
        quantity=100,  # Small test quantity
        side="BUY",
        order_type=OrderType.MARKET,
        auto_create_stops=True,
        atr_stop_multiplier=6.0,
        atr_target_multiplier=3.0
    )
    
    buy_rule = Rule(
        rule_id="test_buy_rule",
        name="Test Buy Rule",
        condition=buy_condition,
        action=buy_action
    )
    
    rule_engine.register_rule(buy_rule)
    await rule_engine.start()
    
    # Test 1: Create position with orders
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Creating position with stop, target, and double down orders")
    logger.info("=" * 60)
    
    # Emit buy signal
    buy_signal = PredictionSignalEvent(
        symbol="SOXS",
        signal="BUY",
        confidence=0.9,
        timestamp=datetime.now()
    )
    
    await event_bus.emit(buy_signal)
    
    # Wait for orders to be created
    await asyncio.sleep(3)
    
    # Check what orders were created
    context = rule_engine.context
    if "SOXS" in context:
        soxs_context = context["SOXS"]
        logger.info(f"\nSOXS Context:")
        logger.info(f"  Side: {soxs_context.get('side')}")
        logger.info(f"  Main orders: {soxs_context.get('main_orders', [])}")
        logger.info(f"  Stop orders: {soxs_context.get('stop_orders', [])}")
        logger.info(f"  Target orders: {soxs_context.get('target_orders', [])}")
        logger.info(f"  Double down orders: {soxs_context.get('doubledown_orders', [])}")
        
        # Count total orders
        total_orders = (
            len(soxs_context.get('main_orders', [])) +
            len(soxs_context.get('stop_orders', [])) +
            len(soxs_context.get('target_orders', [])) +
            len(soxs_context.get('doubledown_orders', []))
        )
        logger.info(f"\nTotal orders created: {total_orders}")
    else:
        logger.error("No SOXS context found!")
    
    # Test 2: Monitor for order fills
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Monitoring for stop/target fills...")
    logger.info("=" * 60)
    logger.info("MANUAL STEP: Please manually adjust the stop or target order in TWS")
    logger.info("to trigger a fill (e.g., change stop to market order)")
    logger.info("Waiting 30 seconds for manual intervention...")
    
    # Wait for manual intervention
    await asyncio.sleep(30)
    
    # Check if context was cleared after fill
    if "SOXS" in context:
        logger.warning("SOXS context still exists - position may not have concluded")
        soxs_context = context["SOXS"]
        logger.info(f"Remaining orders:")
        logger.info(f"  Stop orders: {soxs_context.get('stop_orders', [])}")
        logger.info(f"  Target orders: {soxs_context.get('target_orders', [])}")
        logger.info(f"  Double down orders: {soxs_context.get('doubledown_orders', [])}")
    else:
        logger.info("✅ SOXS context cleared - position concluded successfully!")
    
    # Cleanup
    logger.info("\n" + "=" * 60)
    logger.info("Test completed - cleaning up")
    logger.info("=" * 60)
    
    await rule_engine.stop()
    tws_connection.disconnect()
    logger.info("✅ Test completed")


if __name__ == "__main__":
    asyncio.run(main()) 