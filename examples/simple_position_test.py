#!/usr/bin/env python3
"""
Simple Position Management Test

This script tests the basic functionality of the position management system
with direct API calls rather than relying on the event system.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.event.bus import EventBus
from src.position.tracker import PositionTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("position_test")


async def test_position_management():
    """Test the position management system functionality."""
    # Create event bus and position tracker
    event_bus = EventBus()
    position_tracker = PositionTracker(event_bus)
    
    logger.info("Creating test positions...")
    
    # Create a long position
    aapl_position = await position_tracker.create_stock_position(
        symbol="AAPL",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        take_profit=165.0,
        strategy="Test",
        metadata={"test": True}
    )
    
    # Create a short position
    msft_position = await position_tracker.create_stock_position(
        symbol="MSFT",
        quantity=-50,
        entry_price=300.0,
        stop_loss=315.0,
        take_profit=270.0,
        strategy="Test",
        metadata={"test": True}
    )
    
    # Log created positions
    positions = await position_tracker.get_all_positions()
    logger.info(f"Created {len(positions)} positions:")
    for position in positions:
        logger.info(f"  {position}")
    
    # Update position prices
    logger.info("\nUpdating position prices...")
    await position_tracker.update_position_price(aapl_position.position_id, 155.0)
    await position_tracker.update_position_price(msft_position.position_id, 290.0)
    
    # Log updated positions
    positions = await position_tracker.get_all_positions()
    logger.info(f"Updated positions:")
    for position in positions:
        logger.info(f"  {position} - P&L: {position.unrealized_pnl:.2f}")
    
    # Update stop loss for AAPL position
    logger.info("\nUpdating stop loss...")
    await position_tracker.update_stop_loss(aapl_position.position_id, 150.0, "Moving stop to breakeven")
    
    # Log position after stop loss update
    position = await position_tracker.get_position(aapl_position.position_id)
    logger.info(f"After stop loss update: {position} - Stop: {position.stop_loss}")
    
    # Close the MSFT position
    logger.info("\nClosing MSFT position...")
    await position_tracker.close_position(msft_position.position_id, 280.0, "Take profit")
    
    # Log positions after closing
    positions = await position_tracker.get_all_positions()
    logger.info(f"Active positions after closing MSFT: {len(positions)}")
    
    # Get closed positions
    closed_positions = await position_tracker.get_closed_positions()
    logger.info(f"Closed positions: {len(closed_positions)}")
    for position in closed_positions:
        logger.info(f"  {position} - Realized P&L: {position.realized_pnl:.2f}")
    
    # Close the AAPL position
    logger.info("\nClosing AAPL position...")
    await position_tracker.close_position(aapl_position.position_id, 160.0, "Take profit")
    
    # Get all closed positions
    closed_positions = await position_tracker.get_closed_positions()
    logger.info(f"All closed positions: {len(closed_positions)}")
    for position in closed_positions:
        logger.info(f"  {position} - Realized P&L: {position.realized_pnl:.2f}")
    
    # Get position summary
    summary = await position_tracker.get_position_summary()
    logger.info(f"\nFinal position summary:")
    logger.info(f"  Total positions: {summary['total_positions']}")
    logger.info(f"  Total realized P&L: {summary['total_realized_pnl']:.2f}")


if __name__ == "__main__":
    asyncio.run(test_position_management())