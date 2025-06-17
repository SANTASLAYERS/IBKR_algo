#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Main Trading App Initialization

Tests the initialization of the main trading application with Alpaca.
"""

import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_trading_app import TradingApp
from src.logger import get_logger

logger = get_logger(__name__)


async def test_app_initialization():
    """Test that the main trading app initializes correctly."""
    logger.info("=" * 50)
    logger.info("Testing Main Trading App Initialization")
    logger.info("=" * 50)
    
    # Set up test environment variables
    test_env = {
        'ALPACA_API_KEY': 'test_api_key',
        'ALPACA_SECRET_KEY': 'test_secret_key',
        'ALPACA_TRADING_MODE': 'paper',
        'MAX_POSITION_SIZE': '1000',
        'MAX_DAILY_TRADES': '100',
        'RISK_PER_TRADE': '0.02'
    }
    
    with patch.dict(os.environ, test_env):
        # Mock the Alpaca connection to avoid actual API calls
        with patch('src.alpaca_connection.AlpacaConnection') as MockConnection:
            # Set up mock connection
            mock_connection = MagicMock()
            mock_connection.connect = asyncio.coroutine(lambda: True)
            mock_connection.is_connected.return_value = True
            mock_connection.get_next_order_id.return_value = "TEST_ORDER_1"
            MockConnection.return_value = mock_connection
            
            # Create app instance
            app = TradingApp()
            
            # Test initialization
            logger.info("Initializing trading app...")
            success = await app.initialize()
            
            if success:
                logger.info("✅ App initialized successfully")
                
                # Verify components were created
                assert app.config is not None, "Config not initialized"
                assert app.connection is not None, "Connection not initialized"
                assert app.event_bus is not None, "EventBus not initialized"
                assert app.order_manager is not None, "OrderManager not initialized"
                assert app.rule_engine is not None, "RuleEngine not initialized"
                assert app.api_client is not None, "APIClient not initialized"
                
                logger.info("✅ All components initialized")
                
                # Verify configuration
                logger.info(f"✅ Trading mode: {app.config.alpaca.trading_mode}")
                logger.info(f"✅ Max position size: {app.config.trading.max_position_size}")
                logger.info(f"✅ Risk per trade: {app.config.trading.risk_per_trade}")
                
                # Test shutdown
                logger.info("Testing shutdown...")
                await app.shutdown()
                logger.info("✅ App shutdown successfully")
                
                return True
            else:
                logger.error("❌ App initialization failed")
                return False


async def test_missing_credentials():
    """Test that app handles missing credentials gracefully."""
    logger.info("\nTesting missing credentials handling...")
    
    # Clear environment variables
    with patch.dict(os.environ, {}, clear=True):
        app = TradingApp()
        
        try:
            success = await app.initialize()
            if not success:
                logger.info("✅ App correctly failed to initialize with missing credentials")
                return True
            else:
                logger.error("❌ App should have failed with missing credentials")
                return False
        except ValueError as e:
            logger.info(f"✅ Got expected error: {e}")
            return True
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False


async def main():
    """Run all tests."""
    all_passed = True
    
    # Test successful initialization
    if not await test_app_initialization():
        all_passed = False
    
    # Test error handling
    if not await test_missing_credentials():
        all_passed = False
    
    logger.info("\n" + "=" * 50)
    if all_passed:
        logger.info("✅ All tests passed!")
    else:
        logger.info("❌ Some tests failed")
    logger.info("=" * 50)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 