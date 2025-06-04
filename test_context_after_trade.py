#!/usr/bin/env python3
"""
Test Context After Trade
========================

This test will:
1. Connect to TWS
2. Place a BUY order for SLV
3. Wait for order to fill
4. Examine the context to see what's stored
5. Display all context information
"""

import asyncio
import logging
import os
import json
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.action import CreateOrderAction
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedOrderConclusionManager, LinkedDoubleDownFillManager
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
        logging.FileHandler('test_context.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def print_context(context: dict, title: str = "CONTEXT STATE"):
    """Pretty print the context."""
    logger.info("\n" + "="*80)
    logger.info(f"{title}")
    logger.info("="*80)
    
    # Print each key in the context
    for key, value in context.items():
        if key in ['order_manager', 'position_tracker', 'indicator_manager', 'price_service', 'position_sizer']:
            # Just show the type for manager objects
            logger.info(f"{key}: <{type(value).__name__} object>")
        elif key == 'account':
            logger.info(f"{key}: {json.dumps(value, indent=2)}")
        elif key == 'prices':
            logger.info(f"{key}: {value}")
        elif isinstance(value, dict):
            # For symbol-specific context
            logger.info(f"\n{key}:")
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    logger.info(f"  {sub_key}: {sub_value}")
                elif isinstance(sub_value, dict):
                    logger.info(f"  {sub_key}:")
                    for k, v in sub_value.items():
                        logger.info(f"    {k}: {v}")
                else:
                    logger.info(f"  {sub_key}: {sub_value}")
        else:
            logger.info(f"{key}: {value}")
    
    logger.info("="*80 + "\n")


async def test_context_after_trade():
    """Test context state after placing a trade."""
    logger.info("Starting context test...")
    
    # Create event bus
    event_bus = EventBus()
    
    # Setup TWS connection
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws_connection.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return False
    logger.info("✅ Connected to TWS")
    
    # Initialize components
    order_manager = OrderManager(event_bus, tws_connection)
    position_tracker = PositionTracker(event_bus)
    rule_engine = RuleEngine(event_bus)
    indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
    price_service = PriceService(tws_connection)
    position_sizer = PositionSizer(min_shares=1, max_shares=10000)
    
    # Initialize components
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
    
    # Initialize managers
    conclusion_manager = LinkedOrderConclusionManager(
        context=rule_engine.context,
        event_bus=event_bus
    )
    await conclusion_manager.initialize()
    
    doubledown_manager = LinkedDoubleDownFillManager(
        context=rule_engine.context,
        event_bus=event_bus
    )
    await doubledown_manager.initialize()
    
    # Print initial context
    print_context(rule_engine.context, "INITIAL CONTEXT (before any trades)")
    
    try:
        # Create a BUY rule for SLV
        buy_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": "SLV",
                "signal": "BUY",
                "confidence": lambda c: c >= 0.50
            }
        )
        
        buy_action = LinkedCreateOrderAction(
            symbol="SLV",
            quantity=10000,  # $10K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0,
            stop_loss_pct=0.03,      # 3% fallback
            take_profit_pct=0.06     # 6% fallback
        )
        
        buy_rule = Rule(
            rule_id="slv_context_test_rule",
            name="SLV Context Test Rule",
            description="Test rule to check context after trade",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # Simulate a BUY signal
        logger.info("\n" + "="*80)
        logger.info("SIMULATING SLV BUY SIGNAL")
        logger.info("="*80)
        
        signal_event = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.77,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal_event)
        
        # Wait for order processing
        logger.info("Waiting for order processing...")
        await asyncio.sleep(3)
        
        # Print context after order creation
        print_context(rule_engine.context, "CONTEXT AFTER ORDER CREATION")
        
        # Check if SLV is in the context
        if "SLV" in rule_engine.context:
            slv_context = rule_engine.context["SLV"]
            logger.info("\n📊 SLV Context Details:")
            logger.info(f"  Status: {slv_context.get('status')}")
            logger.info(f"  Side: {slv_context.get('side')}")
            logger.info(f"  Orders: {slv_context.get('orders', {})}")
            
            # Check for specific order types
            orders = slv_context.get('orders', {})
            logger.info(f"\n  Order Types Present:")
            for order_type, order_ids in orders.items():
                logger.info(f"    {order_type}: {order_ids}")
        
        # Wait a bit more to see if any fills happen
        logger.info("\nWaiting for potential order fills...")
        await asyncio.sleep(5)
        
        # Print final context
        print_context(rule_engine.context, "FINAL CONTEXT STATE")
        
        # Get order summary
        logger.info("\n📋 Order Summary:")
        active_orders = await order_manager.get_active_orders()
        for order in active_orders:
            logger.info(f"  Order {order.order_id}: {order.symbol} {order.side.value if order.side else 'N/A'} {order.quantity} @ {order.order_type.value} - Status: {order.status.value}")
        
        completed_orders = await order_manager.get_completed_orders(limit=10)
        if completed_orders:
            logger.info("\n  Completed Orders:")
            for order in completed_orders:
                logger.info(f"  Order {order.order_id}: {order.symbol} {order.side.value if order.side else 'N/A'} {order.quantity} @ {order.order_type.value} - Status: {order.status.value}")
        
        # Get position summary
        logger.info("\n💼 Position Summary:")
        positions = await position_tracker.get_all_positions()
        for position in positions:
            logger.info(f"  Position {position.symbol}: {position.quantity} shares @ ${position.entry_price:.2f} - Status: {position.status.value}")
        
        # Check if SLV is in the context
        if "SLV" in rule_engine.context:
            slv_context = rule_engine.context["SLV"]
            logger.info("\n📊 SLV Context Found!")
            logger.info(f"  Status: {slv_context.get('status')}")
            logger.info(f"  Side: {slv_context.get('side')}")
            logger.info(f"  Main orders: {slv_context.get('main_orders', [])}")
            logger.info(f"  Stop orders: {slv_context.get('stop_orders', [])}")
            logger.info(f"  Target orders: {slv_context.get('target_orders', [])}")
            logger.info(f"  Double down orders: {slv_context.get('doubledown_orders', [])}")
            
            # Also check for stored values
            logger.info(f"  Quantity: {slv_context.get('quantity')}")
            logger.info(f"  ATR stop multiplier: {slv_context.get('atr_stop_multiplier')}")
            logger.info(f"  ATR target multiplier: {slv_context.get('atr_target_multiplier')}")
        else:
            logger.warning("❌ SLV context NOT found in rule engine context!")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during context test: {e}", exc_info=True)
        return False
        
    finally:
        # Stop rule engine
        await rule_engine.stop()
        
        # Cancel any open orders
        logger.info("\nCleaning up orders...")
        active_orders = await order_manager.get_active_orders()
        for order in active_orders:
            if order.status.value in ["pending", "submitted", "partially_filled", "accepted"]:
                await order_manager.cancel_order(order.order_id, "Test cleanup")
        
        # Disconnect from TWS
        logger.info("Disconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_context_after_trade()
    
    if success:
        logger.info("\n✅ Context test completed successfully!")
    else:
        logger.error("\n❌ Context test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONTEXT STATE TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Connect to TWS")
    print("2. Place a BUY order for SLV")
    print("3. Show context state at each stage")
    print("4. Display all stored information")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 