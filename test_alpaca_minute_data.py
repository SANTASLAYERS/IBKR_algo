#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Alpaca Minute Data Manager

Tests the AlpacaMinuteBarManager functionality.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import logging

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.broker_config import BrokerConfig
from src.alpaca_connection import AlpacaConnection
from src.logger import get_logger

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

# Also set the alpaca manager logger to DEBUG
logging.getLogger('src.minute_data.alpaca_manager').setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()


async def test_historical_data():
    """Test fetching historical minute bar data."""
    logger.info("=" * 50)
    logger.info("Testing Alpaca Minute Data Manager")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = BrokerConfig.from_env()
        
        if not config.validate():
            logger.error("Configuration validation failed")
            return False
        
        # Create and connect
        logger.info("Creating Alpaca connection...")
        connection = AlpacaConnection(config.alpaca)
        
        logger.info("Connecting to Alpaca...")
        connected = await connection.connect()
        
        if not connected:
            logger.error("Failed to connect to Alpaca")
            return False
        
        logger.info("✅ Connected successfully!")
        
        # Test 1: Get historical data using convenience method
        logger.info("\n" + "-" * 40)
        logger.info("Test 1: Get historical AAPL data")
        logger.info("-" * 40)
        
        # Use a specific known trading day (December 13, 2024 was a Friday)
        end_time = datetime(2024, 12, 13, 20, 0, 0, tzinfo=timezone.utc)  # 4 PM ET
        start_time = datetime(2024, 12, 13, 13, 30, 0, tzinfo=timezone.utc)  # 9:30 AM ET
        
        collection = await connection.minute_bar_manager.get_historical_bars(
            symbol="AAPL",
            start=start_time,
            end=end_time,
            bar_size="1 min",
            use_cache=False  # Don't use cache for testing
        )
        
        logger.info(f"✅ Retrieved {len(collection)} minute bars")
        if len(collection) > 0:
            first_bar = collection[0]
            last_bar = collection[-1]
            logger.info(f"First bar: {first_bar.timestamp} - O:{first_bar.open_price} H:{first_bar.high_price} L:{first_bar.low_price} C:{first_bar.close_price} V:{first_bar.volume}")
            logger.info(f"Last bar: {last_bar.timestamp} - O:{last_bar.open_price} H:{last_bar.high_price} L:{last_bar.low_price} C:{last_bar.close_price} V:{last_bar.volume}")
        
        # Test 2: Get historical data with specific date range
        logger.info("\n" + "-" * 40)
        logger.info("Test 2: Get specific date range for SPY")
        logger.info("-" * 40)
        
        # Use December 12-13, 2024
        end_date = datetime(2024, 12, 13, 20, 0, 0, tzinfo=timezone.utc)
        start_date = datetime(2024, 12, 12, 13, 30, 0, tzinfo=timezone.utc)
        
        collection = await connection.minute_bar_manager.get_historical_bars(
            symbol="SPY",
            start=start_date,
            end=end_date,
            bar_size="5 mins",
            use_cache=False
        )
        
        logger.info(f"✅ Retrieved {len(collection)} bars for SPY")
        if len(collection) > 0:
            logger.info(f"Date range: {collection[0].timestamp} to {collection[-1].timestamp}")
        
        # Test 3: Test caching
        logger.info("\n" + "-" * 40)
        logger.info("Test 3: Test caching functionality")
        logger.info("-" * 40)
        
        # Use December 13, 2024
        cache_end = datetime(2024, 12, 13, 16, 0, 0, tzinfo=timezone.utc)
        cache_start = datetime(2024, 12, 13, 14, 0, 0, tzinfo=timezone.utc)
        
        # First request (will fetch from API)
        import time
        start_time = time.time()
        collection1 = await connection.minute_bar_manager.get_historical_bars(
            symbol="TSLA",
            start=cache_start,
            end=cache_end,
            bar_size="1 min",
            use_cache=True
        )
        fetch_time = time.time() - start_time
        logger.info(f"First request took {fetch_time:.2f} seconds, got {len(collection1)} bars")
        
        # Second request (should use cache)
        start_time = time.time()
        collection2 = await connection.minute_bar_manager.get_historical_bars(
            symbol="TSLA",
            start=cache_start,
            end=cache_end,
            bar_size="1 min",
            use_cache=True
        )
        cache_time = time.time() - start_time
        logger.info(f"Second request took {cache_time:.2f} seconds, got {len(collection2)} bars")
        if cache_time > 0:
            logger.info(f"✅ Cache speedup: {fetch_time/cache_time:.1f}x faster")
        
        # Test 4: Get latest bar
        logger.info("\n" + "-" * 40)
        logger.info("Test 4: Get latest bar for MSFT")
        logger.info("-" * 40)
        
        latest_bar = await connection.minute_bar_manager.get_latest_bar("MSFT")
        if latest_bar:
            logger.info(f"✅ Latest bar: {latest_bar.timestamp} - O:{latest_bar.open_price} H:{latest_bar.high_price} L:{latest_bar.low_price} C:{latest_bar.close_price} V:{latest_bar.volume}")
        else:
            logger.warning("No latest bar available (market may be closed)")
        
        # Test 5: Different timeframes
        logger.info("\n" + "-" * 40)
        logger.info("Test 5: Test different timeframes")
        logger.info("-" * 40)
        
        # Use December 13, 2024
        tf_end = datetime(2024, 12, 13, 20, 0, 0, tzinfo=timezone.utc)
        tf_start = datetime(2024, 12, 13, 13, 30, 0, tzinfo=timezone.utc)
        
        timeframes = ["1 min", "5 mins", "15 mins", "1 hour"]
        for tf in timeframes:
            try:
                collection = await connection.minute_bar_manager.get_historical_bars(
                    symbol="QQQ",
                    start=tf_start,
                    end=tf_end,
                    bar_size=tf,
                    use_cache=False
                )
                logger.info(f"✅ {tf}: Retrieved {len(collection)} bars")
            except Exception as e:
                logger.error(f"❌ {tf}: Failed - {e}")
        
        # Disconnect
        logger.info("\nDisconnecting...")
        connection.disconnect()
        logger.info("✅ Disconnected successfully")
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All minute data tests completed!")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def test_streaming():
    """Test real-time bar streaming (requires market hours)."""
    logger.info("\n" + "=" * 50)
    logger.info("Testing Real-time Bar Streaming")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config = BrokerConfig.from_env()
        connection = AlpacaConnection(config.alpaca)
        
        # Connect
        if not await connection.connect():
            logger.error("Failed to connect")
            return False
        
        logger.info("✅ Connected successfully!")
        
        # Check if market is open
        clock = connection._trading_client.get_clock()
        if not clock.is_open:
            logger.warning("Market is closed. Real-time streaming test skipped.")
            logger.info(f"Market opens at: {clock.next_open}")
            connection.disconnect()
            return True
        
        logger.info("Market is open - testing real-time streaming")
        
        # Define callback for bar updates
        bars_received = []
        
        def on_bar(bar):
            bars_received.append(bar)
            logger.info(f"Bar received: {bar.symbol} @ {bar.timestamp} - C:{bar.close_price} V:{bar.volume}")
        
        # Subscribe to a few symbols
        symbols = ["AAPL", "SPY", "TSLA"]
        logger.info(f"Subscribing to bars for: {', '.join(symbols)}")
        connection.minute_bar_manager.subscribe_bars(symbols, callback=on_bar)
        
        # Wait for some bars
        logger.info("Waiting 2 minutes for bar updates...")
        await asyncio.sleep(120)
        
        # Unsubscribe
        logger.info("Unsubscribing...")
        connection.minute_bar_manager.unsubscribe_bars(symbols)
        
        logger.info(f"✅ Received {len(bars_received)} bar updates")
        
        # Disconnect
        connection.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"Streaming test failed: {e}", exc_info=True)
        return False


async def main():
    """Main entry point."""
    # Test historical data
    success = await test_historical_data()
    
    if success:
        # Ask if user wants to test streaming
        response = input("\nDo you want to test real-time streaming? (requires market hours) (y/n): ")
        if response.lower() == 'y':
            await test_streaming()


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv('ALPACA_API_KEY') or not os.getenv('ALPACA_SECRET_KEY'):
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        print("Please set these environment variables or create a .env file")
        sys.exit(1)
    
    # Run the test
    asyncio.run(main()) 