#!/usr/bin/env python3
"""
Live ATR System Tests
====================

Tests the ATR indicator system with real TWS connections and 10-second market data.
Validates ATR calculations and stop-loss/profit-target multipliers.
"""

import pytest
import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.indicators.manager import IndicatorManager

logger = logging.getLogger("live_atr_tests")


class TestATRSystemLive:
    """Live tests for ATR indicator system."""
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_atr_calculation_single_ticker(self, tws_credentials):
        """Test ATR calculation for a single ticker with real 10-second data."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 520,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for ATR calculation test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create indicator manager
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test with AAPL (should have good data)
            test_ticker = "AAPL"
            logger.info(f"📊 Calculating 10-second ATR for {test_ticker}...")
            
            start_time = datetime.now()
            atr_value = await indicator_manager.get_atr(test_ticker, period=14)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            
            # Verify results
            assert atr_value is not None, f"Should receive ATR value for {test_ticker}"
            assert atr_value > 0, f"ATR should be positive, got: {atr_value}"
            assert atr_value < 100, f"ATR should be reasonable for {test_ticker}, got: {atr_value}"
            
            logger.info(f"✅ {test_ticker} 10s ATR: ${atr_value:.4f} (calculated in {duration:.2f}s)")
            
            # Test stop loss and profit target calculations
            current_price = 150.0  # Example price for calculations
            
            # Our multipliers: 6x ATR for stop loss, 3x ATR for profit target
            stop_loss_distance = atr_value * 6
            profit_target_distance = atr_value * 3
            
            # For a BUY position
            stop_loss_price = current_price - stop_loss_distance
            profit_target_price = current_price + profit_target_distance
            
            logger.info(f"📈 Trading levels (example @ ${current_price:.2f}):")
            logger.info(f"   Stop Loss:     ${stop_loss_price:.2f} (-${stop_loss_distance:.4f})")
            logger.info(f"   Profit Target: ${profit_target_price:.2f} (+${profit_target_distance:.4f})")
            
            # Verify reasonable risk/reward
            risk_reward_ratio = profit_target_distance / stop_loss_distance
            logger.info(f"   Risk/Reward:   1:{risk_reward_ratio:.2f}")
            
            # Should be 1:0.5 ratio (risk twice as much as reward)
            expected_ratio = 3.0 / 6.0  # 0.5
            assert abs(risk_reward_ratio - expected_ratio) < 0.01, f"Risk/reward ratio should be ~{expected_ratio:.2f}, got {risk_reward_ratio:.2f}"
            
            # Performance check
            assert duration < 35.0, f"ATR calculation took too long: {duration:.2f}s"
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_atr_for_our_trading_tickers(self, tws_credentials):
        """Test ATR calculations for all our actual trading tickers."""
        # Our actual trading tickers
        tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]
        
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 521,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for multi-ticker ATR test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create indicator manager
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test each ticker
            atr_results = []
            logger.info("📊 Calculating 10-second ATR for all trading tickers...")
            
            for ticker in tickers:
                logger.info(f"📈 Processing {ticker}...")
                start_time = datetime.now()
                
                try:
                    atr_value = await indicator_manager.get_atr(ticker, period=14)
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    if atr_value is not None:
                        # Calculate trading levels
                        stop_loss_multiplier = atr_value * 6
                        profit_target_multiplier = atr_value * 3
                        
                        result = {
                            "ticker": ticker,
                            "atr": atr_value,
                            "stop_loss_distance": stop_loss_multiplier,
                            "profit_target_distance": profit_target_multiplier,
                            "duration": duration
                        }
                        atr_results.append(result)
                        
                        logger.info(f"✅ {ticker}: ATR=${atr_value:.4f}, SL=${stop_loss_multiplier:.4f}, PT=${profit_target_multiplier:.4f} ({duration:.1f}s)")
                    else:
                        logger.warning(f"⚠️ {ticker}: No ATR data available")
                        
                except Exception as e:
                    logger.warning(f"⚠️ {ticker}: Error calculating ATR: {e}")
                
                # Small delay between requests
                await asyncio.sleep(1.0)
            
            # Analysis of results
            if atr_results:
                logger.info("📊 ATR Analysis Summary:")
                logger.info(f"   Successful calculations: {len(atr_results)}/{len(tickers)}")
                
                # Calculate statistics
                atr_values = [r["atr"] for r in atr_results]
                avg_atr = sum(atr_values) / len(atr_values)
                min_atr = min(atr_values)
                max_atr = max(atr_values)
                
                avg_duration = sum(r["duration"] for r in atr_results) / len(atr_results)
                
                logger.info(f"   Average ATR: ${avg_atr:.4f}")
                logger.info(f"   ATR range: ${min_atr:.4f} - ${max_atr:.4f}")
                logger.info(f"   Average calculation time: {avg_duration:.1f}s")
                
                # Detailed results table
                logger.info("📈 Detailed ATR Results:")
                logger.info("   Ticker     ATR      Stop Loss   Profit Target   Time")
                logger.info("   ------   -------   -----------  -------------   ----")
                for result in atr_results:
                    logger.info(f"   {result['ticker']:6s}   ${result['atr']:6.4f}   ${result['stop_loss_distance']:10.4f}   ${result['profit_target_distance']:12.4f}   {result['duration']:3.0f}s")
                
                # Verify reasonable results
                assert len(atr_results) >= len(tickers) * 0.4, "Should succeed for at least 40% of tickers"
                assert avg_atr > 0, "Average ATR should be positive"
                assert avg_duration < 25.0, f"Average calculation time too slow: {avg_duration:.1f}s"
                
            else:
                pytest.fail("No successful ATR calculations - check market data availability")
                
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_atr_different_periods(self, tws_credentials):
        """Test ATR with different periods to validate calculation stability."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 522,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for ATR period comparison test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create indicator manager
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test different ATR periods
            test_ticker = "AAPL"
            test_periods = [7, 14, 21]  # Different ATR periods
            
            logger.info(f"📊 Testing different ATR periods for {test_ticker}...")
            
            atr_by_period = {}
            for period in test_periods:
                logger.info(f"📈 Calculating ATR with period {period}...")
                
                atr_value = await indicator_manager.get_atr(test_ticker, period=period)
                
                if atr_value is not None:
                    atr_by_period[period] = atr_value
                    logger.info(f"✅ ATR({period}): ${atr_value:.4f}")
                else:
                    logger.warning(f"⚠️ No ATR data for period {period}")
                
                await asyncio.sleep(0.5)
            
            # Analysis
            if len(atr_by_period) >= 2:
                logger.info("📊 ATR Period Comparison:")
                for period, atr in atr_by_period.items():
                    stop_loss = atr * 6
                    profit_target = atr * 3
                    logger.info(f"   ATR({period:2d}): ${atr:.4f} → SL: ${stop_loss:.4f}, PT: ${profit_target:.4f}")
                
                # Generally, longer periods should give more stable (often higher) ATR values
                atr_values = list(atr_by_period.values())
                assert all(atr > 0 for atr in atr_values), "All ATR values should be positive"
                
                # Check reasonable range
                min_atr = min(atr_values)
                max_atr = max(atr_values)
                ratio = max_atr / min_atr if min_atr > 0 else float('inf')
                
                logger.info(f"📈 ATR range across periods: ${min_atr:.4f} - ${max_atr:.4f} (ratio: {ratio:.2f})")
                
                # ATR values shouldn't vary too wildly across periods
                assert ratio < 5.0, f"ATR values vary too much across periods: {ratio:.2f}x"
                
            else:
                logger.warning("⚠️ Insufficient ATR data for period comparison")
                
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)
    
    @pytest.mark.usefixtures("check_live_tws")
    @pytest.mark.asyncio
    async def test_atr_stop_loss_scenarios(self, tws_credentials):
        """Test realistic stop loss scenarios using ATR."""
        # Create TWS configuration
        config = TWSConfig(
            host=tws_credentials["host"],
            port=tws_credentials["port"],
            client_id=tws_credentials["client_id"] + 523,  # Unique client ID
            connection_timeout=10.0
        )
        
        # Create and connect to TWS
        tws_connection = TWSConnection(config)
        
        try:
            logger.info("🔌 Connecting to TWS for stop loss scenario test...")
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            logger.info("✅ Connected to TWS")
            
            # Create indicator manager
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test realistic trading scenarios
            test_scenarios = [
                {"ticker": "AAPL", "entry_price": 150.0, "side": "BUY"},
                {"ticker": "UVXY", "entry_price": 15.0, "side": "BUY"},
                {"ticker": "SOXL", "entry_price": 25.0, "side": "SELL"}
            ]
            
            logger.info("📊 Testing realistic stop loss scenarios...")
            
            for scenario in test_scenarios:
                ticker = scenario["ticker"]
                entry_price = scenario["entry_price"]
                side = scenario["side"]
                
                logger.info(f"📈 Scenario: {side} {ticker} @ ${entry_price:.2f}")
                
                # Get ATR
                atr_value = await indicator_manager.get_atr(ticker, period=14)
                
                if atr_value is None:
                    logger.warning(f"⚠️ No ATR data for {ticker}")
                    continue
                
                # Calculate stop loss and profit target
                stop_loss_distance = atr_value * 6
                profit_target_distance = atr_value * 3
                
                if side == "BUY":
                    stop_loss_price = entry_price - stop_loss_distance
                    profit_target_price = entry_price + profit_target_distance
                else:  # SELL
                    stop_loss_price = entry_price + stop_loss_distance
                    profit_target_price = entry_price - profit_target_distance
                
                # Calculate risk metrics
                risk_amount = abs(entry_price - stop_loss_price)
                reward_amount = abs(profit_target_price - entry_price)
                risk_percent = (risk_amount / entry_price) * 100
                reward_percent = (reward_amount / entry_price) * 100
                
                logger.info(f"   ATR: ${atr_value:.4f}")
                logger.info(f"   Stop Loss: ${stop_loss_price:.2f} ({risk_percent:.1f}% risk)")
                logger.info(f"   Profit Target: ${profit_target_price:.2f} ({reward_percent:.1f}% reward)")
                logger.info(f"   Risk/Reward: 1:{reward_percent/risk_percent:.2f}")
                
                # Verify reasonable levels
                assert stop_loss_price > 0, "Stop loss should be positive"
                assert profit_target_price > 0, "Profit target should be positive"
                assert risk_percent < 10.0, f"Risk too high: {risk_percent:.1f}%"
                assert reward_percent > 0.5, f"Reward too low: {reward_percent:.1f}%"
                
                # For our 6:3 ratio, should be 1:0.5 risk/reward
                expected_rr = 0.5
                actual_rr = reward_percent / risk_percent
                assert abs(actual_rr - expected_rr) < 0.1, f"Risk/reward ratio off: expected ~{expected_rr:.1f}, got {actual_rr:.2f}"
                
                await asyncio.sleep(0.5)
            
            logger.info("🎯 Stop loss scenario validation completed!")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)


