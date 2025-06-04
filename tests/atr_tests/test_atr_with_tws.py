#!/usr/bin/env python3
"""
Test ATR calculation with real TWS connection
"""

import asyncio
import logging
import os
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.indicators.manager import IndicatorManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_atr_calculation():
    """Test ATR calculation with real TWS connection."""
    logger.info("Starting ATR test with TWS...")
    
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
    
    # Initialize indicator manager
    indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
    
    try:
        # Test ATR calculation for SLV with 10-second bars
        logger.info("\n" + "="*80)
        logger.info("Testing ATR calculation for SLV with 10-second bars")
        logger.info("="*80)
        
        atr_value = await indicator_manager.get_atr(
            symbol="SLV",
            period=14,
            days=1,
            bar_size="10 secs"
        )
        
        if atr_value:
            logger.info(f"✅ ATR calculated successfully: {atr_value:.4f}")
            
            # Calculate stop and target distances
            stop_multiplier = 6.0
            target_multiplier = 3.0
            
            stop_distance = atr_value * stop_multiplier
            target_distance = atr_value * target_multiplier
            
            logger.info(f"Stop distance (6x ATR): ${stop_distance:.4f}")
            logger.info(f"Target distance (3x ATR): ${target_distance:.4f}")
            
            # Example with current price
            current_price = 31.00  # Example price
            stop_price = current_price - stop_distance
            target_price = current_price + target_distance
            
            logger.info(f"\nExample with current price ${current_price:.2f}:")
            logger.info(f"  Stop loss: ${stop_price:.2f}")
            logger.info(f"  Take profit: ${target_price:.2f}")
            
            return True
        else:
            logger.error("❌ Failed to calculate ATR")
            return False
            
    except Exception as e:
        logger.error(f"Error during ATR test: {e}", exc_info=True)
        return False
        
    finally:
        # Disconnect from TWS
        logger.info("\nDisconnecting from TWS...")
        tws_connection.disconnect()
        await asyncio.sleep(1)


async def main():
    """Main test function."""
    success = await test_atr_calculation()
    
    if success:
        logger.info("\n✅ ATR test completed successfully!")
    else:
        logger.error("\n❌ ATR test failed!")
        

if __name__ == "__main__":
    asyncio.run(main()) 