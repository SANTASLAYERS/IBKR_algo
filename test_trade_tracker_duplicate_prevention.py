#!/usr/bin/env python3
"""
Test Trade Tracker Duplicate Prevention
======================================

This test verifies that the TradeTracker properly prevents duplicate trades
when multiple signals of the same type are received.
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
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedOrderConclusionManager
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
        logging.FileHandler('test_trade_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_trade_tracker():
    """Test that TradeTracker prevents duplicate trades."""
    logger.info("Starting TradeTracker test...")
    
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
            quantity=3000,  # $3K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        buy_rule = Rule(
            rule_id="slv_buy_tracker_test",
            name="SLV Buy Tracker Test",
            description="Test rule for TradeTracker",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # Test 1: First BUY signal - should create trade
        logger.info("\n" + "="*80)
        logger.info("TEST 1: FIRST BUY SIGNAL (should create trade)")
        logger.info("="*80)
        
        # Check TradeTracker before
        active_trades = trade_tracker.get_all_active_trades()
        logger.info(f"Active trades before first signal: {len(active_trades)}")
        
        signal1 = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.75,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal1)
        await asyncio.sleep(2)  # Wait for order processing
        
        # Check TradeTracker after
        active_trades = trade_tracker.get_all_active_trades()
        logger.info(f"Active trades after first signal: {len(active_trades)}")
        
        if "SLV" in active_trades:
            trade = active_trades["SLV"]
            logger.info(f"✅ Trade created: {trade.symbol} {trade.side} at {trade.entry_time}")
        else:
            logger.error("❌ No trade created in TradeTracker!")
        
        # Count orders
        active_orders = await order_manager.get_active_orders()
        logger.info(f"Active orders: {len(active_orders)}")
        
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
        
        # Count orders before
        orders_before = len(await order_manager.get_active_orders())
        
        await event_bus.emit(signal2)
        await asyncio.sleep(2)
        
        # Count orders after
        orders_after = len(await order_manager.get_active_orders())
        
        if orders_after == orders_before:
            logger.info("✅ Second BUY signal correctly ignored - no new orders")
        else:
            logger.error(f"❌ Second BUY signal created {orders_after - orders_before} new orders!")
        
        # Check TradeTracker still has only one trade
        active_trades = trade_tracker.get_all_active_trades()
        logger.info(f"Active trades after second signal: {len(active_trades)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False
        
    finally:
        # Stop rule engine
        await rule_engine.stop()
        
        # Cancel any open orders
        logger.info("\nCleaning up orders...")
        active_orders = await order_manager.get_active_orders()
        for order in active_orders:
            await order_manager.cancel_order(order.order_id, "Test cleanup")
        
        # Clear trade tracker
        trade_tracker.clear_all()
        
        # Disconnect from TWS
        logger.info("Disconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_trade_tracker()
    
    if success:
        logger.info("\n✅ TradeTracker test completed successfully!")
    else:
        logger.error("\n❌ TradeTracker test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("TRADE TRACKER DUPLICATE PREVENTION TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Send a BUY signal -> Should create trade in TradeTracker")
    print("2. Send another BUY signal -> Should be IGNORED")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 