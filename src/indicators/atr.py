#!/usr/bin/env python3
"""
ATR (Average True Range) Calculator

This module provides functionality for calculating the Average True Range (ATR)
technical indicator based on price data.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.minute_data.models import MinuteBar

logger = logging.getLogger(__name__)


class ATRCalculator:
    """
    Average True Range calculator.
    
    The ATR is a measure of market volatility that accounts for gaps in price movement.
    It is calculated as the average of true ranges over a specified period.
    
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Average of TR over N periods
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize the ATR calculator.
        
        Args:
            period: The number of periods to use for the ATR calculation.
                   Default is 14, which is standard for the ATR indicator.
        """
        self.period = period
        
    async def calculate(self, price_data: List[MinuteBar]) -> Optional[float]:
        """
        Calculate the ATR for the given price data.
        
        Args:
            price_data: List of MinuteBar objects containing price data
            
        Returns:
            float: The calculated ATR value, or None if insufficient data
        """
        if len(price_data) <= 1:
            logger.warning("Insufficient data for ATR calculation (need at least 2 bars)")
            return None
            
        # Sort data by timestamp to ensure correct order
        sorted_data = sorted(price_data, key=lambda x: x.timestamp)
        
        # Calculate true ranges
        true_ranges = []
        
        for i in range(1, len(sorted_data)):
            current_bar = sorted_data[i]
            previous_bar = sorted_data[i-1]
            
            # Calculate the three components of True Range
            high_low = current_bar.high_price - current_bar.low_price
            high_prev_close = abs(current_bar.high_price - previous_bar.close_price)
            low_prev_close = abs(current_bar.low_price - previous_bar.close_price)
            
            # True Range is the maximum of these components
            true_range = max(high_low, high_prev_close, low_prev_close)
            true_ranges.append(true_range)
        
        # If we don't have enough data for the requested period, use what we have
        if len(true_ranges) < self.period:
            if len(true_ranges) == 0:
                logger.warning("No true ranges calculated")
                return None
                
            logger.warning(
                f"Using {len(true_ranges)} periods for ATR calculation "
                f"instead of requested {self.period} due to insufficient data"
            )
            period = len(true_ranges)
        else:
            # Use the most recent data for the calculation
            period = self.period
            true_ranges = true_ranges[-period:]
        
        # Calculate the average of true ranges
        atr = sum(true_ranges) / len(true_ranges)
        
        return atr