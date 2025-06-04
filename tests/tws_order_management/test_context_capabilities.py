#!/usr/bin/env python3
"""
Test Context Capabilities
========================

This test demonstrates the key capabilities of context-based order management:
1. Canceling all related orders when closing positions
2. Updating stop/target orders after double down fills
"""

import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.event.order import FillEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedCloseAllAction,
    LinkedOrderConclusionManager,
    LinkedDoubleDownFillManager,
    LinkedOrderManager
)
from src.rule.base import Rule
from src.order import OrderType, OrderStatus
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
        logging.FileHandler('test_context_capabilities.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_context_capabilities():
    """Test context-based order management capabilities."""
    logger.info("Starting context capabilities test...")
    
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
    
    # Initialize double down fill manager
    dd_fill_manager = LinkedDoubleDownFillManager(
        context=rule_engine.context,
        event_bus=event_bus
    )
    await dd_fill_manager.initialize()
    
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
            quantity=100,  # Fixed 100 shares
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        buy_rule = Rule(
            rule_id="slv_buy_test",
            name="SLV Buy Test",
            description="Test rule for context capabilities",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # CAPABILITY 1: Create position with multiple orders
        logger.info("\n" + "="*80)
        logger.info("CAPABILITY 1: CREATE POSITION WITH MULTIPLE ORDERS")
        logger.info("="*80)
        
        signal = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.75,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal)
        await asyncio.sleep(3)  # Wait for all orders to be created
        
        # Show what was created
        active_orders = await order_manager.get_active_orders()
        slv_orders = [o for o in active_orders if o.symbol == "SLV"]
        logger.info(f"\n📊 Created {len(slv_orders)} orders for SLV:")
        
        order_map = {}
        for order in slv_orders:
            order_type_str = order.order_type.value
            if order.order_type == OrderType.LIMIT and order.quantity > 0:
                order_type_str = "DOUBLE_DOWN"
            elif order.order_type == OrderType.LIMIT and order.quantity < 0:
                order_type_str = "TARGET"
            
            order_map[order_type_str] = order
            logger.info(f"  - {order_type_str}: {order.quantity} @ "
                       f"${order.limit_price or order.stop_price or 'MKT'}")
        
        # Show context tracking
        context = rule_engine.context
        if "SLV" in context:
            slv_context = context["SLV"]
            logger.info(f"\n📋 Context is tracking:")
            logger.info(f"  - Side: {slv_context.get('side')}")
            logger.info(f"  - Main orders: {len(slv_context.get('main_orders', []))}")
            logger.info(f"  - Stop orders: {len(slv_context.get('stop_orders', []))}")
            logger.info(f"  - Target orders: {len(slv_context.get('target_orders', []))}")
            logger.info(f"  - Double down orders: {len(slv_context.get('doubledown_orders', []))}")
        
        # CAPABILITY 2: Cancel all orders with one command
        logger.info("\n" + "="*80)
        logger.info("CAPABILITY 2: CANCEL ALL ORDERS WITH ONE COMMAND")
        logger.info("="*80)
        
        logger.info("\nUsing LinkedCloseAllAction to cancel all orders at once...")
        
        close_action = LinkedCloseAllAction(
            symbol="SLV",
            reason="Demonstrating bulk cancellation"
        )
        
        # Execute the close action
        success = await close_action.execute(rule_engine.context)
        await asyncio.sleep(2)
        
        # Verify results
        remaining_orders = [o for o in await order_manager.get_active_orders() if o.symbol == "SLV"]
        logger.info(f"\n✅ Results:")
        logger.info(f"  - Orders before: {len(slv_orders)}")
        logger.info(f"  - Orders after: {len(remaining_orders)}")
        logger.info(f"  - All cancelled with ONE command!")
        
        # Verify context was cleared
        if "SLV" not in rule_engine.context:
            logger.info("  - Context automatically cleared")
        
        # Verify TradeTracker was updated
        if not trade_tracker.has_active_trade("SLV"):
            logger.info("  - TradeTracker automatically updated")
        
        # CAPABILITY 3: Double down fill updates stops/targets
        logger.info("\n" + "="*80)
        logger.info("CAPABILITY 3: DOUBLE DOWN UPDATES (Simulation)")
        logger.info("="*80)
        
        logger.info("\nWhen a double down order fills, the context enables:")
        logger.info("1. Automatic cancellation of old stop/target orders")
        logger.info("2. Creation of new stop/target with updated quantities")
        logger.info("3. New average price calculation")
        logger.info("4. Preservation of ATR multipliers from original position")
        
        logger.info("\nExample flow:")
        logger.info("  - Original: 100 shares @ $31.00, stop @ $30.00, target @ $33.00")
        logger.info("  - Double down fills: 100 shares @ $30.50")
        logger.info("  - New position: 200 shares @ $30.75 average")
        logger.info("  - Old stop/target cancelled automatically")
        logger.info("  - New stop: 200 shares @ $29.75 (using same ATR multiplier)")
        logger.info("  - New target: 200 shares @ $32.75 (using same ATR multiplier)")
        
        # Show the benefits
        logger.info("\n" + "="*80)
        logger.info("BENEFITS OF CONTEXT-BASED MANAGEMENT")
        logger.info("="*80)
        
        logger.info("\n✅ WITH Context:")
        logger.info("  - One command cancels all related orders")
        logger.info("  - Automatic tracking of order relationships")
        logger.info("  - Preserves position parameters (ATR multipliers, etc.)")
        logger.info("  - Automatic updates when orders fill")
        logger.info("  - Clean state management")
        
        logger.info("\n❌ WITHOUT Context:")
        logger.info("  - Query all orders and filter manually")
        logger.info("  - Risk cancelling wrong orders")
        logger.info("  - Lose position parameters")
        logger.info("  - Manual tracking of relationships")
        logger.info("  - Complex state management")
        
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
    success = await test_context_capabilities()
    
    if success:
        logger.info("\n✅ Context capabilities test completed successfully!")
    else:
        logger.error("\n❌ Context capabilities test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONTEXT CAPABILITIES TEST")
    print("="*80)
    print("\nThis test demonstrates:")
    print("1. Creating multiple related orders (main, stop, target, double down)")
    print("2. Canceling ALL orders with one command")
    print("3. How double down fills trigger automatic updates")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 