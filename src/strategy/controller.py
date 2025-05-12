#!/usr/bin/env python3
"""
Strategy Controller

This module provides the central controller for automated trading strategies,
integrating the Rule Engine with other components of the system.
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from src.rule.engine import RuleEngine
from src.indicators.manager import IndicatorManager
from src.event.market import PriceEvent

logger = logging.getLogger(__name__)


class StrategyController:
    """
    Central controller for automated trading strategies.
    
    The StrategyController integrates the Rule Engine with market data, indicators,
    position management, order management, and other components.
    """
    
    def __init__(
        self,
        event_bus,
        rule_engine,
        indicator_manager,
        position_tracker,
        order_manager
    ):
        """
        Initialize the strategy controller.
        
        Args:
            event_bus: The event bus for communication
            rule_engine: The rule engine for strategy execution
            indicator_manager: Manager for technical indicators
            position_tracker: Tracker for positions
            order_manager: Manager for orders
        """
        self.event_bus = event_bus
        self.rule_engine = rule_engine
        self.indicator_manager = indicator_manager
        self.position_tracker = position_tracker
        self.order_manager = order_manager
        self._initialized = False
        
    async def initialize(self):
        """Initialize the strategy controller and its components."""
        if self._initialized:
            logger.warning("Strategy controller already initialized")
            return
            
        # Set up rule engine context with required components
        self.rule_engine.update_context({
            "position_tracker": self.position_tracker,
            "order_manager": self.order_manager,
            "indicators": {}
        })
        
        # Subscribe to price events
        await self.event_bus.subscribe(PriceEvent, self._handle_price_event)
        
        # Start rule engine
        await self.rule_engine.start()
        
        logger.info("Strategy controller initialized")
        self._initialized = True
    
    async def get_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Calculate ATR for a symbol and update the rule engine context.
        
        Args:
            symbol: The ticker symbol
            period: The ATR period (default: 14)
            
        Returns:
            float: The calculated ATR value, or None if calculation fails
        """
        # Calculate ATR
        atr = await self.indicator_manager.get_atr(symbol, period)
        
        if atr is not None:
            # Update rule engine context
            indicators = self.rule_engine.context.get("indicators", {})
            if symbol not in indicators:
                indicators[symbol] = {}
            
            indicators[symbol]["ATR"] = atr
            self.rule_engine.update_context({"indicators": indicators})
            
            logger.info(f"Updated ATR for {symbol}: {atr:.4f}")
        
        return atr
    
    async def _handle_price_event(self, event):
        """
        Handle price update events.
        
        Args:
            event: The price event
        """
        # Process price event
        logger.debug(f"Processing price event for {event.symbol}: {event.price}")
        
        # Optionally update ATR on price events
        # For simplicity, we'll only do this occasionally to avoid
        # excessive API calls for historical data
        #
        # In a real implementation, you might want to:
        # 1. Update ATR on a schedule rather than on every price event
        # 2. Have a more sophisticated caching mechanism
        # 3. Only update when there's a significant price change
        
        # Update rule engine context with current price
        prices = self.rule_engine.context.get("prices", {})
        prices[event.symbol] = event.price
        self.rule_engine.update_context({"prices": prices})
        
    async def shutdown(self):
        """Shut down the strategy controller and its components."""
        if not self._initialized:
            return
            
        # Stop rule engine
        await self.rule_engine.stop()
        
        # Unsubscribe from events
        await self.event_bus.unsubscribe(PriceEvent, self._handle_price_event)
        
        logger.info("Strategy controller shutdown")
        self._initialized = False