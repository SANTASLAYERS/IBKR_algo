#!/usr/bin/env python3
"""
Live Position Sizing Tests
==========================

Tests the complete position sizing system with real TWS connections and market data.
Validates position sizer calculations using actual current market prices.
"""

import pytest
import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.price.service import PriceService
from src.position.sizer import PositionSizer

logger = logging.getLogger("live_position_tests")


class TestPositionSizingLive:
    """Live tests for position sizing with real market data."""
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_position_sizing_with_real_prices(self, tws_credentials):
        """Test position sizing calculations using real market prices."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 510,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for position sizing test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            
            # Test with various allocation amounts
            test_allocations = [5000, 10000, 25000]  # $5K, $10K, $25K
            test_ticker = "AAPL"  # Use AAPL as it should have good data
            
            logger.info(f"📊 Getting current price for {test_ticker}...")
            current_price = await price_service.get_price(test_ticker, timeout=10.0)
            
            assert current_price is not None, f"Should get price for {test_ticker}"
            assert current_price > 0, f"Price should be positive: {current_price}"
            
            logger.info(f"💰 {test_ticker} current price: ${current_price:.2f}")
            
            # Test position sizing with different allocations
            results = []
            for allocation in test_allocations:
                logger.info(f"🔢 Calculating position size for ${allocation:,} allocation...")
                
                shares = position_sizer.calculate_shares(
                    allocation=allocation,
                    price=current_price,
                    side="BUY"
                )
                
                assert shares is not None, f"Should calculate shares for ${allocation:,}"
                assert shares > 0, f"Shares should be positive: {shares}"
                
                # Calculate efficiency
                actual_cost = shares * current_price
                efficiency = (actual_cost / allocation) * 100
                unused_cash = allocation - actual_cost
                
                result = {
                    "allocation": allocation,
                    "shares": shares,
                    "actual_cost": actual_cost,
                    "efficiency": efficiency,
                    "unused_cash": unused_cash
                }
                results.append(result)
                
                logger.info(f"✅ ${allocation:,} → {shares:,} shares = ${actual_cost:,.2f} ({efficiency:.1f}% efficient)")
                
            # Verify results make sense
            for i, result in enumerate(results):
                # Efficiency should be reasonable (>95% for most stocks)
                if current_price < 1000:  # Not a super expensive stock
                    assert result["efficiency"] >= 95.0, f"Efficiency too low: {result['efficiency']:.1f}%"
                
                # Larger allocations should result in more shares
                if i > 0:
                    assert result["shares"] > results[i-1]["shares"], "More allocation should mean more shares"
            
            logger.info("📈 Position sizing validation completed!")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_our_trading_tickers_position_sizing(self, tws_credentials):
        """Test position sizing for all our actual trading tickers."""
        # Our actual trading tickers
        tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]
        allocation = 10000  # Our standard $10K allocation
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 511,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for trading tickers test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            
            # Test each ticker
            position_results = []
            logger.info(f"📊 Testing ${allocation:,} position sizing for all tickers...")
            
            for ticker in tickers:
                logger.info(f"📈 Processing {ticker}...")
                
                # Get current price
                price = await price_service.get_price(ticker, timeout=10.0)
                
                if price is None:
                    logger.warning(f"⚠️ No price available for {ticker}")
                    continue
                
                # Calculate position size
                shares = position_sizer.calculate_shares(
                    allocation=allocation,
                    price=price,
                    side="BUY"
                )
                
                if shares is None:
                    logger.warning(f"⚠️ Cannot calculate position for {ticker} at ${price:.2f}")
                    continue
                
                # Calculate metrics
                actual_cost = shares * price
                efficiency = (actual_cost / allocation) * 100
                unused_cash = allocation - actual_cost
                
                result = {
                    "ticker": ticker,
                    "price": price,
                    "shares": shares,
                    "actual_cost": actual_cost,
                    "efficiency": efficiency,
                    "unused_cash": unused_cash
                }
                position_results.append(result)
                
                logger.info(f"✅ {ticker}: {shares:,} shares @ ${price:.2f} = ${actual_cost:,.2f} ({efficiency:.1f}%)")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
            
            # Summary analysis
            if position_results:
                avg_efficiency = sum(r["efficiency"] for r in position_results) / len(position_results)
                min_efficiency = min(r["efficiency"] for r in position_results)
                max_efficiency = max(r["efficiency"] for r in position_results)
                
                logger.info("📊 Position Sizing Summary:")
                logger.info(f"   Successful calculations: {len(position_results)}/{len(tickers)}")
                logger.info(f"   Average efficiency: {avg_efficiency:.1f}%")
                logger.info(f"   Efficiency range: {min_efficiency:.1f}% - {max_efficiency:.1f}%")
                
                # Verify reasonable results
                assert len(position_results) >= len(tickers) * 0.5, "Should succeed for at least half the tickers"
                assert avg_efficiency >= 90.0, f"Average efficiency too low: {avg_efficiency:.1f}%"
                
                # Show detailed table
                logger.info("💰 Detailed Position Sizing Results:")
                logger.info("   Ticker   Price    Shares      Cost     Efficiency  Unused")
                logger.info("   ------  -------  --------  ----------  ----------  ------")
                for result in position_results:
                    logger.info(f"   {result['ticker']:6s}  ${result['price']:6.2f}  {result['shares']:8,}  ${result['actual_cost']:9,.2f}  {result['efficiency']:9.1f}%  ${result['unused_cash']:5.0f}")
                
            else:
                pytest.fail("No successful position calculations - check market data availability")
                
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_extreme_price_scenarios(self, tws_credentials):
        """Test position sizing with extreme price scenarios."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 512,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for extreme scenarios test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            
            # Test scenarios
            allocation = 10000
            
            # Scenario 1: Very cheap stock (if available)
            # Try to find a cheap stock
            cheap_candidates = ["SOXL", "UVXY"]  # These might be cheaper
            cheap_price = None
            cheap_ticker = None
            
            for ticker in cheap_candidates:
                price = await price_service.get_price(ticker, timeout=5.0)
                if price and price < 50:  # Under $50
                    cheap_price = price
                    cheap_ticker = ticker
                    break
                await asyncio.sleep(0.5)
            
            if cheap_price:
                logger.info(f"📊 Testing cheap stock scenario: {cheap_ticker} @ ${cheap_price:.2f}")
                shares = position_sizer.calculate_shares(allocation, cheap_price, "BUY")
                
                if shares:
                    logger.info(f"✅ Cheap stock: {shares:,} shares of {cheap_ticker}")
                    assert shares >= 200, f"Should get many shares for cheap stock: {shares}"
                else:
                    logger.warning(f"⚠️ Could not calculate position for cheap stock")
            
            # Scenario 2: Expensive stock
            expensive_candidates = ["GOOGL", "NVDA"]  # These are typically expensive
            expensive_price = None
            expensive_ticker = None
            
            for ticker in expensive_candidates:
                price = await price_service.get_price(ticker, timeout=5.0)
                if price and price > 100:  # Over $100
                    expensive_price = price
                    expensive_ticker = ticker
                    break
                await asyncio.sleep(0.5)
            
            if expensive_price:
                logger.info(f"📊 Testing expensive stock scenario: {expensive_ticker} @ ${expensive_price:.2f}")
                shares = position_sizer.calculate_shares(allocation, expensive_price, "BUY")
                
                if shares:
                    logger.info(f"✅ Expensive stock: {shares:,} shares of {expensive_ticker}")
                    assert shares <= 100, f"Should get few shares for expensive stock: {shares}"
                else:
                    logger.warning(f"⚠️ Could not calculate position for expensive stock")
            
            # Scenario 3: Normal priced stock
            aapl_price = await price_service.get_price("AAPL", timeout=5.0)
            if aapl_price:
                logger.info(f"📊 Testing normal stock scenario: AAPL @ ${aapl_price:.2f}")
                shares = position_sizer.calculate_shares(allocation, aapl_price, "BUY")
                
                if shares:
                    logger.info(f"✅ Normal stock: {shares:,} shares of AAPL")
                    actual_cost = shares * aapl_price
                    efficiency = (actual_cost / allocation) * 100
                    assert efficiency >= 95.0, f"Efficiency should be high for normal stock: {efficiency:.1f}%"
            
            logger.info("🎯 Extreme scenarios test completed!")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)


