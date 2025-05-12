#!/usr/bin/env python3
"""
IBKR Gateway Order Integration Demo

This example demonstrates the integration between the Order Management System
and the Interactive Brokers Gateway, showing how to place orders, track their
status, and handle fills.

IMPORTANT: This demo uses paper trading. Never run with a live trading account
without explicit modification and thorough testing.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.event.bus import EventBus
from src.event.order import OrderEvent, OrderStatusEvent, FillEvent, CancelEvent
from src.gateway import IBGateway, IBGatewayConfig
from src.order.base import Order, OrderStatus, OrderType, TimeInForce, OrderSide
from src.order.manager import OrderManager
from src.gateway_order_manager import OrderGatewayIntegration

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("order_demo")

# Configuration - read from environment or use defaults
IB_HOST = os.environ.get("IB_HOST", "127.0.0.1")
IB_PORT = int(os.environ.get("IB_PORT", "4002"))  # Paper trading port
IB_CLIENT_ID = int(os.environ.get("IB_CLIENT_ID", "1"))
IB_ACCOUNT = os.environ.get("IB_ACCOUNT", "")  # Account ID
DEMO_SYMBOL = os.environ.get("DEMO_SYMBOL", "SPY")  # Default to SPY
DEMO_QUANTITY = int(os.environ.get("DEMO_QUANTITY", "1"))  # Small quantity for demo


class OrderEventHandler:
    """Handles order events for the demo."""
    
    def __init__(self):
        """Initialize the event handler."""
        self.orders = {}
        self.status_updates = {}
        self.fills = {}
        self.cancels = {}
    
    async def handle_order_status(self, event):
        """Handle order status update events."""
        logger.info(f"Order Status Update: {event.order_id} - {event.status.value}")
        if event.order_id not in self.status_updates:
            self.status_updates[event.order_id] = []
        self.status_updates[event.order_id].append(event)
    
    async def handle_fill(self, event):
        """Handle order fill events."""
        logger.info(f"Order Fill: {event.order_id} - {event.fill_quantity} @ {event.fill_price}")
        if event.order_id not in self.fills:
            self.fills[event.order_id] = []
        self.fills[event.order_id].append(event)
    
    async def handle_cancel(self, event):
        """Handle order cancellation events."""
        logger.info(f"Order Cancel: {event.order_id} - {event.reason}")
        self.cancels[event.order_id] = event


async def get_current_price(gateway, symbol):
    """Get the current market price for a symbol."""
    from ibapi.contract import Contract
    
    # Create a contract for the symbol
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    
    # Create a Future to get the price
    price_future = asyncio.Future()
    
    # Define callback
    def price_callback(data):
        if not price_future.done() and data.get("last_price"):
            price_future.set_result(data["last_price"])
    
    # Subscribe to market data
    req_id = gateway.subscribe_market_data(contract, callback=price_callback)
    
    try:
        # Wait for the price (with timeout)
        return await asyncio.wait_for(price_future, timeout=10.0)
    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for {symbol} price")
        return None
    finally:
        # Unsubscribe from market data
        gateway.unsubscribe_market_data(req_id)


async def demo_market_order(order_manager, event_handler, symbol, quantity):
    """Demo placing a market order and tracking its status."""
    logger.info(f"\n=== Demo Market Order for {symbol} ===")
    
    # Create a market order
    order = await order_manager.create_order(
        symbol=symbol,
        quantity=quantity,
        order_type=OrderType.MARKET,
        auto_submit=False
    )
    
    logger.info(f"Created market order: {order.order_id}")
    
    # Submit the order
    success = await order_manager.submit_order(order.order_id)
    if not success:
        logger.error("Failed to submit market order")
        return None
    
    logger.info(f"Submitted market order: {order.order_id}")
    
    # Wait for the order to be processed
    for _ in range(30):  # Wait up to 30 seconds
        # Check if we have a fill
        if order.order_id in event_handler.fills:
            logger.info(f"Market order filled: {order.order_id}")
            return order
        
        # Check if we have a status update
        if order.order_id in event_handler.status_updates:
            status_events = event_handler.status_updates[order.order_id]
            latest_status = status_events[-1].status
            if latest_status in [OrderStatus.REJECTED, OrderStatus.CANCELLED]:
                logger.warning(f"Market order not filled: {latest_status.value}")
                return None
        
        await asyncio.sleep(1)
    
    logger.warning("Timeout waiting for market order fill")
    return None


async def demo_limit_order(order_manager, event_handler, symbol, quantity, current_price):
    """Demo placing a limit order below market price and cancelling it."""
    logger.info(f"\n=== Demo Limit Order for {symbol} ===")
    
    # Use a price below current market to avoid execution
    limit_price = current_price - (current_price * 0.05)  # 5% below market
    
    # Create a limit order
    order = await order_manager.create_order(
        symbol=symbol,
        quantity=quantity,
        order_type=OrderType.LIMIT,
        limit_price=limit_price,
        auto_submit=False
    )
    
    logger.info(f"Created limit order: {order.order_id} @ {limit_price}")
    
    # Submit the order
    success = await order_manager.submit_order(order.order_id)
    if not success:
        logger.error("Failed to submit limit order")
        return None
    
    logger.info(f"Submitted limit order: {order.order_id}")
    
    # Wait for the order to be acknowledged
    acknowledged = False
    for _ in range(10):  # Wait up to 10 seconds
        if order.order_id in event_handler.status_updates:
            status_events = event_handler.status_updates[order.order_id]
            latest_status = status_events[-1].status
            if latest_status in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED]:
                acknowledged = True
                logger.info(f"Limit order acknowledged: {latest_status.value}")
                break
        await asyncio.sleep(1)
    
    if not acknowledged:
        logger.warning("Limit order not acknowledged")
        return None
    
    # Wait 5 seconds and then cancel the order
    await asyncio.sleep(5)
    
    # Cancel the order
    logger.info(f"Cancelling limit order: {order.order_id}")
    cancel_success = await order_manager.cancel_order(order.order_id, "Demo cancellation")
    
    if not cancel_success:
        logger.error("Failed to cancel limit order")
        return None
    
    # Wait for cancellation to be confirmed
    cancelled = False
    for _ in range(10):  # Wait up to 10 seconds
        if order.order_id in event_handler.cancels:
            cancelled = True
            logger.info("Limit order cancellation confirmed")
            break
            
        if order.order_id in event_handler.status_updates:
            status_events = event_handler.status_updates[order.order_id]
            latest_status = status_events[-1].status
            if latest_status == OrderStatus.CANCELLED:
                cancelled = True
                logger.info("Limit order cancellation confirmed via status update")
                break
                
        await asyncio.sleep(1)
    
    if not cancelled:
        logger.warning("Limit order cancellation not confirmed")
        
    return order


async def demo_bracket_order(order_manager, event_handler, symbol, quantity, current_price):
    """Demo placing a bracket order below market price and cancelling it."""
    logger.info(f"\n=== Demo Bracket Order for {symbol} ===")
    
    # Use prices below market to avoid execution
    entry_price = current_price - (current_price * 0.05)  # 5% below market
    stop_loss_price = entry_price - (entry_price * 0.02)  # 2% below entry
    take_profit_price = entry_price + (entry_price * 0.03)  # 3% above entry
    
    # Create a bracket order
    bracket = await order_manager.create_bracket_order(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        entry_type=OrderType.LIMIT,
        auto_submit=False
    )
    
    logger.info(f"Created bracket order: {bracket.entry_order_id}")
    logger.info(f"  Entry: {entry_price}")
    logger.info(f"  Stop Loss: {stop_loss_price}")
    logger.info(f"  Take Profit: {take_profit_price}")
    
    # Submit the entry order
    success = await order_manager.submit_order(bracket.entry_order_id)
    if not success:
        logger.error("Failed to submit bracket entry order")
        return None
    
    logger.info(f"Submitted bracket entry order: {bracket.entry_order_id}")
    
    # Wait for the order to be acknowledged
    acknowledged = False
    for _ in range(10):  # Wait up to 10 seconds
        if bracket.entry_order_id in event_handler.status_updates:
            status_events = event_handler.status_updates[bracket.entry_order_id]
            latest_status = status_events[-1].status
            if latest_status in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED]:
                acknowledged = True
                logger.info(f"Bracket entry order acknowledged: {latest_status.value}")
                break
        await asyncio.sleep(1)
    
    if not acknowledged:
        logger.warning("Bracket entry order not acknowledged")
        return None
    
    # Wait 5 seconds and then cancel the bracket
    await asyncio.sleep(5)
    
    # Cancel the bracket (which will cancel all orders in the group)
    logger.info(f"Cancelling bracket order: {bracket.group_id}")
    cancelled_count = await order_manager.cancel_order_group(bracket.group_id, "Demo cancellation")
    
    logger.info(f"Cancelled {cancelled_count} orders in bracket")
    
    # Wait for cancellation to be confirmed
    cancelled = False
    for _ in range(10):  # Wait up to 10 seconds
        if bracket.entry_order_id in event_handler.cancels:
            cancelled = True
            logger.info("Bracket order cancellation confirmed")
            break
            
        if bracket.entry_order_id in event_handler.status_updates:
            status_events = event_handler.status_updates[bracket.entry_order_id]
            latest_status = status_events[-1].status
            if latest_status == OrderStatus.CANCELLED:
                cancelled = True
                logger.info("Bracket order cancellation confirmed via status update")
                break
                
        await asyncio.sleep(1)
    
    if not cancelled:
        logger.warning("Bracket order cancellation not confirmed")
        
    return bracket


async def run_demo():
    """Run the order management integration demo."""
    logger.info("Starting IBKR Gateway Order Integration Demo")
    
    # Create event bus
    event_bus = EventBus()
    
    # Create event handler
    event_handler = OrderEventHandler()
    
    # Subscribe to order events
    await event_bus.subscribe(OrderStatusEvent, event_handler.handle_order_status)
    await event_bus.subscribe(FillEvent, event_handler.handle_fill)
    await event_bus.subscribe(CancelEvent, event_handler.handle_cancel)
    
    # Create gateway configuration
    gateway_config = IBGatewayConfig(
        host=IB_HOST,
        port=IB_PORT,
        client_id=IB_CLIENT_ID,
        account_id=IB_ACCOUNT,
        trading_mode="paper"
    )
    
    # Create gateway
    gateway = IBGateway(gateway_config)
    
    # Create order manager
    order_manager = OrderManager(event_bus)
    
    # Create and initialize the integration
    integration = OrderGatewayIntegration(gateway, order_manager)
    integration.initialize()
    
    # Connect to gateway
    connected = await gateway.connect_gateway()
    if not connected:
        logger.error("Failed to connect to IBKR Gateway")
        return
    
    logger.info("Connected to IBKR Gateway")
    
    try:
        # Wait for connection to fully initialize
        await asyncio.sleep(2)
        
        # Get current price for the demo symbol
        current_price = await get_current_price(gateway, DEMO_SYMBOL)
        if not current_price:
            logger.error(f"Could not get current price for {DEMO_SYMBOL}")
            return
        
        logger.info(f"Current price for {DEMO_SYMBOL}: {current_price}")
        
        # Demo limit order
        await demo_limit_order(order_manager, event_handler, DEMO_SYMBOL, DEMO_QUANTITY, current_price)
        
        # Demo bracket order
        await demo_bracket_order(order_manager, event_handler, DEMO_SYMBOL, DEMO_QUANTITY, current_price)
        
        # Optional: Demo market order - only uncomment if you want to place a real market order
        # await demo_market_order(order_manager, event_handler, DEMO_SYMBOL, DEMO_QUANTITY)
        
        # Show summary of orders
        logger.info("\n=== Order Summary ===")
        active_orders = await order_manager.get_active_orders()
        logger.info(f"Active orders: {len(active_orders)}")
        
        completed_orders = await order_manager.get_completed_orders()
        logger.info(f"Completed orders: {len(completed_orders)}")
        for order in completed_orders:
            logger.info(f"  {order.order_id}: {order.symbol} - {order.status.value}")
        
    finally:
        # Cleanup - cancel any active orders
        active_orders = await order_manager.get_active_orders()
        if active_orders:
            logger.info(f"Cancelling {len(active_orders)} active orders")
            await order_manager.cancel_all_orders(reason="Demo cleanup")
        
        # Shutdown integration
        integration.shutdown()
        
        # Disconnect from gateway
        gateway.disconnect()
        logger.info("Disconnected from IBKR Gateway")


if __name__ == "__main__":
    asyncio.run(run_demo())