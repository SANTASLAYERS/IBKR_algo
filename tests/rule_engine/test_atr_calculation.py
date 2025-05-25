#!/usr/bin/env python3
"""
Unit tests for ATR (Average True Range) calculation.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

# Import the ATR calculator that doesn't exist yet
from src.indicators.atr import ATRCalculator
from src.minute_data.models import MinuteBar


@pytest.fixture
def sample_price_data():
    """Create sample minute bar data for testing ATR calculation."""
    # Create 20 bars of sample data with known true range values
    base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    price_data = []
    
    # Starting price
    current_price = 100.0
    
    for i in range(20):
        # Create some volatility
        high = current_price + (i % 5) + 1
        low = current_price - (i % 3) - 0.5
        close = current_price + ((-1) ** i) * (i % 4) * 0.25
        
        # Create minute bar
        bar = MinuteBar(
            timestamp=base_time + timedelta(minutes=i),
            open_price=current_price,
            high_price=high,
            low_price=low,
            close_price=close,
            volume=1000 + i * 100,
            symbol="AAPL"
        )
        price_data.append(bar)
        
        # Next bar opens at previous close
        current_price = close
    
    return price_data


@pytest.mark.asyncio
async def test_atr_calculation(sample_price_data):
    """Test basic ATR calculation."""
    # Create calculator with 14-period default
    calculator = ATRCalculator()
    
    # Calculate ATR
    atr = await calculator.calculate(sample_price_data)
    
    # ATR should be a positive float
    assert atr > 0
    assert isinstance(atr, float)


@pytest.mark.asyncio
async def test_atr_with_custom_period(sample_price_data):
    """Test ATR calculation with custom period."""
    # Create calculator with 5-period
    calculator = ATRCalculator(period=5)
    
    # Calculate ATR
    atr = await calculator.calculate(sample_price_data)
    
    # ATR should be a positive float
    assert atr > 0
    assert isinstance(atr, float)
    
    # Calculate with different period
    calculator_10 = ATRCalculator(period=10)
    atr_10 = await calculator_10.calculate(sample_price_data)
    
    # Should be different from 5-period ATR
    assert atr != atr_10


@pytest.mark.asyncio
async def test_atr_insufficient_data():
    """Test ATR calculation with insufficient data."""
    # Create calculator with 14-period default
    calculator = ATRCalculator()
    
    # Only 5 bars, but calculator needs at least 14
    short_data = [
        MinuteBar(
            timestamp=datetime.now() + timedelta(minutes=i),
            open_price=100.0 + i,
            high_price=105.0 + i,
            low_price=95.0 + i,
            close_price=102.0 + i,
            volume=1000,
            symbol="AAPL"
        )
        for i in range(5)
    ]
    
    # Should return a value using available data (not None)
    # The calculator will use fewer periods and log a warning
    atr = await calculator.calculate(short_data)
    assert atr is not None
    assert atr > 0
    assert isinstance(atr, float)


@pytest.mark.asyncio
async def test_atr_verification():
    """
    Test ATR calculation with known values to verify the formula.
    
    The formula for True Range (TR) is:
    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    
    ATR = Average of TR over N periods
    """
    # Create data with known true ranges
    known_data = []
    base_time = datetime.now()
    
    # Day 1: High=110, Low=100, Close=105
    known_data.append(MinuteBar(
        timestamp=base_time,
        open_price=105,
        high_price=110,
        low_price=100,
        close_price=105,
        volume=1000,
        symbol="TEST"
    ))
    
    # Day 2: High=115, Low=105, Close=110, Prev Close=105
    # TR = max(10, 10, 0) = 10
    known_data.append(MinuteBar(
        timestamp=base_time + timedelta(minutes=1),
        open_price=105,
        high_price=115,
        low_price=105,
        close_price=110,
        volume=1000,
        symbol="TEST"
    ))
    
    # Day 3: High=120, Low=110, Close=115, Prev Close=110
    # TR = max(10, 10, 0) = 10
    known_data.append(MinuteBar(
        timestamp=base_time + timedelta(minutes=2),
        open_price=110,
        high_price=120,
        low_price=110,
        close_price=115,
        volume=1000,
        symbol="TEST"
    ))
    
    # Day 4: High=115, Low=105, Close=110, Prev Close=115
    # TR = max(10, 0, 10) = 10
    known_data.append(MinuteBar(
        timestamp=base_time + timedelta(minutes=3),
        open_price=115,
        high_price=115,
        low_price=105,
        close_price=110,
        volume=1000,
        symbol="TEST"
    ))
    
    # Day 5: High=105, Low=95, Close=100, Prev Close=110
    # TR = max(10, 5, 15) = 15
    known_data.append(MinuteBar(
        timestamp=base_time + timedelta(minutes=4),
        open_price=110,
        high_price=105,
        low_price=95,
        close_price=100,
        volume=1000,
        symbol="TEST"
    ))
    
    # Expected ATR for 5-period is (10 + 10 + 10 + 15) / 4 = 11.25
    # Note: first day doesn't have a TR as there's no previous close
    expected_atr_5 = 11.25
    
    # Create calculator with 5-period
    calculator = ATRCalculator(period=5)
    
    # Calculate ATR
    atr = await calculator.calculate(known_data)
    
    # Check against expected value with small tolerance for floating point
    assert abs(atr - expected_atr_5) < 0.001