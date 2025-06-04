#!/usr/bin/env python3
"""
Test Multi-Symbol Trade Tracking
================================

This test verifies that the TradeTracker allows trades on different symbols
while preventing duplicates on the same symbol.
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
        logging.FileHandler('test_multi_symbol.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_multi_symbol():
    """Test that TradeTracker allows different symbols while blocking same symbol."""
    logger.info("Starting multi-symbol test...")
    
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
        # Create rules for multiple symbols
        symbols = ["SLV", "GLD", "SPY"]
        
        for symbol in symbols:
            # Create BUY rule
            buy_condition = EventCondition(
                event_type=PredictionSignalEvent,
                field_conditions={
                    "symbol": symbol,
                    "signal": "BUY",
                    "confidence": lambda c: c >= 0.50
                }
            )
            
            buy_action = LinkedCreateOrderAction(
                symbol=symbol,
                quantity=2000,  # $2K allocation each
                side="BUY",
                order_type=OrderType.MARKET,
                auto_create_stops=True,
                stop_loss_pct=0.03,
                take_profit_pct=0.06
            )
            
            buy_rule = Rule(
                rule_id=f"{symbol.lower()}_buy_test",
                name=f"{symbol} Buy Test",
                description=f"Test rule for {symbol}",
                condition=buy_condition,
                action=buy_action,
                priority=100
            )
            
            rule_engine.register_rule(buy_rule)
        
        await rule_engine.start()
        
        # Test 1: Send BUY signals for different symbols - all should work
        logger.info("\n" + "="*80)
        logger.info("TEST 1: BUY SIGNALS FOR DIFFERENT SYMBOLS")
        logger.info("="*80)
        
        for symbol in symbols:
            logger.info(f"\nSending BUY signal for {symbol}...")
            
            signal = PredictionSignalEvent(
                symbol=symbol,
                signal="BUY",
                confidence=0.75,
                timestamp=datetime.now(),
                source="test"
            )
            
            await event_bus.emit(signal)
            await asyncio.sleep(1)  # Small delay between signals
        
        # Wait for all orders to process
        await asyncio.sleep(2)
        
        # Check TradeTracker
        active_trades = trade_tracker.get_all_active_trades()
        logger.info(f"\nActive trades: {len(active_trades)}")
        for symbol, trade in active_trades.items():
            logger.info(f"  {symbol}: {trade.side} trade started at {trade.entry_time}")
        
        if len(active_trades) == len(symbols):
            logger.info("✅ All symbols have active trades")
        else:
            logger.error(f"❌ Expected {len(symbols)} trades, got {len(active_trades)}")
        
        # Test 2: Send duplicate BUY signal for SLV - should be ignored
        logger.info("\n" + "="*80)
        logger.info("TEST 2: DUPLICATE BUY SIGNAL FOR SLV")
        logger.info("="*80)
        
        orders_before = len(await order_manager.get_active_orders())
        
        duplicate_signal = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.80,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(duplicate_signal)
        await asyncio.sleep(2)
        
        orders_after = len(await order_manager.get_active_orders())
        
        if orders_after == orders_before:
            logger.info("✅ Duplicate SLV signal correctly ignored")
        else:
            logger.error("❌ Duplicate SLV signal created new orders!")
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("FINAL SUMMARY")
        logger.info("="*80)
        
        active_trades = trade_tracker.get_all_active_trades()
        logger.info(f"Total active trades: {len(active_trades)}")
        logger.info(f"Symbols with trades: {list(active_trades.keys())}")
        
        return len(active_trades) == len(symbols)
        
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
    success = await test_multi_symbol()
    
    if success:
        logger.info("\n✅ Multi-symbol test completed successfully!")
    else:
        logger.error("\n❌ Multi-symbol test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("MULTI-SYMBOL TRADE TRACKING TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Send BUY signals for SLV, GLD, and SPY")
    print("2. Verify all three trades are created")
    print("3. Send duplicate SLV signal and verify it's ignored")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 