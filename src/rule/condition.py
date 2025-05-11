"""
Condition implementations for the rule engine.

This module contains various condition classes that can be used to define
when rules should trigger.
"""

from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional, Callable, List, Type, Union

from src.rule.base import Condition
from src.event.base import BaseEvent
from src.event.position import PositionStatus


class AndCondition(Condition):
    """Represents a logical AND of multiple conditions."""
    
    def __init__(self, *conditions: Condition):
        self.conditions = conditions
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if all conditions are met."""
        for condition in self.conditions:
            if not await condition.evaluate(context):
                return False
        return True


class OrCondition(Condition):
    """Represents a logical OR of multiple conditions."""
    
    def __init__(self, *conditions: Condition):
        self.conditions = conditions
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if any condition is met."""
        for condition in self.conditions:
            if await condition.evaluate(context):
                return True
        return False


class NotCondition(Condition):
    """Represents a logical NOT of a condition."""
    
    def __init__(self, condition: Condition):
        self.condition = condition
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if the condition is not met."""
        return not await self.condition.evaluate(context)


class EventCondition(Condition):
    """Condition based on an event."""
    
    def __init__(self, event_type: Type[BaseEvent], field_conditions: Dict[str, Any] = None):
        self.event_type = event_type
        self.field_conditions = field_conditions or {}
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the event meets the criteria."""
        event = context.get("event")
        if not isinstance(event, self.event_type):
            return False
            
        # Check field conditions
        for field, expected_value in self.field_conditions.items():
            if not hasattr(event, field):
                return False
            actual_value = getattr(event, field)
            
            # Handle callable predicates
            if callable(expected_value):
                if not expected_value(actual_value):
                    return False
            # Direct comparison
            elif actual_value != expected_value:
                return False
                
        return True


class PositionCondition(Condition):
    """Condition based on position state."""
    
    def __init__(self, 
                 symbol: Optional[str] = None,
                 position_id: Optional[str] = None,
                 min_unrealized_pnl_pct: Optional[float] = None,
                 max_unrealized_pnl_pct: Optional[float] = None,
                 min_position_duration: Optional[timedelta] = None,
                 status: Optional[PositionStatus] = None):
        self.symbol = symbol
        self.position_id = position_id
        self.min_unrealized_pnl_pct = min_unrealized_pnl_pct
        self.max_unrealized_pnl_pct = max_unrealized_pnl_pct
        self.min_position_duration = min_position_duration
        self.status = status
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the position meets the criteria."""
        position = context.get("position")
        if not position:
            return False
            
        # Check position properties
        if self.symbol and position.symbol != self.symbol:
            return False
            
        if self.position_id and position.position_id != self.position_id:
            return False
            
        if self.status and position.status != self.status:
            return False
            
        if self.min_unrealized_pnl_pct is not None:
            if not hasattr(position, "unrealized_pnl_pct"):
                return False
            if position.unrealized_pnl_pct < self.min_unrealized_pnl_pct:
                return False
                
        if self.max_unrealized_pnl_pct is not None:
            if not hasattr(position, "unrealized_pnl_pct"):
                return False
            if position.unrealized_pnl_pct > self.max_unrealized_pnl_pct:
                return False
                
        if self.min_position_duration is not None:
            if not hasattr(position, "open_time"):
                return False
            if datetime.now() - position.open_time < self.min_position_duration:
                return False
                
        return True


class TimeCondition(Condition):
    """Condition based on time."""
    
    def __init__(self, 
                 start_time: Optional[time] = None, 
                 end_time: Optional[time] = None,
                 days_of_week: Optional[List[int]] = None,  # 0=Monday, 6=Sunday
                 market_hours_only: bool = False):
        self.start_time = start_time
        self.end_time = end_time
        self.days_of_week = days_of_week
        self.market_hours_only = market_hours_only
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the current time meets the criteria."""
        now = datetime.now()
        
        # Check day of week
        if self.days_of_week and now.weekday() not in self.days_of_week:
            return False
            
        # Check time range
        current_time = now.time()
        if self.start_time and current_time < self.start_time:
            return False
            
        if self.end_time and current_time > self.end_time:
            return False
            
        # Check market hours (simplified)
        if self.market_hours_only:
            # 9:30 AM to 4:00 PM Eastern Time, converted to local time
            # This is a simplified check and would need to be enhanced for accuracy
            market_open = time(9, 30)  # Adjust for timezone difference
            market_close = time(16, 0)  # Adjust for timezone difference
            
            if current_time < market_open or current_time > market_close:
                return False
                
        return True


class MarketCondition(Condition):
    """Condition based on market indicators."""
    
    def __init__(self,
                 symbol: str,
                 min_price: Optional[float] = None,
                 max_price: Optional[float] = None,
                 min_volume: Optional[int] = None,
                 max_volatility: Optional[float] = None,
                 indicator_conditions: Dict[str, Callable[[float], bool]] = None):
        self.symbol = symbol
        self.min_price = min_price
        self.max_price = max_price
        self.min_volume = min_volume
        self.max_volatility = max_volatility
        self.indicator_conditions = indicator_conditions or {}
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the market conditions meet the criteria."""
        market_data = context.get("market_data", {}).get(self.symbol)
        if not market_data:
            return False
            
        # Check price
        current_price = market_data.get("price")
        if current_price is None:
            return False
            
        if self.min_price is not None and current_price < self.min_price:
            return False
            
        if self.max_price is not None and current_price > self.max_price:
            return False
            
        # Check volume
        current_volume = market_data.get("volume")
        if self.min_volume is not None:
            if not current_volume or current_volume < self.min_volume:
                return False
        
        # Check volatility
        current_volatility = market_data.get("volatility")
        if self.max_volatility is not None:
            if not current_volatility or current_volatility > self.max_volatility:
                return False
        
        # Check indicators
        indicators = market_data.get("indicators", {})
        for indicator_name, condition_func in self.indicator_conditions.items():
            indicator_value = indicators.get(indicator_name)
            if indicator_value is None or not condition_func(indicator_value):
                return False
                
        return True