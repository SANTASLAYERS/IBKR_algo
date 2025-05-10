#!/usr/bin/env python3
"""
Order Management System Demo

This script demonstrates the basic usage of the order management system
components of the IBKR Trading Framework.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.event.bus import EventBus
from src.event.order import OrderEvent, NewOrderEvent, OrderStatusEvent, FillEvent
from src.order.base import Order, OrderStatus, OrderType, TimeInForce, OrderSide
from src.order.group import BracketOrder, OCOGroup
from src.order.manager import OrderManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("order_demo")


class OrderDemoHandler:
    """Demo handler for order management."""
    
    def __init__(self, event_bus, order_manager):
        """Initialize the demo handler."""
        self.event_bus = event_bus
        self.order_manager = order_manager
        
        # Store filled orders for position creation
        self.filled_orders = {}
    
    async def initialize(self):
        """Set up event subscriptions."""
        # Subscribe to order events
        await self.event_bus.subscribe(NewOrderEvent, self.handle_order_event)
        await self.event_bus.subscribe(OrderStatusEvent, self.handle_order_event)
        await self.event_bus.subscribe(FillEvent, self.handle_order_event)
        
        logger.info("OrderDemoHandler initialized and subscribed to events")
    
    async def handle_order_event(self, event):
        """Handle order events."""
        # Log the event details
        if isinstance(event, NewOrderEvent):
            logger.info(f"New order: {event.symbol} - Order ID: {event.order_id}")
        elif isinstance(event, OrderStatusEvent):
            logger.info(f"Order status update: {event.symbol} - Status: {event.status.value}")
        elif isinstance(event, FillEvent):
            logger.info(f"Order fill: {event.symbol} - Qty: {event.fill_quantity} @ {event.fill_price}")
            
            # Store filled orders for position creation
            if event.status == OrderStatus.FILLED:
                self.filled_orders[event.order_id] = {
                    "symbol": event.symbol,
                    "quantity": event.fill_quantity,
                    "price": event.fill_price
                }


async def simulate_order_lifecycle():
    """Simulate a complete order lifecycle."""
    # Create the event bus
    event_bus = EventBus()
    
    # Create the order manager
    order_manager = OrderManager(event_bus)
    
    # Create the demo handler
    demo_handler = OrderDemoHandler(event_bus, order_manager)
    await demo_handler.initialize()
    
    logger.info("Starting order lifecycle simulation")
    
    # 1. Create and submit a simple market order
    logger.info("\n=== Simple Market Order ===")
    market_order = await order_manager.create_order(
        symbol="AAPL",
        quantity=100,  # Buy 100 shares
        order_type=OrderType.MARKET,
        auto_submit=True  # Automatically submit the order
    )
    
    # Wait for order processing
    await asyncio.sleep(0.5)
    
    # Simulate a fill
    await order_manager.process_fill(
        order_id=market_order.order_id,
        quantity=100,
        price=150.0
    )
    
    await asyncio.sleep(0.5)
    
    # 2. Create and submit a limit order
    logger.info("\n=== Limit Order ===")
    limit_order = await order_manager.create_order(
        symbol="MSFT",
        quantity=50,  # Buy 50 shares
        order_type=OrderType.LIMIT,
        limit_price=250.0
    )
    
    # Submit the order
    await order_manager.submit_order(limit_order.order_id)
    
    await asyncio.sleep(0.5)
    
    # Simulate a partial fill
    await order_manager.process_fill(
        order_id=limit_order.order_id,
        quantity=25,
        price=250.0
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate another partial fill
    await order_manager.process_fill(
        order_id=limit_order.order_id,
        quantity=25,
        price=249.8
    )
    
    await asyncio.sleep(0.5)
    
    # 3. Create and submit a bracket order
    logger.info("\n=== Bracket Order ===")
    bracket = await order_manager.create_bracket_order(
        symbol="GOOG",
        quantity=10,  # Buy 10 shares
        entry_price=2500.0,  # Limit price for entry
        stop_loss_price=2450.0,  # Stop loss price
        take_profit_price=2550.0,  # Take profit price
        entry_type=OrderType.LIMIT,
        auto_submit=True  # Automatically submit the entry order
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate a fill on the entry order
    await order_manager.process_fill(
        order_id=bracket.entry_order_id,
        quantity=10,
        price=2500.0
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate a fill on the take profit order
    await order_manager.process_fill(
        order_id=bracket.take_profit_order_id,
        quantity=10,
        price=2550.0
    )
    
    await asyncio.sleep(0.5)
    
    # 4. Create and submit OCO orders
    logger.info("\n=== OCO Orders ===")
    
    # Create orders for the OCO group
    oco_orders = [
        {
            "symbol": "AMZN",
            "quantity": -20,  # Sell 20 shares
            "order_type": OrderType.LIMIT,
            "limit_price": 3300.0
        },
        {
            "symbol": "AMZN",
            "quantity": -20,  # Sell 20 shares
            "order_type": OrderType.STOP,
            "stop_price": 3200.0
        }
    ]
    
    oco_group = await order_manager.create_oco_orders(
        orders=oco_orders,
        auto_submit=True
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate a fill on the limit order
    oco_orders = oco_group.get_orders()
    await order_manager.process_fill(
        order_id=oco_orders[0].order_id,
        quantity=20,
        price=3300.0
    )
    
    await asyncio.sleep(0.5)
    
    # 5. Create an order and then cancel it
    logger.info("\n=== Order Cancellation ===")
    
    cancel_order = await order_manager.create_order(
        symbol="TSLA",
        quantity=30,  # Buy 30 shares
        order_type=OrderType.LIMIT,
        limit_price=700.0,
        auto_submit=True
    )
    
    await asyncio.sleep(0.5)
    
    # Cancel the order
    await order_manager.cancel_order(cancel_order.order_id, "Testing cancellation")
    
    await asyncio.sleep(0.5)
    
    # 6. Check active and completed orders
    logger.info("\n=== Order Status Summary ===")
    
    active_orders = await order_manager.get_active_orders()
    logger.info(f"Active orders: {len(active_orders)}")
    for order in active_orders:
        logger.info(f"  {order}")
    
    completed_orders = await order_manager.get_completed_orders()
    logger.info(f"Completed orders: {len(completed_orders)}")
    for order in completed_orders:
        logger.info(f"  {order}")
    
    logger.info("\nSimulation completed")


if __name__ == "__main__":
    asyncio.run(simulate_order_lifecycle())