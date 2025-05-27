#!/usr/bin/env python3
"""
Position Sizer
==============

Calculates position sizes based on dollar allocation and current prices.
Simple, clean logic without complex risk models.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculate position sizes based on dollar allocations."""
    
    def __init__(self, min_shares: int = 1, max_shares: int = 10000):
        """
        Initialize position sizer.
        
        Args:
            min_shares: Minimum position size (default 1)
            max_shares: Maximum position size for safety (default 10,000)
        """
        self.min_shares = min_shares
        self.max_shares = max_shares
    
    def calculate_shares(self, 
                        allocation: float, 
                        price: float, 
                        side: str = "BUY") -> Optional[int]:
        """
        Calculate number of shares for given allocation and price.
        
        Args:
            allocation: Dollar amount to allocate (e.g., 10000)
            price: Current stock price
            side: "BUY" or "SELL" (for logging)
            
        Returns:
            Number of shares to trade, or None if invalid
        """
        if not price or price <= 0:
            logger.warning(f"Invalid price for position sizing: {price}")
            return None
            
        if allocation <= 0:
            logger.warning(f"Invalid allocation for position sizing: {allocation}")
            return None
        
        # Calculate raw shares (can be fractional)
        raw_shares = allocation / price
        
        # Round down to whole shares
        shares = int(math.floor(raw_shares))
        
        # Validate minimum
        if shares < self.min_shares:
            logger.warning(f"Position too small: {shares} shares (${allocation:.2f} @ ${price:.2f}) - minimum is {self.min_shares}")
            return None
            
        # Apply maximum limit
        if shares > self.max_shares:
            logger.warning(f"Position too large: {shares} shares - limiting to {self.max_shares}")
            shares = self.max_shares
        
        # Calculate actual dollar amount
        actual_allocation = shares * price
        efficiency = (actual_allocation / allocation) * 100
        
        logger.info(f"{side} position size: {shares} shares @ ${price:.2f} = ${actual_allocation:.2f} ({efficiency:.1f}% of ${allocation:.2f} allocation)")
        
        return shares
    
    def calculate_allocation_efficiency(self, shares: int, price: float, target_allocation: float) -> float:
        """
        Calculate how efficiently the allocation was used.
        
        Args:
            shares: Number of shares purchased
            price: Price per share
            target_allocation: Target dollar allocation
            
        Returns:
            Efficiency percentage (0-100)
        """
        actual_allocation = shares * price
        return (actual_allocation / target_allocation) * 100 if target_allocation > 0 else 0
    
    def get_allocation_summary(self, shares: int, price: float, allocation: float) -> dict:
        """
        Get detailed allocation summary.
        
        Args:
            shares: Number of shares
            price: Price per share  
            allocation: Target allocation
            
        Returns:
            Dictionary with allocation details
        """
        actual_cost = shares * price
        unused_cash = allocation - actual_cost
        efficiency = self.calculate_allocation_efficiency(shares, price, allocation)
        
        return {
            "shares": shares,
            "price": price,
            "target_allocation": allocation,
            "actual_cost": actual_cost,
            "unused_cash": unused_cash,
            "efficiency_pct": efficiency
        } 