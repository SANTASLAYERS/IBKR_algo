"""
Rule Templates for Reusable Trading Strategies
==============================================

This module provides essential template functions for creating trading rules with automatic
stop loss, take profit, and scale-in functionality.

Usage:
    from src.rule.templates import create_buy_rule, create_short_rule, create_scale_in_rule
    
    # Create BUY rule with automatic stops/targets
    aapl_buy = create_buy_rule("AAPL", quantity=100)
    
    # Create scale-in rule that triggers after buy rule
    aapl_scale = create_scale_in_rule("AAPL", scale_quantity=50, price_offset=0.02)
"""

import logging
from src.rule.base import Rule, Action
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedOrderManager
from src.event.api import PredictionSignalEvent
from src.order import OrderType
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SimpleScaleInAction(Action):
    """Simple action that places scale-in limit order based on context side."""
    
    def __init__(self, symbol: str, scale_quantity: int, price_offset: float):
        self.symbol = symbol
        self.scale_quantity = scale_quantity
        self.price_offset = price_offset  # e.g., 0.02 = 2% below current for longs
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Place scale-in limit order based on context side."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found")
            return False
        
        try:
            # Check context for the side that was just created
            group = context.get(self.symbol, {})
            side = group.get("side")
            if not side:
                logger.info(f"No active side found for {self.symbol} scale-in")
                return False
            
            # Get current price
            current_price = context.get("prices", {}).get(self.symbol)
            if not current_price:
                logger.error(f"No current price for {self.symbol}")
                return False
            
            # Calculate limit price based on side and offset
            if side == "BUY":  # Long position
                limit_price = current_price * (1 - self.price_offset)  # Below current
                scale_quantity = abs(self.scale_quantity)  # Positive for longs
            else:  # SHORT position (SELL)
                limit_price = current_price * (1 + self.price_offset)  # Above current
                scale_quantity = -abs(self.scale_quantity)  # Negative for shorts
            
            # Create scale-in limit order
            scale_order = await order_manager.create_and_submit_order(
                symbol=self.symbol,
                quantity=scale_quantity,
                order_type=OrderType.LIMIT,
                limit_price=limit_price
            )
            
            # Link the scale order
            LinkedOrderManager.add_order(context, self.symbol, scale_order.order_id, "scale", side)
            
            logger.info(f"Placed {side} scale-in limit at ${limit_price:.2f} for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error placing scale-in for {self.symbol}: {e}")
            return False


def create_buy_rule(
    symbol: str,
    quantity: int,
    confidence_threshold: float = 0.80,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.08,
    cooldown_minutes: int = 5
) -> Rule:
    """
    Create a BUY rule with automatic stop loss and take profit.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        confidence_threshold: Minimum confidence level (0.0-1.0)
        stop_loss_pct: Stop loss percentage below entry (e.g., 0.03 = 3%)
        take_profit_pct: Take profit percentage above entry (e.g., 0.08 = 8%)
        cooldown_minutes: Cooldown period between trades
        
    Returns:
        Rule ready for registration with rule engine
    """
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": "BUY",
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = LinkedCreateOrderAction(
        symbol=symbol,
        quantity=quantity,
        side="BUY",
        order_type=OrderType.MARKET,
        auto_create_stops=True,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_buy_rule",
        name=f"{symbol} Buy Rule",
        description=f"Buy {quantity} shares of {symbol} when confidence >= {confidence_threshold}",
        condition=condition,
        action=action,
        priority=100,
        cooldown_seconds=cooldown_minutes * 60
    )


def create_short_rule(
    symbol: str,
    quantity: int,
    confidence_threshold: float = 0.80,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.08,
    cooldown_minutes: int = 5
) -> Rule:
    """
    Create a SHORT rule with automatic stop loss and take profit.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares to short
        confidence_threshold: Minimum confidence level (0.0-1.0)
        stop_loss_pct: Stop loss percentage above entry (e.g., 0.03 = 3%)
        take_profit_pct: Take profit percentage below entry (e.g., 0.08 = 8%)
        cooldown_minutes: Cooldown period between trades
        
    Returns:
        Rule ready for registration with rule engine
    """
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": "SHORT",
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = LinkedCreateOrderAction(
        symbol=symbol,
        quantity=quantity,
        side="SELL",
        order_type=OrderType.MARKET,
        auto_create_stops=True,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_short_rule",
        name=f"{symbol} Short Rule",
        description=f"Short {quantity} shares of {symbol} when confidence >= {confidence_threshold}",
        condition=condition,
        action=action,
        priority=100,
        cooldown_seconds=cooldown_minutes * 60
    )


def create_scale_in_rule(
    symbol: str,
    scale_quantity: int,
    price_offset: float = 0.02,
    confidence_threshold: float = 0.80
) -> Rule:
    """
    Create a scale-in rule that executes after buy/short rules.
    
    This rule:
    1. Triggers on the same BUY/SHORT signals as entry rules
    2. Executes with lower priority (after entry rule)
    3. Checks context to find the side that was just created
    4. Places limit order at current_price +/- price_offset
    
    Args:
        symbol: Stock symbol
        scale_quantity: Additional shares to add to position
        price_offset: Price offset from current (e.g., 0.02 = 2% away from current)
        confidence_threshold: Minimum confidence (should match entry rules)
        
    Returns:
        Rule ready for registration with rule engine
    """
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": lambda s: s in ["BUY", "SHORT"],
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = SimpleScaleInAction(
        symbol=symbol,
        scale_quantity=scale_quantity,
        price_offset=price_offset
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_scale_in_rule",
        name=f"{symbol} Scale-In Rule",
        description=f"Scale into {symbol} with limit order {price_offset:.1%} from current price",
        condition=condition,
        action=action,
        priority=90,  # Lower priority = executes after buy/short rules
        cooldown_seconds=0  # No cooldown, let it execute with entry rule
    ) 