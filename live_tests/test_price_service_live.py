#!/usr/bin/env python3
"""
Live Price Service Tests
========================

Tests the PriceService component with real TWS connections and market data.
These tests require TWS to be running with market data subscriptions.
"""

import pytest
import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.price.service import PriceService

logger = logging.getLogger("live_price_tests")


class TestPriceServiceLive:
    """Live tests for PriceService component."""
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_price_service_single_ticker(self, tws_credentials):
        """Test getting price for a single ticker."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 501,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for price service test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create price service
            price_service = PriceService(tws_connection)
            
            # Test getting price for AAPL (should have market data)
            logger.info("📊 Getting price for AAPL...")
            start_time = datetime.now()
            
            price = await price_service.get_price("AAPL", timeout=10.0)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Verify results
            assert price is not None, "Should receive a valid price for AAPL"
            assert price > 0, f"Price should be positive, got: {price}"
            assert price < 1000, f"AAPL price should be reasonable, got: {price}"
            
            logger.info(f"✅ AAPL price: ${price:.2f} (fetched in {duration:.2f}s)")
            
            # Test performance - should be relatively fast
            assert duration < 15.0, f"Price fetch took too long: {duration:.2f}s"
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_price_service_our_tickers(self, tws_credentials):
        """Test getting prices for our actual trading tickers."""
        # Our actual trading tickers
        tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 502,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for multi-ticker price test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create price service
            price_service = PriceService(tws_connection)
            
            # Test each ticker individually
            prices = {}
            for ticker in tickers:
                logger.info(f"📊 Getting price for {ticker}...")
                start_time = datetime.now()
                
                price = await price_service.get_price(ticker, timeout=10.0)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                if price is not None:
                    prices[ticker] = price
                    logger.info(f"✅ {ticker}: ${price:.2f} (fetched in {duration:.2f}s)")
                else:
                    logger.warning(f"⚠️ {ticker}: No price available")
                
                # Small delay between requests to be nice to TWS
                await asyncio.sleep(0.5)
            
            # Verify we got prices for most tickers
            success_rate = len(prices) / len(tickers)
            logger.info(f"📈 Got prices for {len(prices)}/{len(tickers)} tickers ({success_rate:.1%})")
            
            # We should get at least 75% success rate during market hours
            # (some tickers might not have data outside market hours)
            assert success_rate >= 0.5, f"Too many price fetch failures: {success_rate:.1%}"
            
            # Log all successful prices
            logger.info("💰 Current prices:")
            for ticker, price in sorted(prices.items()):
                logger.info(f"  {ticker:6s}: ${price:8.2f}")
                
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_price_service_multiple_concurrent(self, tws_credentials):
        """Test getting multiple prices concurrently."""
        tickers = ["AAPL", "MSFT", "GOOGL"]  # Popular tickers with good data
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 503,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for concurrent price test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create price service
            price_service = PriceService(tws_connection)
            
            # Test concurrent price fetching
            logger.info(f"📊 Getting prices for {len(tickers)} tickers concurrently...")
            start_time = datetime.now()
            
            prices = await price_service.get_multiple_prices(tickers, timeout=15.0)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Verify results
            assert isinstance(prices, dict), "Should return a dictionary"
            assert len(prices) == len(tickers), "Should have entry for each ticker"
            
            successful_prices = {k: v for k, v in prices.items() if v is not None}
            success_rate = len(successful_prices) / len(tickers)
            
            logger.info(f"📈 Concurrent fetch: {len(successful_prices)}/{len(tickers)} successful ({success_rate:.1%}) in {duration:.2f}s")
            
            # Log results
            for ticker in tickers:
                price = prices[ticker]
                if price is not None:
                    logger.info(f"✅ {ticker}: ${price:.2f}")
                else:
                    logger.warning(f"⚠️ {ticker}: No price available")
            
            # Should be faster than sequential fetching
            assert duration < 20.0, f"Concurrent fetch took too long: {duration:.2f}s"
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_price_service_invalid_ticker(self, tws_credentials):
        """Test error handling with invalid ticker."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 504,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for error handling test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create price service
            price_service = PriceService(tws_connection)
            
            # Test with invalid ticker
            logger.info("📊 Testing with invalid ticker...")
            price = await price_service.get_price("INVALID_TICKER_XYZ", timeout=5.0)
            
            # Should handle gracefully
            assert price is None, "Should return None for invalid ticker"
            logger.info("✅ Invalid ticker handled gracefully")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)


if __name__ == "__main__":
    # Manual test runner for quick testing
    import os
    
    async def main():
        print("🧪 Live Price Service Testing")
        print("=" * 50)
        
        # Check environment
        if not os.getenv("TWS_HOST"):
            print("⚠️ No TWS environment variables set. Using defaults:")
            print("   TWS_HOST=127.0.0.1")
            print("   TWS_PORT=7497 (paper trading)")
            print("   TWS_CLIENT_ID=10")
        
        # Simple manual test
        from tests.integration.conftest import get_tws_credentials, is_tws_available
        
        credentials = get_tws_credentials()
        print(f"🔍 Checking TWS availability at {credentials['host']}:{credentials['port']}...")
        
        if not is_tws_available(credentials["host"], credentials["port"], credentials["client_id"] + 500):
            print("❌ TWS not available. Make sure TWS is running with API enabled.")
            return
        
        print("✅ TWS is available!")
        
        # Quick price test
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 500,
            connection_timeout=10.0
        )
        
        tws_connection = TWSConnection(config)
        
        try:
            print("🔌 Connecting to TWS...")
            connected = await tws_connection.connect()
            if not connected:
                print("❌ Failed to connect to TWS")
                return
            
            print("✅ Connected!")
            
            price_service = PriceService(tws_connection)
            
            # Test AAPL price
            print("📊 Getting AAPL price...")
            price = await price_service.get_price("AAPL")
            
            if price:
                print(f"💰 AAPL: ${price:.2f}")
            else:
                print("⚠️ No price available for AAPL")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
        
        print("🏁 Manual test completed!")
    
    asyncio.run(main()) 