if __name__ == "__main__":
    # Manual test runner
    async def main():
        print("🧪 Live ATR System Testing")
        print("=" * 50)
        
        from tests.integration.conftest import get_tws_credentials, is_tws_available
        
        credentials = get_tws_credentials()
        print(f"🔍 Checking TWS availability...")
        
        if not is_tws_available(credentials["host"], credentials["port"], credentials["client_id"] + 520):
            print("❌ TWS not available")
            return
        
        print("✅ TWS is available!")
        
        # Quick ATR test
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 520,
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
            
            indicator_manager = IndicatorManager(tws_connection.minute_bar_manager)
            
            # Test ATR for some tickers
            tickers = ["AAPL", "UVXY", "SOXL"]
            
            print(f"\n📊 10-second ATR calculations:")
            print("=" * 50)
            
            for ticker in tickers:
                print(f"📈 Getting ATR for {ticker}...")
                start_time = datetime.now()
                
                atr = await indicator_manager.get_atr(ticker, period=14)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                if atr:
                    stop_loss = atr * 6
                    profit_target = atr * 3
                    print(f"   {ticker:6s}: ATR=${atr:.4f} → SL=${stop_loss:.4f}, PT=${profit_target:.4f} ({duration:.1f}s)")
                else:
                    print(f"   {ticker:6s}: No ATR data available")
                
                await asyncio.sleep(0.5)
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
        
        print("\n🏁 Manual test completed!")
    
    asyncio.run(main()) 