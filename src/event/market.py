"""
Market-related events for the event system.

This module defines events related to market data, such as price updates,
volume changes, and indicator events.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

from src.event.base import BaseEvent


@dataclass
class MarketEvent(BaseEvent):
    """Base class for all market-related events."""
    
    source: str = "market"


@dataclass
class PriceEvent(MarketEvent):
    """Event for price updates."""
    
    # Symbol for which the price event occurred
    symbol: str = ""
    
    # Current price
    price: float = 0.0
    
    # Price change since previous update
    change: float = 0.0
    
    # Percentage change since previous update
    change_percent: float = 0.0
    
    # Bid price
    bid: Optional[float] = None
    
    # Ask price
    ask: Optional[float] = None
    
    # Volume at last price
    volume: Optional[int] = None
    
    # The time of the price update
    price_time: Optional[datetime] = None
    
    # Additional price data
    price_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VolumeEvent(MarketEvent):
    """Event for volume updates."""
    
    # Symbol for which the volume event occurred
    symbol: str = ""
    
    # Current volume
    volume: int = 0
    
    # Volume change since previous update
    change: int = 0
    
    # The time of the volume update
    volume_time: Optional[datetime] = None


@dataclass
class IndicatorEvent(MarketEvent):
    """Event for indicator updates or signals."""
    
    # Symbol for which the indicator event occurred
    symbol: str = ""
    
    # Indicator name (e.g., "RSI", "MACD")
    indicator: str = ""
    
    # Indicator value
    value: float = 0.0
    
    # Previous indicator value
    previous_value: Optional[float] = None
    
    # Signal type (e.g., "crossover", "threshold")
    signal_type: Optional[str] = None
    
    # Indicator-specific data
    indicator_data: Dict[str, Any] = field(default_factory=dict)