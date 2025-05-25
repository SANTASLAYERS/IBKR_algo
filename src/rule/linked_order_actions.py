"""
Linked Order Actions for automatic order relationship management.

This module provides enhanced order actions that automatically link related orders
through the rule engine context, enabling easy tracking and management of order groups.
"""

import logging
from typing import Dict, Any, Optional, List
from src.rule.base import Action
from src.rule.action import CreateOrderAction
from src.order import OrderType

logger = logging.getLogger(__name__)


class LinkedOrderManager:
    """Helper class for managing linked orders in context."""
    
    @staticmethod
    def get_order_group(context: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Get or create order group for a symbol."""
        if symbol not in context:
            context[symbol] = {
                "main_orders": [],
                "stop_orders": [],
                "target_orders": [],
                "scale_orders": [],
                "status": "active"
            }
        return context[symbol]
    
    @staticmethod
    def add_order(context: Dict[str, Any], symbol: str, order_id: str, order_type: str):
        """Add an order to the appropriate group."""
        group = LinkedOrderManager.get_order_group(context, symbol)
        
        if order_type == "main":
            group["main_orders"].append(order_id)
        elif order_type == "stop":
            group["stop_orders"].append(order_id)
        elif order_type == "target":
            group["target_orders"].append(order_id)
        elif order_type == "scale":
            group["scale_orders"].append(order_id)
        
        logger.debug(f"Added {order_type} order {order_id} to {symbol} group")
    
    @staticmethod
    def get_linked_orders(context: Dict[str, Any], symbol: str, order_type: Optional[str] = None) -> List[str]:
        """Get linked orders for a symbol."""
        group = context.get(symbol, {})
        
        if order_type:
            return group.get(f"{order_type}_orders", [])
        else:
            # Return all order IDs
            all_orders = []
            for key in ["main_orders", "stop_orders", "target_orders", "scale_orders"]:
                all_orders.extend(group.get(key, []))
            return all_orders
    
    @staticmethod
    def remove_order(context: Dict[str, Any], symbol: str, order_id: str):
        """Remove an order from all groups."""
        group = context.get(symbol, {})
        for key in ["main_orders", "stop_orders", "target_orders", "scale_orders"]:
            if order_id in group.get(key, []):
                group[key].remove(order_id)
                logger.debug(f"Removed order {order_id} from {symbol} {key}")
                break


class LinkedCreateOrderAction(Action):
    """Enhanced order creation that automatically links orders."""
    
    def __init__(self, 
                 symbol: str,
                 quantity: float,
                 order_type: OrderType = OrderType.MARKET,
                 limit_price: Optional[float] = None,
                 stop_price: Optional[float] = None,
                 link_type: str = "main",  # main, stop, target, scale
                 auto_create_stops: bool = False,
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None):
        
        self.symbol = symbol
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.link_type = link_type
        self.auto_create_stops = auto_create_stops
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create order and automatically link it."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
        
        try:
            # Create the main order
            order = await order_manager.create_and_submit_order(
                symbol=self.symbol,
                quantity=self.quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                stop_price=self.stop_price
            )
            
            # Link the order
            LinkedOrderManager.add_order(context, self.symbol, order.order_id, self.link_type)
            
            # Auto-create stop loss and take profit if requested
            if self.auto_create_stops and self.link_type == "main":
                await self._create_protective_orders(context, order)
            
            logger.info(f"Created and linked {self.link_type} order {order.order_id} for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating linked order for {self.symbol}: {e}")
            return False
    
    async def _create_protective_orders(self, context: Dict[str, Any], main_order):
        """Create stop loss and take profit orders."""
        order_manager = context.get("order_manager")
        
        # Get current price for percentage calculations
        current_price = self.limit_price or context.get("prices", {}).get(self.symbol)
        if not current_price:
            logger.warning(f"No price available for {self.symbol} protective orders")
            return
        
        # Create stop loss
        if self.stop_loss_pct:
            is_long = self.quantity > 0
            stop_price = current_price * (1 - self.stop_loss_pct) if is_long else current_price * (1 + self.stop_loss_pct)
            
            stop_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=-self.quantity,  # Opposite direction
                order_type=OrderType.STOP,
                stop_price=stop_price
            )
            
            LinkedOrderManager.add_order(context, self.symbol, stop_order.order_id, "stop")
            logger.info(f"Auto-created stop loss {stop_order.order_id} at ${stop_price:.2f}")
        
        # Create take profit
        if self.take_profit_pct:
            is_long = self.quantity > 0
            target_price = current_price * (1 + self.take_profit_pct) if is_long else current_price * (1 - self.take_profit_pct)
            
            target_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=-self.quantity,  # Opposite direction
                order_type=OrderType.LIMIT,
                limit_price=target_price
            )
            
            LinkedOrderManager.add_order(context, self.symbol, target_order.order_id, "target")
            logger.info(f"Auto-created take profit {target_order.order_id} at ${target_price:.2f}")


class LinkedScaleInAction(Action):
    """Scale-in action that automatically links and updates related orders."""
    
    def __init__(self, 
                 symbol: str,
                 scale_quantity: float,
                 trigger_profit_pct: float = 0.02):
        self.symbol = symbol
        self.scale_quantity = scale_quantity
        self.trigger_profit_pct = trigger_profit_pct
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute scale-in and update linked orders."""
        order_manager = context.get("order_manager")
        position_tracker = context.get("position_tracker")
        
        if not order_manager or not position_tracker:
            logger.error("Required managers not found in context")
            return False
        
        try:
            # Check if we have an existing position
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            active_positions = [p for p in positions if p.status.value == "open"]
            
            if not active_positions:
                logger.info(f"No active position for {self.symbol} scale-in")
                return False
            
            position = active_positions[0]
            
            # Check profitability threshold
            if position.unrealized_pnl_pct < self.trigger_profit_pct:
                logger.info(f"Position not profitable enough for scale-in: {position.unrealized_pnl_pct:.2%}")
                return False
            
            # Create scale-in order
            scale_order = await order_manager.create_and_submit_order(
                symbol=self.symbol,
                quantity=self.scale_quantity,
                order_type=OrderType.MARKET
            )
            
            # Link the scale order
            LinkedOrderManager.add_order(context, self.symbol, scale_order.order_id, "scale")
            
            # Update stop and target orders with new average price
            await self._update_protective_orders(context, position, scale_order)
            
            logger.info(f"Scale-in executed: {scale_order.order_id} for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing scale-in for {self.symbol}: {e}")
            return False
    
    async def _update_protective_orders(self, context: Dict[str, Any], position, scale_order):
        """Update stop loss and take profit orders after scale-in."""
        order_manager = context.get("order_manager")
        
        # Calculate new average price
        current_value = position.quantity * position.entry_price
        new_value = scale_order.quantity * position.current_price
        new_quantity = position.quantity + scale_order.quantity
        new_avg_price = (current_value + new_value) / new_quantity
        
        # Get linked stop and target orders
        stop_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "stop")
        target_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "target")
        
        # Update stop orders
        for stop_order_id in stop_orders:
            # Cancel old stop and create new one
            await order_manager.cancel_order(stop_order_id, "Scale-in adjustment")
            LinkedOrderManager.remove_order(context, self.symbol, stop_order_id)
            
            # Create new stop at adjusted price
            new_stop_price = new_avg_price * 0.97  # 3% stop loss
            new_stop = await order_manager.create_order(
                symbol=self.symbol,
                quantity=-new_quantity,
                order_type=OrderType.STOP,
                stop_price=new_stop_price
            )
            LinkedOrderManager.add_order(context, self.symbol, new_stop.order_id, "stop")
            logger.info(f"Updated stop loss to {new_stop_price:.2f} after scale-in")
        
        # Update target orders
        for target_order_id in target_orders:
            # Cancel old target and create new one
            await order_manager.cancel_order(target_order_id, "Scale-in adjustment")
            LinkedOrderManager.remove_order(context, self.symbol, target_order_id)
            
            # Create new target at adjusted price
            new_target_price = new_avg_price * 1.08  # 8% profit target
            new_target = await order_manager.create_order(
                symbol=self.symbol,
                quantity=-new_quantity,
                order_type=OrderType.LIMIT,
                limit_price=new_target_price
            )
            LinkedOrderManager.add_order(context, self.symbol, new_target.order_id, "target")
            logger.info(f"Updated take profit to {new_target_price:.2f} after scale-in")


class LinkedCloseAllAction(Action):
    """Close all linked orders for a symbol."""
    
    def __init__(self, symbol: str, reason: str = "Close all linked orders"):
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Cancel all linked orders and close position."""
        order_manager = context.get("order_manager")
        position_tracker = context.get("position_tracker")
        
        if not order_manager or not position_tracker:
            return False
        
        try:
            # Get all linked orders
            all_orders = LinkedOrderManager.get_linked_orders(context, self.symbol)
            
            # Cancel all orders
            for order_id in all_orders:
                await order_manager.cancel_order(order_id, self.reason)
                LinkedOrderManager.remove_order(context, self.symbol, order_id)
            
            # Close position
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            for position in positions:
                await position_tracker.close_position(position.position_id, self.reason)
            
            # Mark group as closed
            if self.symbol in context:
                context[self.symbol]["status"] = "closed"
            
            logger.info(f"Closed all linked orders and position for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing linked orders for {self.symbol}: {e}")
            return False 