if __name__ == "__main__":
    # Manual test runner
    async def main():
        print("🧪 Live Position Sizing Testing")
        print("=" * 50)
        
        from tests.integration.conftest import get_tws_credentials, is_tws_available
        
        credentials = get_tws_credentials()
        print(f"🔍 Checking TWS availability...")
        
        if not is_tws_available(credentials["host"], credentials["port"], credentials["client_id"] + 510):
            print("❌ TWS not available")
            return
        
        print("✅ TWS is available!")
        
        # Quick position sizing test
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 510,
            connection_timeout=10.0
        )
        
        tws_connection = TWSConnection(config)
        
        try:
            print("🔌 Connecting to TWS...")
            connected = await tws_connection.connect()
            if not connected:
                print("❌ Failed to connect")
                return
            
            print("✅ Connected!")
            
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer()
            
            # Test position sizing for our tickers
            tickers = ["AAPL", "UVXY", "SOXL"]
            allocation = 10000
            
            print(f"\n💰 Position sizing for ${allocation:,} allocation:")
            print("=" * 50)
            
            for ticker in tickers:
                price = await price_service.get_price(ticker)
                if price:
                    shares = position_sizer.calculate_shares(allocation, price, "BUY")
                    if shares:
                        actual_cost = shares * price
                        efficiency = (actual_cost / allocation) * 100
                        print(f"{ticker:6s}: {shares:4,} shares @ ${price:6.2f} = ${actual_cost:8,.2f} ({efficiency:5.1f}%)")
                    else:
                        print(f"{ticker:6s}: Cannot calculate position")
                else:
                    print(f"{ticker:6s}: No price available")
                
                await asyncio.sleep(0.5)
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
        
        print("\n🏁 Manual test completed!")
    
    asyncio.run(main()) 