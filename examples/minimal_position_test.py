#!/usr/bin/env python3
"""
Minimal Position Test

This script tests the most basic functionality of the Position class.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.position.base import Position, PositionStatus

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("minimal_test")


async def test_basic_position():
    """Test basic position functionality."""
    # Create a position
    position = Position("AAPL")
    logger.info(f"Created position: {position}")
    logger.info(f"Position status: {position.status}")
    
    # Open the position
    await position.open(100, 150.0)
    logger.info(f"Opened position: {position}")
    logger.info(f"Position status: {position.status}")
    logger.info(f"Is active: {position.is_active}")
    
    # Update price
    await position.update_price(160.0)
    logger.info(f"After price update: {position}")
    logger.info(f"Unrealized P&L: {position.unrealized_pnl}")
    
    # Close the position
    await position.close(170.0, "Test close")
    logger.info(f"Closed position: {position}")
    logger.info(f"Position status: {position.status}")
    logger.info(f"Is active: {position.is_active}")
    logger.info(f"Realized P&L: {position.realized_pnl}")
    
    logger.info("Test completed successfully")


if __name__ == "__main__":
    asyncio.run(test_basic_position())