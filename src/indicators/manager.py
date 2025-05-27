#!/usr/bin/env python3
"""
Indicator Manager

This module provides a simple manager for calculating technical indicators
based on historical price data.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.indicators.atr import ATRCalculator

logger = logging.getLogger(__name__)


class IndicatorManager:
    """
    Manager for technical indicators.
    
    This class provides a simplified interface for calculating technical indicators
    based on historical price data. It currently supports ATR calculation.
    """
    
    def __init__(self, minute_data_manager):
        """
        Initialize the indicator manager.
        
        Args:
            minute_data_manager: Manager for fetching historical minute data
        """
        self.minute_data_manager = minute_data_manager
        self.atr_calculator = ATRCalculator()
        self.indicator_values = {}  # Simple cache for indicator values
        
    async def get_atr(self, symbol: str, period: int = 14, days: int = 5, bar_size: str = "10 secs") -> Optional[float]:
        """
        Get the ATR value for a symbol.
        
        Args:
            symbol: The ticker symbol
            period: The ATR period (default: 14)
            days: Number of days of data to fetch (default: 5)
            bar_size: The timeframe for bars (default: "10 secs")
            
        Returns:
            float: The calculated ATR value, or None if calculation fails
        """
        # Create a calculator with the specified period
        calculator = ATRCalculator(period=period)
        
        try:
            # Fetch historical data for the symbol with specified bar size
            data = await self.minute_data_manager.get_historical_data(
                symbol=symbol,
                days=days,
                bar_size=bar_size
            )
            
            if not data:
                logger.warning(f"No historical data available for {symbol}")
                return None
                
            # Calculate ATR
            atr = await calculator.calculate(data)
            
            # Store the result
            if symbol not in self.indicator_values:
                self.indicator_values[symbol] = {}
            
            self.indicator_values[symbol]["ATR"] = atr
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR for {symbol}: {str(e)}")
            return None
    
    def get_cached_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        Get cached indicator values for a symbol.
        
        Args:
            symbol: The ticker symbol
            
        Returns:
            Dict: Dictionary of indicator values for the symbol
        """
        return self.indicator_values.get(symbol, {})