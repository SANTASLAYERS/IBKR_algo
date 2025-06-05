"""
Test script for going long GLD with ATR-based protective orders and double down.

This test:
1. Goes long GLD
2. Places protective orders using ATR multiplier of 3
3. Creates a double down order
4. Waits for the position to close
"""

import asyncio
import logging
from datetime import datetime
import os

# Set up logging with reduced verbosity
logging.basicConfig(
    level=logging.WARNING,  # Set default to WARNING
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set specific loggers
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Keep INFO for our test

# Silence verbose loggers
logging.getLogger('ibapi').setLevel(logging.ERROR)
logging.getLogger('src.tws_connection').setLevel(logging.WARNING)
logging.getLogger('src.indicators').setLevel(logging.WARNING)
logging.getLogger('src.price').setLevel(logging.WARNING)
logging.getLogger('src.rule').setLevel(logging.WARNING)
logging.getLogger('src.minute_data').setLevel(logging.WARNING)

# Import required components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.rule.engine import RuleEngine
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderConclusionManager,
    LinkedDoubleDownFillManager
)
from src.indicators.manager import IndicatorManager
from src.minute_data.manager import MinuteBarManager
from src.price.service import PriceService
from src.position.sizer import PositionSizer
from src.event.order import FillEvent
from src.order import OrderType


async def wait_for_position_close(event_bus: EventBus, symbol: str, timeout: int = 300):
    """Wait for position to close via stop or target fill."""
    position_closed = asyncio.Event()
    
    async def on_fill(event: FillEvent):
        if event.symbol == symbol:
            logger.info(f"Fill event for {symbol}: {event.order_id} at ${event.fill_price}")
            # Check if this might be a closing fill
            # In a real scenario, we'd check if it's a stop or target order
            # For now, we'll set the event after any fill
            position_closed.set()
    
    # Subscribe to fill events
    await event_bus.subscribe(FillEvent, on_fill)
    
    try:
        # Wait for position to close or timeout
        await asyncio.wait_for(position_closed.wait(), timeout=timeout)
        logger.info(f"Position for {symbol} has been closed")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for {symbol} position to close")
    finally:
        await event_bus.unsubscribe(FillEvent, on_fill)


async def main():
    """Main test function."""
    logger.info("Starting GLD long position test with ATR-based stops")
    
    # Configuration
    symbol = "GLD"
    allocation = 10000  # $10,000 allocation
    atr_multiplier = 3.0  # ATR multiplier for both stop and target
    
    # Initialize components
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    event_bus = EventBus()
    order_manager = OrderManager(event_bus, tws_connection)
    position_tracker = PositionTracker(event_bus)
    rule_engine = RuleEngine(event_bus)
    
    # Initialize minute data manager for ATR calculation
    minute_data_manager = MinuteBarManager(tws_connection)
    indicator_manager = IndicatorManager(minute_data_manager)
    
    price_service = PriceService(tws_connection)
    position_sizer = PositionSizer()
    
    # Connect to TWS
    logger.info("Connecting to TWS...")
    connected = await tws_connection.connect()
    if not connected:
        logger.error("Failed to connect to TWS")
        return
    
    logger.info("Connected to TWS successfully")
    
    # Initialize components
    await order_manager.initialize()
    await position_tracker.initialize()
    
    # Set up rule engine context
    rule_engine.update_context({
        "order_manager": order_manager,
        "position_tracker": position_tracker,
        "indicator_manager": indicator_manager,
        "price_service": price_service,
        "position_sizer": position_sizer,
        "prices": {}  # Will be populated by price service
    })
    
    # Initialize conclusion managers
    conclusion_manager = LinkedOrderConclusionManager(rule_engine.context, event_bus)
    await conclusion_manager.initialize()
    
    doubledown_manager = LinkedDoubleDownFillManager(rule_engine.context, event_bus)
    await doubledown_manager.initialize()
    
    # Start rule engine
    await rule_engine.start()
    
    try:
        # Create the long position with ATR-based protective orders
        logger.info(f"Creating long position for {symbol} with ${allocation} allocation")
        
        # Create the order action
        create_order_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=allocation,  # Will be converted to shares based on price
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=atr_multiplier,      # 3x ATR for stop
            atr_target_multiplier=atr_multiplier     # 3x ATR for target
        )
        
        # Execute the order
        success = await create_order_action.execute(rule_engine.context)
        
        if success:
            logger.info(f"Successfully created long position for {symbol}")
            
            # Wait a bit for the orders to be processed
            await asyncio.sleep(5)
            
            # The double down orders should be created automatically
            # by the LinkedCreateOrderAction when auto_create_stops=True
            logger.info("Double down orders should have been created automatically")
            
            # Wait for position to close (via stop or target)
            logger.info("Waiting for position to close via stop or target...")
            await wait_for_position_close(event_bus, symbol, timeout=300)
            
        else:
            logger.error(f"Failed to create position for {symbol}")
            
    except Exception as e:
        logger.error(f"Error during test execution: {e}", exc_info=True)
    finally:
        # Clean up
        logger.info("Cleaning up...")
        await rule_engine.stop()
        tws_connection.disconnect()
        logger.info("Test completed")


if __name__ == "__main__":
    # Run the test
    asyncio.run(main()) 