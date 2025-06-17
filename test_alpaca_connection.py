#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Alpaca Connection

Simple test script to verify Alpaca connection is working.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.broker_config import BrokerConfig, AlpacaConfig
from src.alpaca_connection import AlpacaConnection
from src.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()


async def test_connection():
    """Test Alpaca connection and basic operations."""
    logger.info("=" * 50)
    logger.info("Testing Alpaca Connection")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = BrokerConfig.from_env()
        
        if not config.validate():
            logger.error("Configuration validation failed")
            return False
        
        logger.info(f"✅ Configuration loaded - Mode: {config.alpaca.trading_mode}")
        
        # Create connection
        logger.info("Creating Alpaca connection...")
        connection = AlpacaConnection(config.alpaca)
        
        # Connect
        logger.info("Connecting to Alpaca...")
        connected = await connection.connect()
        
        if not connected:
            logger.error("Failed to connect to Alpaca")
            return False
        
        logger.info("✅ Connected successfully!")
        
        # Get account info
        logger.info("\nGetting account information...")
        account = connection.get_account()
        if account:
            logger.info(f"✅ Account: {account.account_number}")
            logger.info(f"✅ Buying Power: ${account.buying_power}")
            logger.info(f"✅ Portfolio Value: ${account.portfolio_value}")
            logger.info(f"✅ Cash: ${account.cash}")
        
        # Get positions
        logger.info("\nGetting positions...")
        positions = connection.get_positions()
        logger.info(f"✅ Found {len(positions)} positions")
        for position in positions:
            logger.info(f"  - {position.symbol}: {position.qty} shares @ ${position.avg_entry_price}")
        
        # Test order placement (paper trading only)
        if config.alpaca.is_paper_trading:
            logger.info("\nTesting order placement (paper trading)...")
            
            # Get next order ID
            order_id = connection.get_next_order_id()
            logger.info(f"Generated order ID: {order_id}")
            
            # Place a small test order
            logger.info("Placing test market order for 1 share of AAPL...")
            connection.placeOrder(
                orderId=order_id,
                symbol="AAPL",
                quantity=1,
                order_type="MKT",
                side="BUY"
            )
            
            # Wait a moment for order to process
            await asyncio.sleep(2)
            
            # Cancel the order
            logger.info(f"Cancelling order {order_id}...")
            connection.cancelOrder(order_id)
            
            logger.info("✅ Order test completed")
        
        # Disconnect
        logger.info("\nDisconnecting...")
        connection.disconnect()
        logger.info("✅ Disconnected successfully")
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All tests passed!")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def main():
    """Main entry point."""
    success = await test_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv('ALPACA_API_KEY') or not os.getenv('ALPACA_SECRET_KEY'):
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        print("Please set these environment variables or create a .env file")
        sys.exit(1)
    
    # Run the test
    asyncio.run(main()) 