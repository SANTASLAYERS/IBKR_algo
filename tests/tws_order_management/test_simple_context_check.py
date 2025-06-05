#!/usr/bin/env python3
"""
Simple Position Check Test
==========================

This test simply:
1. Places a single BUY order
2. Checks that the position is properly created in PositionTracker
3. Verifies all the expected fields are present
"""

import asyncio
import logging
import json
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
        logging.FileHandler('test_simple_position.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def print_position_details(position_tracker: PositionTracker, symbol: str):
    """Print detailed position information for a symbol."""
    logger.info("\n" + "="*80)
    logger.info(f"POSITION DETAILS FOR {symbol}")
    logger.info("="*80)
    
    positions = asyncio.run(position_tracker.get_positions_for_symbol(symbol))
    
    if positions:
        logger.info(f"✅ Found {len(positions)} position(s) for {symbol}")
        
        for i, position in enumerate(positions):
            logger.info(f"\nPosition {i+1}:")
            logger.info(f"  Symbol: {position.symbol}")
            logger.info(f"  Side: {position.side}")
            logger.info(f"  Status: {position.status}")
            logger.info(f"  Quantity: {position.quantity}")
            logger.info(f"  Entry Price: {position.entry_price}")
            
            # Check order IDs
            logger.info(f"\nOrder IDs:")
            logger.info(f"  Main orders: {len(position.main_order_ids)} - {position.main_order_ids}")
            logger.info(f"  Stop orders: {len(position.stop_order_ids)} - {position.stop_order_ids}")
            logger.info(f"  Target orders: {len(position.target_order_ids)} - {position.target_order_ids}")
            logger.info(f"  Scale orders: {len(position.scale_order_ids)} - {position.scale_order_ids}")
            logger.info(f"  Double down orders: {len(position.doubledown_order_ids)} - {position.doubledown_order_ids}")
            
            # Check ATR multipliers
            logger.info(f"\nATR Multipliers:")
            logger.info(f"  Stop ATR multiplier: {position.atr_stop_multiplier}")
            logger.info(f"  Target ATR multiplier: {position.atr_target_multiplier}")
            
            # Additional fields
            logger.info(f"\nAdditional fields:")
            logger.info(f"  Position ID: {position.position_id}")
            logger.info(f"  Created at: {position.created_at}")
            logger.info(f"  Updated at: {position.updated_at}")
                
    else:
        logger.error(f"❌ No positions found for {symbol}")
    
    logger.info("="*80 + "\n")


async def test_simple_position():
    """Test that position is properly created after placing an order."""
    logger.info("Starting simple position test...")
    
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
        # Create a simple BUY rule for SLV
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
            quantity=5000,  # $5K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        buy_rule = Rule(
            rule_id="slv_position_test",
            name="SLV Position Test",
            description="Test rule to verify position creation",
            condition=buy_condition,
            action=buy_action,
            priority=100
        )
        
        # Register and start rule engine
        rule_engine.register_rule(buy_rule)
        await rule_engine.start()
        
        # Check position BEFORE signal
        logger.info("\n📋 CHECKING POSITION BEFORE SIGNAL:")
        print_position_details(position_tracker, "SLV")
        
        # Send a BUY signal
        logger.info("\n📡 SENDING BUY SIGNAL FOR SLV...")
        signal = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.75,
            timestamp=datetime.now(),
            source="test"
        )
        
        await event_bus.emit(signal)
        
        # Wait for order processing
        logger.info("⏳ Waiting for order processing...")
        await asyncio.sleep(3)
        
        # Check position AFTER signal
        logger.info("\n📋 CHECKING POSITION AFTER SIGNAL:")
        print_position_details(position_tracker, "SLV")
        
        # Get order details
        logger.info("\n📊 ORDER SUMMARY:")
        active_orders = await order_manager.get_active_orders()
        logger.info(f"Total active orders: {len(active_orders)}")
        
        for order in active_orders:
            logger.info(f"  Order {order.order_id}: {order.symbol} {order.side.value if order.side else 'N/A'} "
                       f"{abs(order.quantity)} @ {order.order_type.value} - Status: {order.status.value}")
        
        # Final position check
        positions = await position_tracker.get_positions_for_symbol("SLV")
        if positions:
            position = positions[0]  # Should only be one position
            
            # Verify the position has the expected structure
            has_all_fields = all([
                hasattr(position, 'side'),
                hasattr(position, 'main_order_ids'),
                hasattr(position, 'stop_order_ids'),
                hasattr(position, 'target_order_ids'),
                hasattr(position, 'status')
            ])
            
            if has_all_fields:
                logger.info("\n✅ Position verification PASSED - all expected fields present")
                
                # Count orders
                main_count = len(position.main_order_ids)
                stop_count = len(position.stop_order_ids)
                target_count = len(position.target_order_ids)
                dd_count = len(position.doubledown_order_ids)
                
                logger.info(f"  Main orders: {main_count}")
                logger.info(f"  Stop orders: {stop_count}")
                logger.info(f"  Target orders: {target_count}")
                logger.info(f"  Double down orders: {dd_count}")
                
                return True
            else:
                logger.error("\n❌ Position verification FAILED - missing expected fields")
                return False
        else:
            logger.error("\n❌ Position verification FAILED - no position created for SLV")
            return False
        
    except Exception as e:
        logger.error(f"Error during position test: {e}", exc_info=True)
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
    success = await test_simple_position()
    
    if success:
        logger.info("\n✅ Position test completed successfully!")
    else:
        logger.error("\n❌ Position test failed!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SIMPLE POSITION VERIFICATION TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Connect to TWS")
    print("2. Place a single BUY order for SLV")
    print("3. Verify the position is properly created in PositionTracker")
    print("4. Check all expected fields are present")
    print("\nNOTE: This will create REAL orders in TWS")
    print("="*80 + "\n")
    
    confirm = input("Proceed with test? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 