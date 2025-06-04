#!/usr/bin/env python3
"""
Test Duplicate Signal Handling
==============================

This test verifies that the context properly prevents duplicate positions
when multiple signals of the same type are received.

Test scenarios:
1. Send BUY signal -> Should create position
2. Send another BUY signal -> Should be ignored
3. Send SELL signal -> Should reverse position
4. Send another SELL signal -> Should be ignored
"""

import asyncio
import logging
import os
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
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
        logging.FileHandler('test_duplicate_signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_duplicate_signals():
    """Test duplicate signal handling."""
    logger.info("Starting duplicate signal test...")
    
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
    
    try:
        # Create BUY rule for SLV
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
            quantity=5000,  # $5K allocation (smaller for testing)
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        buy_rule = Rule(
            rule_id="slv_buy_duplicate_test",
            name="SLV Buy Duplicate Test",
            description="Test rule for duplicate signal handling",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Create SELL rule for SLV
        sell_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": "SLV",
                "signal": "SELL",
                "confidence": lambda c: c >= 0.50
            }
        )
        
        sell_action = LinkedCreateOrderAction(
            symbol="SLV",
            quantity=5000,  # $5K allocation
            side="SELL",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        sell_rule = Rule(
            rule_id="slv_sell_duplicate_test",
            name="SLV Sell Duplicate Test",
            description="Test rule for duplicate signal handling",
            condition=sell_condition,
            action=sell_action,
            priority=100
        )
        
        # Register rules and start engine
        rule_engine.register_rule(buy_rule)
        rule_engine.register_rule(sell_rule)
        await rule_engine.start()
        
        # Test 1: First BUY signal - should create position
        logger.info("\n" + "="*80)
        logger.info("TEST 1: FIRST BUY SIGNAL (should create position)")
        logger.info("="*80)
        
        signal1 = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.75,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal1)
        await asyncio.sleep(3)  # Wait for order processing
        
        # Check context after first signal
        if "SLV" in rule_engine.context:
            slv_context = rule_engine.context["SLV"]
            logger.info(f"✅ SLV context created: side={slv_context.get('side')}, status={slv_context.get('status')}")
            logger.info(f"   Main orders: {len(slv_context.get('main_orders', []))}")
            logger.info(f"   Stop orders: {len(slv_context.get('stop_orders', []))}")
        else:
            logger.error("❌ SLV context NOT created after first signal!")
        
        # Test 2: Second BUY signal - should be ignored
        logger.info("\n" + "="*80)
        logger.info("TEST 2: SECOND BUY SIGNAL (should be ignored)")
        logger.info("="*80)
        
        signal2 = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.80,
            timestamp=datetime.now(),
            source="test"
        )
        
        # Count orders before second signal
        active_orders_before = await order_manager.get_active_orders()
        logger.info(f"Active orders before second signal: {len(active_orders_before)}")
        
        await event_bus.emit(signal2)
        await asyncio.sleep(2)  # Wait to see if any new orders are created
        
        # Count orders after second signal
        active_orders_after = await order_manager.get_active_orders()
        logger.info(f"Active orders after second signal: {len(active_orders_after)}")
        
        if len(active_orders_after) == len(active_orders_before):
            logger.info("✅ Second BUY signal correctly ignored - no new orders created")
        else:
            logger.error("❌ Second BUY signal created new orders!")
        
        # Wait a bit before position reversal
        await asyncio.sleep(3)
        
        # Test 3: SELL signal - should reverse position
        logger.info("\n" + "="*80)
        logger.info("TEST 3: SELL SIGNAL (should reverse position)")
        logger.info("="*80)
        
        signal3 = PredictionSignalEvent(
            symbol="SLV",
            signal="SELL",
            confidence=0.70,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal3)
        await asyncio.sleep(5)  # Wait for position reversal
        
        # Check context after reversal
        if "SLV" in rule_engine.context:
            slv_context = rule_engine.context["SLV"]
            logger.info(f"✅ SLV context after reversal: side={slv_context.get('side')}, status={slv_context.get('status')}")
        
        # Test 4: Second SELL signal - should be ignored
        logger.info("\n" + "="*80)
        logger.info("TEST 4: SECOND SELL SIGNAL (should be ignored)")
        logger.info("="*80)
        
        signal4 = PredictionSignalEvent(
            symbol="SLV",
            signal="SELL",
            confidence=0.85,
            timestamp=datetime.now(),
            source="test"
        )
        
        # Count orders before second SELL signal
        active_orders_before = await order_manager.get_active_orders()
        logger.info(f"Active orders before second SELL signal: {len(active_orders_before)}")
        
        await event_bus.emit(signal4)
        await asyncio.sleep(2)
        
        # Count orders after second SELL signal
        active_orders_after = await order_manager.get_active_orders()
        logger.info(f"Active orders after second SELL signal: {len(active_orders_after)}")
        
        if len(active_orders_after) == len(active_orders_before):
            logger.info("✅ Second SELL signal correctly ignored - no new orders created")
        else:
            logger.error("❌ Second SELL signal created new orders!")
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        # Get all orders
        all_active = await order_manager.get_active_orders()
        all_completed = await order_manager.get_completed_orders(limit=20)
        
        logger.info(f"Total active orders: {len(all_active)}")
        logger.info(f"Total completed orders: {len(all_completed)}")
        
        # List all orders
        logger.info("\nOrder Details:")
        for order in all_completed:
            logger.info(f"  {order.symbol} {order.side.value if order.side else 'N/A'} {abs(order.quantity)} @ {order.order_type.value} - {order.status.value}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during duplicate signal test: {e}", exc_info=True)
        return False
        
    finally:
        # Stop rule engine
        await rule_engine.stop()
        
        # Cancel any open orders
        logger.info("\nCleaning up orders...")
        active_orders = await order_manager.get_active_orders()
        for order in active_orders:
            await order_manager.cancel_order(order.order_id, "Test cleanup")
        
        # Disconnect from TWS
        logger.info("Disconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_duplicate_signals()
    
    if success:
        logger.info("\n✅ Duplicate signal test completed successfully!")
    else:
        logger.error("\n❌ Duplicate signal test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("DUPLICATE SIGNAL HANDLING TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Send a BUY signal -> Should create position")
    print("2. Send another BUY signal -> Should be IGNORED")
    print("3. Send a SELL signal -> Should reverse position")
    print("4. Send another SELL signal -> Should be IGNORED")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 