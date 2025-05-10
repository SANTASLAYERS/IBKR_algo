"""
Stock position implementation for the position management system.

This module provides the StockPosition class, which extends the base Position
class with functionality specific to stock positions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.position.base import Position

# Set up logger
logger = logging.getLogger(__name__)


class StockPosition(Position):
    """
    Stock position implementation.
    
    Extends the base Position class with stock-specific functionality.
    """
    
    def __init__(self, symbol: str, position_id: Optional[str] = None):
        """
        Initialize a new stock position.
        
        Args:
            symbol: The stock symbol
            position_id: Optional position ID (generated if not provided)
        """
        super().__init__(symbol, position_id)
        
        # Stock-specific metrics
        self.average_volume = None
        self.beta = None
        self.dividend_yield = None
        self.sector = None
        self.industry = None
        self.market_cap = None
        
        # Risk metrics
        self.max_drawdown = 0.0
        self.peak_value = 0.0
        self.risk_multiple = 1.0
        
        # Position sizing
        self.account_value_at_entry = None
        self.position_size_pct = None
        
        logger.debug(f"Created stock position {self.position_id} for {symbol}")
    
    async def set_stock_info(self,
                           avg_volume: Optional[float] = None,
                           beta: Optional[float] = None,
                           dividend_yield: Optional[float] = None,
                           sector: Optional[str] = None,
                           industry: Optional[str] = None,
                           market_cap: Optional[float] = None) -> None:
        """
        Set stock-specific information.

        Args:
            avg_volume: Average trading volume
            beta: Stock beta
            dividend_yield: Dividend yield
            sector: Stock sector
            industry: Stock industry
            market_cap: Market cap
        """
        # Simplified for demo - no locking
        updates = {}

        if avg_volume is not None:
            self.average_volume = avg_volume
            updates["average_volume"] = avg_volume

        if beta is not None:
            self.beta = beta
            updates["beta"] = beta

        if dividend_yield is not None:
            self.dividend_yield = dividend_yield
            updates["dividend_yield"] = dividend_yield

        if sector is not None:
            self.sector = sector
            updates["sector"] = sector

        if industry is not None:
            self.industry = industry
            updates["industry"] = industry

        if market_cap is not None:
            self.market_cap = market_cap
            updates["market_cap"] = market_cap

        if updates:
            self._record_update("stock_info_update", updates)
            logger.debug(f"Updated stock info for position {self.position_id}: {updates}")
    
    async def update_price(self, price: float) -> None:
        """
        Update the current price of the position.

        Args:
            price: The new price
        """
        await super().update_price(price)

        # Update drawdown and peak value tracking
        # Simplified for demo - no locking
        if self.entry_value > 0:
            if self.position_value > self.peak_value:
                self.peak_value = self.position_value

            # Calculate drawdown from peak
            if self.peak_value > 0:
                current_drawdown = (self.peak_value - self.position_value) / self.peak_value
                if current_drawdown > self.max_drawdown:
                    self.max_drawdown = current_drawdown
                    self._record_update("max_drawdown_update", {
                        "max_drawdown": self.max_drawdown,
                        "peak_value": self.peak_value,
                        "current_value": self.position_value
                    })
    
    async def set_position_sizing(self, account_value: float, position_size_pct: float) -> None:
        """
        Set position sizing information.

        Args:
            account_value: Account value at entry
            position_size_pct: Position size as a percentage of account
        """
        # Simplified for demo - no locking
        self.account_value_at_entry = account_value
        self.position_size_pct = position_size_pct

        self._record_update("position_sizing_update", {
            "account_value": account_value,
            "position_size_pct": position_size_pct
        })
    
    async def calculate_optimal_stop_loss(self, atr_multiple: float = 2.0, atr_value: Optional[float] = None) -> float:
        """
        Calculate optimal stop loss based on ATR (Average True Range).

        Args:
            atr_multiple: Multiple of ATR to use for stop loss
            atr_value: ATR value (optional, will be stored in metadata if provided)

        Returns:
            float: The calculated stop loss price
        """
        # Simplified for demo - no locking
        # If ATR value is provided, store it
        if atr_value is not None:
            self.metadata["atr"] = atr_value
        else:
            # Use stored ATR if available
            atr_value = self.metadata.get("atr")
            if atr_value is None:
                raise ValueError("ATR value not provided and not found in metadata")

        # Calculate stop loss
        if self.is_long:
            stop_loss = self.entry_price - (atr_value * atr_multiple)
        else:
            stop_loss = self.entry_price + (atr_value * atr_multiple)

        # Store the ATR multiple used
        self.risk_multiple = atr_multiple

        logger.debug(f"Calculated stop loss for {self.position_id}: {stop_loss} (ATR: {atr_value}, multiple: {atr_multiple})")
        return stop_loss
    
    async def calculate_optimal_take_profit(self, risk_reward_ratio: float = 2.0) -> float:
        """
        Calculate optimal take profit based on risk-reward ratio.

        Args:
            risk_reward_ratio: Risk-reward ratio

        Returns:
            float: The calculated take profit price
        """
        # Simplified for demo - no locking
        if self.stop_loss is None:
            raise ValueError("Stop loss must be set before calculating take profit")

        # Calculate risk per share
        risk_per_share = abs(self.entry_price - self.stop_loss)

        # Calculate take profit
        if self.is_long:
            take_profit = self.entry_price + (risk_per_share * risk_reward_ratio)
        else:
            take_profit = self.entry_price - (risk_per_share * risk_reward_ratio)

        logger.debug(f"Calculated take profit for {self.position_id}: {take_profit} (R:R ratio: {risk_reward_ratio})")
        return take_profit
    
    async def calculate_trailing_stop(self, price: float, trail_percentage: float = 0.03) -> float:
        """
        Calculate trailing stop price.
        
        Args:
            price: Current price
            trail_percentage: Trailing stop percentage
            
        Returns:
            float: The calculated trailing stop price
        """
        if self.is_long:
            return price * (1 - trail_percentage)
        else:
            return price * (1 + trail_percentage)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the stock position to a dictionary."""
        base_dict = super().to_dict()
        
        # Add stock-specific fields
        stock_dict = {
            "average_volume": self.average_volume,
            "beta": self.beta,
            "dividend_yield": self.dividend_yield,
            "sector": self.sector,
            "industry": self.industry,
            "market_cap": self.market_cap,
            "max_drawdown": self.max_drawdown,
            "peak_value": self.peak_value,
            "risk_multiple": self.risk_multiple,
            "account_value_at_entry": self.account_value_at_entry,
            "position_size_pct": self.position_size_pct
        }
        
        return {**base_dict, **stock_dict}