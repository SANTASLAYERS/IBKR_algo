"""
Action implementations for the rule engine.

This module contains various action classes that can be executed
when rule conditions are met.
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union

from src.rule.base import Action, Condition
from src.event.order import OrderType, OrderSide, TimeInForce

logger = logging.getLogger(__name__)


class SequentialAction(Action):
    """Execute multiple actions in sequence."""
    
    def __init__(self, *actions: Action):
        self.actions = actions
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute all actions in sequence."""
        success = True
        for action in self.actions:
            action_success = await action.execute(context)
            success = success and action_success
            if not action_success:
                # Stop executing if an action fails
                break
        return success


class ConditionalAction(Action):
    """Execute an action only if a condition is met."""
    
    def __init__(self, condition: Condition, action: Action):
        self.condition = condition
        self.action = action
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the action if the condition is met."""
        if await self.condition.evaluate(context):
            return await self.action.execute(context)
        return True  # Not executing is considered successful


class CreatePositionAction(Action):
    """Action to create a new position."""
    
    def __init__(self, 
                 symbol: Union[str, Callable[[Dict[str, Any]], str]], 
                 quantity: Union[float, Callable[[Dict[str, Any]], float]],
                 position_type: str = "stock",
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None,
                 trailing_stop_pct: Optional[float] = None):
        self.symbol = symbol
        self.quantity = quantity
        self.position_type = position_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create a new position."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            # Resolve callable parameters
            symbol = self.symbol(context) if callable(self.symbol) else self.symbol
            quantity = self.quantity(context) if callable(self.quantity) else self.quantity
            
            # Create position based on type
            if self.position_type == "stock":
                kwargs = {
                    "symbol": symbol,
                    "quantity": quantity
                }
                
                # Add optional parameters if provided
                if self.stop_loss_pct is not None:
                    kwargs["stop_loss_pct"] = self.stop_loss_pct
                    
                if self.take_profit_pct is not None:
                    kwargs["take_profit_pct"] = self.take_profit_pct
                    
                if self.trailing_stop_pct is not None:
                    kwargs["trailing_stop_pct"] = self.trailing_stop_pct
                
                position = await position_tracker.create_stock_position(**kwargs)
                
                # Add the created position to context for potential further actions
                context["created_position"] = position
                return True
            else:
                logger.error(f"Unsupported position type: {self.position_type}")
                return False
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return False


class ClosePositionAction(Action):
    """Action to close an existing position."""
    
    def __init__(self, 
                 position_id: Optional[str] = None,
                 symbol: Optional[str] = None,
                 reason: str = "Rule triggered"):
        self.position_id = position_id
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Close the position."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            # Close by ID
            if self.position_id:
                await position_tracker.close_position(
                    position_id=self.position_id,
                    reason=self.reason
                )
                return True
                
            # Close by symbol
            if self.symbol:
                positions = await position_tracker.get_positions_for_symbol(self.symbol)
                for position in positions:
                    await position_tracker.close_position(
                        position_id=position.position_id,
                        reason=self.reason
                    )
                return True
                
            # Close specific position in context
            position = context.get("position")
            if position:
                await position_tracker.close_position(
                    position_id=position.position_id,
                    reason=self.reason
                )
                return True
                
            logger.error("No position ID, symbol, or position in context provided")
            return False
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False


class AdjustPositionAction(Action):
    """Action to adjust an existing position."""
    
    def __init__(self,
                 position_id: Optional[str] = None,
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None,
                 trailing_stop_pct: Optional[float] = None,
                 reason: str = "Rule triggered"):
        self.position_id = position_id
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Adjust the position parameters."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            # Determine which position to adjust
            position_id = self.position_id
            if not position_id:
                position = context.get("position")
                if position:
                    position_id = position.position_id
                    
            if not position_id:
                logger.error("No position ID provided or found in context")
                return False
                
            # Get current position for parameter calculations
            position = await position_tracker.get_position(position_id)
            if not position:
                logger.error(f"Position not found: {position_id}")
                return False
                
            # Calculate absolute values from percentages if needed
            kwargs = {
                "position_id": position_id,
                "reason": self.reason
            }
            
            if hasattr(position, "current_price") and position.current_price is not None:
                current_price = position.current_price
                
                if self.stop_loss_pct is not None:
                    is_long = getattr(position, "is_long", position.quantity > 0)
                    if is_long:
                        kwargs["stop_loss"] = current_price * (1 - self.stop_loss_pct)
                    else:
                        kwargs["stop_loss"] = current_price * (1 + self.stop_loss_pct)
                        
                if self.take_profit_pct is not None:
                    is_long = getattr(position, "is_long", position.quantity > 0)
                    if is_long:
                        kwargs["take_profit"] = current_price * (1 + self.take_profit_pct)
                    else:
                        kwargs["take_profit"] = current_price * (1 - self.take_profit_pct)
            
            # Add trailing stop directly if provided
            if self.trailing_stop_pct is not None:
                kwargs["trailing_stop_pct"] = self.trailing_stop_pct
            
            # Apply adjustments
            await position_tracker.adjust_position(**kwargs)
            
            return True
        except Exception as e:
            logger.error(f"Error adjusting position: {e}")
            return False


class CreateOrderAction(Action):
    """Action to create an order."""
    
    def __init__(self,
                 symbol: Union[str, Callable[[Dict[str, Any]], str]],
                 quantity: Union[float, Callable[[Dict[str, Any]], float]],
                 order_type: OrderType = OrderType.MARKET,
                 limit_price: Optional[float] = None,
                 stop_price: Optional[float] = None,
                 time_in_force: Optional[TimeInForce] = None,
                 auto_submit: bool = True):
        self.symbol = symbol
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.auto_submit = auto_submit
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create an order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            # Resolve callable parameters
            symbol = self.symbol(context) if callable(self.symbol) else self.symbol
            quantity = self.quantity(context) if callable(self.quantity) else self.quantity
            
            # Create order
            order = await order_manager.create_order(
                symbol=symbol,
                quantity=quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                stop_price=self.stop_price,
                time_in_force=self.time_in_force,
                auto_submit=self.auto_submit
            )
            
            # Add order to context for potential further actions
            context["created_order"] = order
            return True
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return False


class CancelOrderAction(Action):
    """Action to cancel an order."""
    
    def __init__(self, 
                 order_id: Optional[str] = None,
                 symbol: Optional[str] = None,
                 reason: str = "Rule triggered"):
        self.order_id = order_id
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Cancel the order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            # Cancel by ID
            if self.order_id:
                await order_manager.cancel_order(
                    order_id=self.order_id,
                    reason=self.reason
                )
                return True
                
            # Cancel by symbol
            if self.symbol:
                orders = await order_manager.get_orders_for_symbol(self.symbol)
                for order in orders:
                    if order.is_active or order.is_pending:
                        await order_manager.cancel_order(
                            order_id=order.order_id,
                            reason=self.reason
                        )
                return True
                
            # Cancel specific order in context
            order = context.get("order")
            if order:
                await order_manager.cancel_order(
                    order_id=order.order_id,
                    reason=self.reason
                )
                return True
                
            logger.error("No order ID, symbol, or order in context provided")
            return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False


class CreateBracketOrderAction(Action):
    """Action to create a bracket order."""
    
    def __init__(self,
                 symbol: Union[str, Callable[[Dict[str, Any]], str]],
                 quantity: Union[float, Callable[[Dict[str, Any]], float]],
                 entry_price: Optional[float] = None,
                 stop_loss_price: Optional[float] = None,
                 take_profit_price: Optional[float] = None,
                 entry_type: OrderType = OrderType.MARKET,
                 auto_submit: bool = True):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.entry_type = entry_type
        self.auto_submit = auto_submit
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create a bracket order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            # Resolve callable parameters
            symbol = self.symbol(context) if callable(self.symbol) else self.symbol
            quantity = self.quantity(context) if callable(self.quantity) else self.quantity
            
            # Create bracket order
            bracket = await order_manager.create_bracket_order(
                symbol=symbol,
                quantity=quantity,
                entry_price=self.entry_price,
                stop_loss_price=self.stop_loss_price,
                take_profit_price=self.take_profit_price,
                entry_type=self.entry_type,
                auto_submit=self.auto_submit
            )
            
            # Add bracket to context for potential further actions
            context["created_bracket"] = bracket
            return True
        except Exception as e:
            logger.error(f"Error creating bracket order: {e}")
            return False


class LogAction(Action):
    """Action to log information."""
    
    def __init__(self, message: str, level: str = "INFO"):
        self.message = message
        self.level = level.upper()
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Log the message."""
        try:
            log_func = getattr(logger, self.level.lower(), logger.info)
            log_func(self.message)
            return True
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            return False