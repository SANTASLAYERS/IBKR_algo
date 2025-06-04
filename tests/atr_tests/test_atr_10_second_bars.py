#!/usr/bin/env python3
"""
Test ATR with 10-Second Bars
============================

Tests for verifying that the ATR indicator works correctly with 10-second bars
instead of the default 1-minute bars.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.indicators.manager import IndicatorManager
from src.indicators.atr import ATRCalculator
from src.minute_data.models import MinuteBar


class TestATR10SecondBars:
    """Test ATR calculation with 10-second bars."""
    
    @pytest.fixture
    def mock_minute_data_manager(self):
        """Create a mock minute data manager that returns 10-second bar data."""
        manager = AsyncMock()
        
        # Create mock 10-second bars (6 bars per minute)
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        bars = []
        
        # Generate 100 bars (about 16-17 minutes of 10-second bars)
        for i in range(100):
            timestamp = base_time + timedelta(seconds=i * 10)
            bar = MinuteBar(
                symbol="AAPL",
                timestamp=timestamp,
                open_price=150.0 + (i % 20) * 0.1,  # Varied prices
                high_price=152.0 + (i % 20) * 0.1,
                low_price=148.0 + (i % 20) * 0.1,
                close_price=151.0 + (i % 20) * 0.1,
                volume=1000 + i * 10
            )
            bars.append(bar)
        
        manager.get_historical_data.return_value = bars
        return manager
    
    @pytest.fixture
    def indicator_manager(self, mock_minute_data_manager):
        """Create an indicator manager with the mock data manager."""
        return IndicatorManager(mock_minute_data_manager)
    
    @pytest.mark.asyncio
    async def test_atr_with_10_second_bars(self, indicator_manager, mock_minute_data_manager):
        """Test that ATR can be calculated using 10-second bars."""
        # Calculate ATR with 10-second bars
        atr_value = await indicator_manager.get_atr(
            symbol="AAPL",
            period=14,  # 14 periods of 10-second bars
            days=1,
            bar_size="10 secs"
        )
        
        # Verify the data manager was called with correct parameters
        mock_minute_data_manager.get_historical_data.assert_called_once_with(
            symbol="AAPL",
            days=1,
            bar_size="10 secs"
        )
        
        # Verify ATR was calculated successfully
        assert atr_value is not None
        assert isinstance(atr_value, float)
        assert atr_value > 0
        
        print(f"ATR (10-second bars): {atr_value}")
    
    @pytest.mark.asyncio
    async def test_atr_comparison_different_timeframes(self, mock_minute_data_manager):
        """Test ATR calculation with different timeframes to show the difference."""
        
        # Create different mock data for different timeframes
        def create_bars_for_timeframe(bar_size, num_bars):
            base_time = datetime(2024, 1, 1, 10, 0, 0)
            bars = []
            
            for i in range(num_bars):
                if "secs" in bar_size:
                    seconds = int(bar_size.split()[0])
                    timestamp = base_time + timedelta(seconds=i * seconds)
                else:  # minutes
                    minutes = int(bar_size.split()[0])
                    timestamp = base_time + timedelta(minutes=i * minutes)
                
                bar = MinuteBar(
                    symbol="AAPL",
                    timestamp=timestamp,
                    open_price=150.0 + (i % 20) * 0.1,
                    high_price=152.0 + (i % 20) * 0.1,
                    low_price=148.0 + (i % 20) * 0.1,
                    close_price=151.0 + (i % 20) * 0.1,
                    volume=1000 + i * 10
                )
                bars.append(bar)
            
            return bars
        
        # Test different timeframes
        timeframes = [
            ("10 secs", 100),  # 100 x 10-second bars
            ("30 secs", 50),   # 50 x 30-second bars  
            ("1 min", 30),     # 30 x 1-minute bars
        ]
        
        atr_results = {}
        
        for bar_size, num_bars in timeframes:
            # Mock the data for this timeframe
            mock_minute_data_manager.get_historical_data.return_value = create_bars_for_timeframe(bar_size, num_bars)
            
            # Create indicator manager
            indicator_manager = IndicatorManager(mock_minute_data_manager)
            
            # Calculate ATR
            atr_value = await indicator_manager.get_atr(
                symbol="AAPL",
                period=14,
                days=1,
                bar_size=bar_size
            )
            
            atr_results[bar_size] = atr_value
            print(f"ATR ({bar_size}): {atr_value}")
        
        # Verify all ATR calculations succeeded
        for bar_size, atr_value in atr_results.items():
            assert atr_value is not None, f"ATR calculation failed for {bar_size}"
            assert isinstance(atr_value, float), f"ATR should be float for {bar_size}"
            assert atr_value > 0, f"ATR should be positive for {bar_size}"
    
    @pytest.mark.asyncio
    async def test_atr_caching_works_with_10_second_bars(self, indicator_manager):
        """Test that indicator caching works correctly with 10-second bars."""
        
        # Calculate ATR twice
        atr1 = await indicator_manager.get_atr("AAPL", bar_size="10 secs")
        atr2 = await indicator_manager.get_atr("AAPL", bar_size="10 secs")
        
        # Both should be the same
        assert atr1 == atr2
        
        # Check that the value is cached
        cached_indicators = indicator_manager.get_cached_indicators("AAPL")
        assert "ATR" in cached_indicators
        assert cached_indicators["ATR"] == atr1
        
        print(f"Cached ATR value: {cached_indicators['ATR']}")


if __name__ == "__main__":
    # Run a simple test
    async def main():
        print("Testing ATR with 10-second bars...")
        
        # Create mock data
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        bars = []
        
        for i in range(50):
            timestamp = base_time + timedelta(seconds=i * 10)
            bar = MinuteBar(
                symbol="TEST",
                timestamp=timestamp,
                open_price=100.0 + i * 0.1,
                high_price=102.0 + i * 0.1,
                low_price=98.0 + i * 0.1,
                close_price=101.0 + i * 0.1,
                volume=1000
            )
            bars.append(bar)
        
        # Create mock manager
        mock_manager = AsyncMock()
        mock_manager.get_historical_data.return_value = bars
        
        # Test ATR calculation
        indicator_manager = IndicatorManager(mock_manager)
        atr = await indicator_manager.get_atr("TEST", bar_size="10 secs", period=14)
        
        print(f"ATR Result: {atr}")
        print("✅ Test completed successfully!")
    
    asyncio.run(main()) 