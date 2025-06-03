#!/usr/bin/env python3
"""
Live Component Integration Tests
===============================

Tests the complete integration of all trading components with real TWS connections.
Validates end-to-end functionality: prices → position sizing → ATR calculations → trading decisions.
"""

import pytest
import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.price.service import PriceService
from src.position.sizer import PositionSizer
from src.indicators.manager import IndicatorManager

logger = logging.getLogger("live_integration_tests")


class TestComponentIntegrationLive:
    """Live tests for complete component integration."""
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_complete_trading_decision_flow(self, tws_credentials):
        """Test complete flow from price → position sizing → ATR → trading decision."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 530,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for complete integration test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create all services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test scenario parameters
            test_ticker = "AAPL"
            allocation = 10000  # $10K allocation
            
            logger.info(f"🎯 Testing complete trading decision flow for {test_ticker}")
            logger.info(f"   Allocation: ${allocation:,}")
            
            # Step 1: Get current market price
            logger.info("📊 Step 1: Getting current market price...")
            start_time = datetime.now()
            
            current_price = await price_service.get_price(test_ticker, timeout=10.0)
            
            price_time = (datetime.now() - start_time).total_seconds()
            
            assert current_price is not None, f"Failed to get price for {test_ticker}"
            assert current_price > 0, f"Invalid price: {current_price}"
            
            logger.info(f"✅ Current price: ${current_price:.2f} (fetched in {price_time:.2f}s)")
            
            # Step 2: Calculate position size
            logger.info("🔢 Step 2: Calculating position size...")
            start_time = datetime.now()
            
            shares = position_sizer.calculate_shares(
                allocation=allocation,
                price=current_price,
                side="BUY"
            )
            
            sizing_time = (datetime.now() - start_time).total_seconds()
            
            assert shares is not None, "Failed to calculate position size"
            assert shares > 0, f"Invalid shares: {shares}"
            
            actual_cost = shares * current_price
            efficiency = (actual_cost / allocation) * 100
            unused_cash = allocation - actual_cost
            
            logger.info(f"✅ Position size: {shares:,} shares")
            logger.info(f"   Actual cost: ${actual_cost:,.2f}")
            logger.info(f"   Efficiency: {efficiency:.1f}%")
            logger.info(f"   Unused cash: ${unused_cash:.2f}")
            logger.info(f"   Calculation time: {sizing_time:.4f}s")
            
            # Step 3: Get ATR for stop losses
            logger.info("📈 Step 3: Calculating ATR for stop losses...")
            start_time = datetime.now()
            
            atr_value = await indicator_manager.get_atr(test_ticker, period=14)
            
            atr_time = (datetime.now() - start_time).total_seconds()
            
            assert atr_value is not None, f"Failed to get ATR for {test_ticker}"
            assert atr_value > 0, f"Invalid ATR: {atr_value}"
            
            logger.info(f"✅ ATR (14-period, 10s): ${atr_value:.4f} (calculated in {atr_time:.2f}s)")
            
            # Step 4: Calculate trading levels
            logger.info("🎯 Step 4: Calculating trading levels...")
            start_time = datetime.now()
            
            # Our multipliers: 6x ATR for stop loss, 3x ATR for profit target
            stop_loss_distance = atr_value * 6
            profit_target_distance = atr_value * 3
            
            # For BUY position
            stop_loss_price = current_price - stop_loss_distance
            profit_target_price = current_price + profit_target_distance
            
            # Calculate risk metrics
            risk_amount = stop_loss_distance
            reward_amount = profit_target_distance
            risk_percent = (risk_amount / current_price) * 100
            reward_percent = (reward_amount / current_price) * 100
            risk_reward_ratio = reward_amount / risk_amount
            
            # Calculate dollar amounts
            risk_dollars = shares * risk_amount
            reward_dollars = shares * reward_amount
            
            levels_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Trading levels calculated:")
            logger.info(f"   Entry Price:    ${current_price:.2f}")
            logger.info(f"   Stop Loss:      ${stop_loss_price:.2f} (-${stop_loss_distance:.4f})")
            logger.info(f"   Profit Target:  ${profit_target_price:.2f} (+${profit_target_distance:.4f})")
            logger.info(f"   Risk/Reward:    1:{risk_reward_ratio:.2f}")
            logger.info(f"   Risk %:         {risk_percent:.2f}%")
            logger.info(f"   Reward %:       {reward_percent:.2f}%")
            logger.info(f"   Risk $:         ${risk_dollars:.2f}")
            logger.info(f"   Reward $:       ${reward_dollars:.2f}")
            logger.info(f"   Calculation time: {levels_time:.4f}s")
            
            # Step 5: Validate complete trading decision
            logger.info("✅ Step 5: Validating complete trading decision...")
            
            # Verify all values are reasonable
            assert stop_loss_price > 0, "Stop loss price should be positive"
            assert profit_target_price > current_price, "Profit target should be above entry for BUY"
            assert risk_percent < 10.0, f"Risk too high: {risk_percent:.2f}%"
            assert reward_percent > 0.5, f"Reward too low: {reward_percent:.2f}%"
            assert efficiency >= 95.0, f"Position sizing efficiency too low: {efficiency:.1f}%"
            
            # Verify our expected risk/reward ratio (1:0.5)
            expected_rr = 0.5
            assert abs(risk_reward_ratio - expected_rr) < 0.01, f"Risk/reward ratio should be ~{expected_rr:.2f}, got {risk_reward_ratio:.2f}"
            
            # Performance validation
            total_time = price_time + sizing_time + atr_time + levels_time
            logger.info(f"⏱️ Performance Summary:")
            logger.info(f"   Price fetch:    {price_time:.2f}s")
            logger.info(f"   Position sizing: {sizing_time:.4f}s")
            logger.info(f"   ATR calculation: {atr_time:.2f}s")
            logger.info(f"   Level calculation: {levels_time:.4f}s")
            logger.info(f"   Total time:     {total_time:.2f}s")
            
            assert total_time < 45.0, f"Complete flow took too long: {total_time:.2f}s"
            
            # Summary
            logger.info("🎉 Complete Trading Decision Summary:")
            logger.info(f"   📊 Ticker: {test_ticker}")
            logger.info(f"   💰 Allocation: ${allocation:,}")
            logger.info(f"   📈 Current Price: ${current_price:.2f}")
            logger.info(f"   🔢 Position: {shares:,} shares (${actual_cost:,.2f})")
            logger.info(f"   📉 Stop Loss: ${stop_loss_price:.2f} (${risk_dollars:.2f} risk)")
            logger.info(f"   📈 Profit Target: ${profit_target_price:.2f} (${reward_dollars:.2f} reward)")
            logger.info(f"   ⚡ Total Time: {total_time:.2f}s")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_multiple_ticker_integration(self, tws_credentials):
        """Test integration across multiple tickers simultaneously."""
        # Our actual trading tickers (subset for testing)
        test_tickers = ["AAPL", "UVXY", "SOXL", "TQQQ"]
        allocation = 10000  # $10K per ticker
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 531,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for multi-ticker integration test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create all services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            logger.info(f"🎯 Testing integration for {len(test_tickers)} tickers")
            
            # Process each ticker
            results = []
            total_start_time = datetime.now()
            
            for ticker in test_tickers:
                logger.info(f"📊 Processing {ticker}...")
                ticker_start_time = datetime.now()
                
                try:
                    # Get price and ATR concurrently
                    logger.info(f"   Fetching price and ATR for {ticker}...")
                    price_task = price_service.get_price(ticker, timeout=10.0)
                    atr_task = indicator_manager.get_atr(ticker, period=14)
                    
                    price, atr_value = await asyncio.gather(price_task, atr_task)
                    
                    if price is None:
                        logger.warning(f"⚠️ No price for {ticker}")
                        continue
                    
                    if atr_value is None:
                        logger.warning(f"⚠️ No ATR for {ticker}")
                        continue
                    
                    # Calculate position
                    shares = position_sizer.calculate_shares(allocation, price, "BUY")
                    if shares is None:
                        logger.warning(f"⚠️ Cannot calculate position for {ticker}")
                        continue
                    
                    # Calculate trading levels
                    actual_cost = shares * price
                    efficiency = (actual_cost / allocation) * 100
                    
                    stop_loss_distance = atr_value * 6
                    profit_target_distance = atr_value * 3
                    
                    stop_loss_price = price - stop_loss_distance
                    profit_target_price = price + profit_target_distance
                    
                    risk_percent = (stop_loss_distance / price) * 100
                    reward_percent = (profit_target_distance / price) * 100
                    
                    ticker_time = (datetime.now() - ticker_start_time).total_seconds()
                    
                    result = {
                        "ticker": ticker,
                        "price": price,
                        "atr": atr_value,
                        "shares": shares,
                        "actual_cost": actual_cost,
                        "efficiency": efficiency,
                        "stop_loss_price": stop_loss_price,
                        "profit_target_price": profit_target_price,
                        "risk_percent": risk_percent,
                        "reward_percent": reward_percent,
                        "processing_time": ticker_time
                    }
                    results.append(result)
                    
                    logger.info(f"✅ {ticker}: ${price:.2f}, {shares:,} shares, {efficiency:.1f}% efficiency ({ticker_time:.1f}s)")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error processing {ticker}: {e}")
                
                # Small delay between tickers
                await asyncio.sleep(0.5)
            
            total_time = (datetime.now() - total_start_time).total_seconds()
            
            # Analysis and validation
            logger.info("📊 Multi-Ticker Integration Analysis:")
            logger.info(f"   Successful: {len(results)}/{len(test_tickers)}")
            logger.info(f"   Total time: {total_time:.2f}s")
            logger.info(f"   Avg time per ticker: {total_time/len(test_tickers):.2f}s")
            
            if results:
                # Calculate aggregate metrics
                total_allocation = len(results) * allocation
                total_actual_cost = sum(r["actual_cost"] for r in results)
                avg_efficiency = sum(r["efficiency"] for r in results) / len(results)
                avg_risk = sum(r["risk_percent"] for r in results) / len(results)
                avg_reward = sum(r["reward_percent"] for r in results) / len(results)
                avg_processing_time = sum(r["processing_time"] for r in results) / len(results)
                
                logger.info(f"   Total allocation: ${total_allocation:,}")
                logger.info(f"   Total actual cost: ${total_actual_cost:,.2f}")
                logger.info(f"   Average efficiency: {avg_efficiency:.1f}%")
                logger.info(f"   Average risk: {avg_risk:.2f}%")
                logger.info(f"   Average reward: {avg_reward:.2f}%")
                logger.info(f"   Average processing time: {avg_processing_time:.2f}s")
                
                # Detailed table
                logger.info("📈 Detailed Results:")
                logger.info("   Ticker   Price    Shares     Cost     Eff%   Risk%  Reward%   Time")
                logger.info("   ------  -------  --------  --------  -----  -----  -------  -----")
                for r in results:
                    logger.info(f"   {r['ticker']:6s}  ${r['price']:6.2f}  {r['shares']:8,}  ${r['actual_cost']:7,.0f}  {r['efficiency']:4.1f}%  {r['risk_percent']:4.1f}%  {r['reward_percent']:6.1f}%  {r['processing_time']:4.1f}s")
                
                # Validation
                assert len(results) >= len(test_tickers) * 0.5, "Should succeed for at least half the tickers"
                assert avg_efficiency >= 90.0, f"Average efficiency too low: {avg_efficiency:.1f}%"
                assert avg_risk < 8.0, f"Average risk too high: {avg_risk:.2f}%"
                assert avg_processing_time < 20.0, f"Average processing too slow: {avg_processing_time:.2f}s"
                
            else:
                pytest.fail("No successful integrations - check market data availability")
                
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_error_resilience_integration(self, tws_credentials):
        """Test system resilience with various error conditions."""
        # Mix of valid and problematic tickers
        test_tickers = ["AAPL", "INVALID_TICKER_XYZ", "UVXY", "ANOTHER_INVALID"]
        allocation = 10000
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 532,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for error resilience test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create all services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            logger.info("🧪 Testing error resilience with mixed valid/invalid tickers")
            
            successes = 0
            errors = 0
            
            for ticker in test_tickers:
                logger.info(f"📊 Testing {ticker}...")
                
                try:
                    # Attempt complete flow with shorter timeouts for invalid tickers
                    price = await price_service.get_price(ticker, timeout=5.0)
                    
                    if price is None:
                        logger.info(f"   ⚠️ No price for {ticker} (expected for invalid tickers)")
                        errors += 1
                        continue
                    
                    atr_value = await indicator_manager.get_atr(ticker, period=14)
                    
                    if atr_value is None:
                        logger.info(f"   ⚠️ No ATR for {ticker}")
                        errors += 1
                        continue
                    
                    shares = position_sizer.calculate_shares(allocation, price, "BUY")
                    
                    if shares is None:
                        logger.info(f"   ⚠️ Cannot calculate position for {ticker}")
                        errors += 1
                        continue
                    
                    # If we get here, everything worked
                    successes += 1
                    logger.info(f"   ✅ {ticker}: Complete flow successful")
                    
                except Exception as e:
                    logger.info(f"   ❌ {ticker}: Exception handled gracefully: {e}")
                    errors += 1
                
                await asyncio.sleep(0.5)
            
            logger.info("🛡️ Error Resilience Summary:")
            logger.info(f"   Total tickers tested: {len(test_tickers)}")
            logger.info(f"   Successful flows: {successes}")
            logger.info(f"   Handled errors: {errors}")
            logger.info(f"   Success rate: {successes/len(test_tickers)*100:.1f}%")
            
            # Verify system handled errors gracefully
            assert successes > 0, "Should have at least some successful flows"
            assert errors > 0, "Should have encountered some errors (due to invalid tickers)"
            
            # Connection should still be healthy
            assert tws_connection.is_connected(), "Connection should remain healthy after errors"
            
            logger.info("✅ System demonstrated good error resilience")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)


if __name__ == "__main__":
    # Manual test runner
    async def main():
        print("🧪 Live Component Integration Testing")
        print("=" * 60)
        
        from tests.integration.conftest import get_tws_credentials, is_tws_available
        
        credentials = get_tws_credentials()
        print(f"🔍 Checking TWS availability...")
        
        if not is_tws_available(credentials["host"], credentials["port"], credentials["client_id"] + 530):
            print("❌ TWS not available")
            return
        
        print("✅ TWS is available!")
        
        # Quick integration test
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 530,
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
            
            # Create services
            price_service = PriceService(tws_connection)
            position_sizer = PositionSizer()
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test complete flow for AAPL
            ticker = "AAPL"
            allocation = 10000
            
            print(f"\n🎯 Complete integration test for {ticker}:")
            print("=" * 50)
            
            # Get price
            print("📊 Getting price...")
            price = await price_service.get_price(ticker)
            
            if not price:
                print("❌ No price available")
                return
            
            print(f"✅ Price: ${price:.2f}")
            
            # Calculate position
            print("🔢 Calculating position...")
            shares = position_sizer.calculate_shares(allocation, price, "BUY")
            
            if not shares:
                print("❌ Cannot calculate position")
                return
            
            actual_cost = shares * price
            efficiency = (actual_cost / allocation) * 100
            print(f"✅ Position: {shares:,} shares = ${actual_cost:,.2f} ({efficiency:.1f}%)")
            
            # Get ATR
            print("📈 Getting ATR...")
            atr = await indicator_manager.get_atr(ticker)
            
            if not atr:
                print("❌ No ATR available")
                return
            
            # Calculate levels
            stop_loss = price - (atr * 6)
            profit_target = price + (atr * 3)
            
            print(f"✅ ATR: ${atr:.4f}")
            print(f"✅ Stop Loss: ${stop_loss:.2f}")
            print(f"✅ Profit Target: ${profit_target:.2f}")
            
            print(f"\n🎉 Complete integration successful!")
            print(f"   Entry: ${price:.2f}")
            print(f"   Size: {shares:,} shares")
            print(f"   Stop: ${stop_loss:.2f}")
            print(f"   Target: ${profit_target:.2f}")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
        
        print("\n🏁 Manual test completed!")
    
    asyncio.run(main()) 