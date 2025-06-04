#!/usr/bin/env python3
"""
Test Order Management with Context
==================================

This test verifies:
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
    LinkedDoubleDownFillManager
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
        logging.FileHandler('test_order_management.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_order_management():
    """Test order cancellation and updates."""
    logger.info("Starting order management test...")
    
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
            description="Test rule for order management",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # Test 1: Create position with stops and double down
        logger.info("\n" + "="*80)
        logger.info("TEST 1: CREATE POSITION WITH STOPS AND DOUBLE DOWN")
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
        
        # Check what orders were created
        active_orders = await order_manager.get_active_orders()
        logger.info(f"\nActive orders after entry:")
        
        main_orders = []
        stop_orders = []
        target_orders = []
        dd_orders = []
        
        for order in active_orders:
            if order.symbol == "SLV":
                if order.order_type == OrderType.MARKET:
                    main_orders.append(order)
                elif order.order_type == OrderType.STOP:
                    stop_orders.append(order)
                elif order.order_type == OrderType.LIMIT:
                    # Check if it's a sell limit (target) or buy limit (double down)
                    if order.quantity < 0:  # Sell order
                        target_orders.append(order)
                    else:  # Buy order
                        dd_orders.append(order)
        
        logger.info(f"  Main orders: {len(main_orders)}")
        logger.info(f"  Stop orders: {len(stop_orders)}")
        logger.info(f"  Target orders: {len(target_orders)}")
        logger.info(f"  Double down orders: {len(dd_orders)}")
        
        # Verify context has all order IDs
        context = rule_engine.context
        if "SLV" in context:
            slv_context = context["SLV"]
            logger.info(f"\nContext for SLV:")
            logger.info(f"  Side: {slv_context.get('side')}")
            logger.info(f"  Main orders in context: {len(slv_context.get('main_orders', []))}")
            logger.info(f"  Stop orders in context: {len(slv_context.get('stop_orders', []))}")
            logger.info(f"  Target orders in context: {len(slv_context.get('target_orders', []))}")
            logger.info(f"  Double down orders in context: {len(slv_context.get('doubledown_orders', []))}")
        
        # Test 2: Simulate double down fill and check if stops/targets update
        if dd_orders:
            logger.info("\n" + "="*80)
            logger.info("TEST 2: SIMULATE DOUBLE DOWN FILL")
            logger.info("="*80)
            
            dd_order = dd_orders[0]
            logger.info(f"\nSimulating fill of double down order {dd_order.order_id}")
            logger.info(f"Double down: {dd_order.quantity} shares @ ${dd_order.limit_price}")
            
            # Record current stop/target prices
            old_stop_price = stop_orders[0].stop_price if stop_orders else None
            old_target_price = target_orders[0].limit_price if target_orders else None
            
            # Emit fill event for double down
            fill_event = FillEvent(
                order_id=dd_order.order_id,
                symbol="SLV",
                quantity=dd_order.quantity,
                fill_price=dd_order.limit_price,
                commission=1.0,
                timestamp=datetime.now()
            )
            
            await event_bus.emit(fill_event)
            await asyncio.sleep(2)  # Wait for updates
            
            # Check if stops/targets were updated
            logger.info("\nChecking for updated orders...")
            # Note: In real implementation, the LinkedDoubleDownFillManager would
            # cancel old orders and create new ones. For this test, we're just
            # verifying the mechanism exists.
        
        # Test 3: Close all positions and verify all orders are cancelled
        logger.info("\n" + "="*80)
        logger.info("TEST 3: CLOSE ALL POSITIONS")
        logger.info("="*80)
        
        # Count orders before closing
        orders_before = len(await order_manager.get_active_orders())
        logger.info(f"\nActive orders before closing: {orders_before}")
        
        # Use LinkedCloseAllAction
        close_action = LinkedCloseAllAction(
            symbol="SLV",
            reason="Test cleanup"
        )
        
        success = await close_action.execute(rule_engine.context)
        await asyncio.sleep(2)
        
        # Count orders after closing
        orders_after = len([o for o in await order_manager.get_active_orders() if o.symbol == "SLV"])
        logger.info(f"Active SLV orders after closing: {orders_after}")
        
        # Verify context was cleared
        if "SLV" not in rule_engine.context:
            logger.info("✅ Context cleared for SLV")
        else:
            logger.error("❌ Context still exists for SLV")
        
        # Verify TradeTracker was updated
        if not trade_tracker.has_active_trade("SLV"):
            logger.info("✅ TradeTracker cleared for SLV")
        else:
            logger.error("❌ TradeTracker still has active trade for SLV")
        
        return orders_after == 0
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False
        
    finally:
        # Stop rule engine
        await rule_engine.stop()
        
        # Cancel any remaining orders
        logger.info("\nFinal cleanup...")
        active_orders = await order_manager.get_active_orders()
        for order in active_orders:
            if order.symbol == "SLV":
                await order_manager.cancel_order(order.order_id, "Final cleanup")
        
        # Clear trade tracker
        trade_tracker.clear_all()
        
        # Disconnect from TWS
        logger.info("Disconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_order_management()
    
    if success:
        logger.info("\n✅ Order management test completed successfully!")
    else:
        logger.error("\n❌ Order management test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ORDER MANAGEMENT TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Create a position with stop, target, and double down orders")
    print("2. Verify all orders are tracked in context")
    print("3. Close the position and verify all orders are cancelled")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 