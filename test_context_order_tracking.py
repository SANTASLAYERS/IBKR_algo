#!/usr/bin/env python3
"""
Test Context Order Tracking
===========================

Simple test to show how context tracks orders and enables proper cancellation.
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
    LinkedCloseAllAction,
    LinkedOrderConclusionManager
)
from src.rule.base import Rule
from src.order import OrderType
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
        logging.FileHandler('test_context_demo.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_context_tracking():
    """Test context-based order tracking."""
    logger.info("Starting context tracking test...")
    
    # Clear any existing trades
    trade_tracker = TradeTracker()
    trade_tracker.clear_all()
    
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
    
    try:
        # Create BUY rule for SLV with auto stops
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
            quantity=50,  # Fixed 50 shares
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        buy_rule = Rule(
            rule_id="slv_buy_context_test",
            name="SLV Buy Context Test",
            description="Test rule for context tracking",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # Step 1: Create position
        logger.info("\n" + "="*80)
        logger.info("STEP 1: CREATE POSITION WITH ORDERS")
        logger.info("="*80)
        
        signal = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.75,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal)
        await asyncio.sleep(3)  # Wait for all orders
        
        # Show actual orders created
        active_orders = await order_manager.get_active_orders()
        slv_orders = [o for o in active_orders if o.symbol == "SLV"]
        logger.info(f"\n📊 Created {len(slv_orders)} orders for SLV:")
        
        order_ids = []
        for order in slv_orders:
            order_ids.append(order.order_id)
            logger.info(f"  - {order.order_type.value}: {order.quantity} @ "
                       f"${order.limit_price or order.stop_price or 'MKT'} "
                       f"(ID: {order.order_id[:8]}...)")
        
        # Step 2: Demonstrate context-based cancellation
        logger.info("\n" + "="*80)
        logger.info("STEP 2: CANCEL ALL ORDERS MANUALLY")
        logger.info("="*80)
        
        logger.info("\nCancelling all orders one by one...")
        
        cancelled_count = 0
        for order_id in order_ids:
            try:
                await order_manager.cancel_order(order_id, "Manual cancellation demo")
                cancelled_count += 1
                logger.info(f"  ✅ Cancelled order {order_id[:8]}...")
            except Exception as e:
                logger.error(f"  ❌ Failed to cancel {order_id[:8]}...: {e}")
        
        await asyncio.sleep(2)
        
        # Verify results
        remaining_orders = [o for o in await order_manager.get_active_orders() if o.symbol == "SLV"]
        logger.info(f"\n📊 Results:")
        logger.info(f"  - Orders cancelled: {cancelled_count}")
        logger.info(f"  - Orders remaining: {len(remaining_orders)}")
        
        # Clear TradeTracker
        trade_tracker.close_trade("SLV")
        
        logger.info("\n" + "="*80)
        logger.info("KEY INSIGHT")
        logger.info("="*80)
        logger.info("\nThe context implementation is valuable because:")
        logger.info("1. It tracks ALL order IDs when created (main, stop, target, double down)")
        logger.info("2. LinkedCloseAllAction can cancel them all with one call")
        logger.info("3. It maintains order relationships (which stops belong to which position)")
        logger.info("4. It stores position parameters (ATR multipliers, quantities, etc.)")
        logger.info("\nWithout context, you'd need to:")
        logger.info("- Query all orders and filter by symbol")
        logger.info("- Guess which orders belong together")
        logger.info("- Lose position-specific parameters")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False
        
    finally:
        # Stop rule engine
        await rule_engine.stop()
        
        # Clear trade tracker
        trade_tracker.clear_all()
        
        # Disconnect from TWS
        logger.info("\nDisconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_context_tracking()
    
    if success:
        logger.info("\n✅ Context tracking demonstration completed!")
    else:
        logger.error("\n❌ Context tracking demonstration failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONTEXT ORDER TRACKING DEMONSTRATION")
    print("="*80)
    print("\nThis test demonstrates why context tracking is valuable:")
    print("1. Shows orders being created and tracked")
    print("2. Shows manual cancellation (what you'd need without context)")
    print("3. Explains benefits of context-based management")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 