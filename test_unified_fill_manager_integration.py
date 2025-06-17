#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test UnifiedFillManager Integration with Alpaca

This script tests that the UnifiedFillManager is properly integrated
and can handle fill events in the Alpaca trading system.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.broker_config import BrokerConfig
from src.alpaca_connection import AlpacaConnection
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.rule.unified_fill_manager import UnifiedFillManager
from src.event.order import FillEvent, OrderStatus
from src.logger import get_logger

logger = get_logger(__name__)


async def test_unified_fill_manager():
    """Test UnifiedFillManager integration."""
    logger.info("=" * 50)
    logger.info("Testing UnifiedFillManager Integration")
    logger.info("=" * 50)
    
    # Initialize components
    config = BrokerConfig.from_env()
    event_bus = EventBus()
    connection = AlpacaConnection(config.alpaca, event_bus)
    
    # Connect to Alpaca
    logger.info("Connecting to Alpaca...")
    connected = await connection.connect()
    if not connected:
        logger.error("Failed to connect to Alpaca")
        return
    
    # Initialize position tracking
    position_tracker = PositionTracker(event_bus)
    await position_tracker.initialize()
    position_manager = PositionManager()
    
    # Initialize order manager
    order_manager = OrderManager(
        event_bus=event_bus,
        broker_connection=connection
    )
    
    # Initialize UnifiedFillManager
    logger.info("Initializing UnifiedFillManager...")
    context = {
        'order_manager': order_manager,
        'position_manager': position_manager,
        'position_tracker': position_tracker,
        'connection': connection
    }
    
    unified_fill_manager = UnifiedFillManager(
        context=context,
        event_bus=event_bus
    )
    await unified_fill_manager.initialize()
    logger.info("UnifiedFillManager initialized and subscribed to FillEvent")
    
    # Test 1: Verify subscription
    logger.info("\nTest 1: Verify event subscription")
    subscriber_count = await event_bus.get_subscriber_count(FillEvent)
    logger.info(f"UnifiedFillManager subscribed to FillEvent: {subscriber_count > 0} (count: {subscriber_count})")
    
    # Test 2: Simulate a fill event
    logger.info("\nTest 2: Simulate fill event handling")
    
    # Create a mock fill event
    test_fill_event = FillEvent(
        order_id="TEST_ORDER_123",
        symbol="AAPL",
        fill_quantity=100,
        fill_price=150.00,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
        timestamp=datetime.now()
    )
    # Add broker_price as an attribute (expected by UnifiedFillManager)
    test_fill_event.broker_price = 150.00
    
    # Emit the event to test handling
    logger.info("Emitting test fill event...")
    await event_bus.emit(test_fill_event)
    
    # Give it a moment to process
    await asyncio.sleep(1)
    
    logger.info("Fill event emitted and processed")
    
    # Test 3: Check context access
    logger.info("\nTest 3: Verify context access")
    logger.info(f"Order manager in context: {unified_fill_manager.context.get('order_manager') is not None}")
    logger.info(f"Position manager in context: {unified_fill_manager.context.get('position_manager') is not None}")
    logger.info(f"Position tracker in context: {unified_fill_manager.context.get('position_tracker') is not None}")
    logger.info(f"Connection in context: {unified_fill_manager.context.get('connection') is not None}")
    
    # Cleanup
    logger.info("\nCleaning up...")
    await unified_fill_manager.cleanup()
    connection.disconnect()
    
    logger.info("\nUnifiedFillManager integration test completed")
    

async def main():
    """Main entry point."""
    try:
        await test_unified_fill_manager()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main()) 