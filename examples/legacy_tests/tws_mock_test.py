#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Mock Test - Simulated AAPL Order Test

This script demonstrates how the order submission process would work
with Interactive Brokers TWS, but uses a mock implementation since
the actual TWS instance is not properly communicating from WSL.
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timedelta

from ibapi.contract import Contract
from ibapi.order import Order

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tws_mock_test")


def create_stock_contract(symbol):
    """Create a stock contract for trading."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


def create_market_order(action, quantity):
    """Create a market order."""
    order = Order()
    order.action = action
    order.orderType = "MKT"
    order.totalQuantity = quantity
    order.tif = "DAY"
    # Add a unique order ID reference for tracking
    order.orderRef = f"TEST_ORDER_{uuid.uuid4().hex[:8]}"
    return order


class MockIBKRConnection:
    """A mock IBKR connection for testing."""
    
    def __init__(self):
        """Initialize the mock connection."""
        self.is_connected_val = False
        self.orders = {}
        self.next_order_id = 1000
        
        # Callback placeholders
        self.nextValidId = lambda x: None
        self.orderStatus = lambda *args: None
        self.error = lambda *args: None
        
    async def connect_async(self):
        """Simulate connecting to TWS."""
        logger.info("Mock: Connecting to TWS at 172.28.64.1:7497")
        await asyncio.sleep(1)  # Simulate connection time
        self.is_connected_val = True
        
        # Call nextValidId callback with initial ID
        self.nextValidId(self.next_order_id)
        return True
        
    def disconnect(self):
        """Simulate disconnecting from TWS."""
        logger.info("Mock: Disconnecting from TWS")
        self.is_connected_val = False
        
    def is_connected(self):
        """Check if the mock connection is connected."""
        return self.is_connected_val
        
    def reqIds(self, num_ids):
        """Simulate requesting order IDs."""
        logger.info(f"Mock: Requesting {num_ids} order ID(s)")
        # Call the nextValidId callback with the next ID
        self.nextValidId(self.next_order_id)
        
    def placeOrder(self, order_id, contract, order):
        """Simulate placing an order."""
        logger.info(f"Mock: Placing order #{order_id} to {order.action} {order.totalQuantity} "
                   f"{contract.symbol} @ {order.orderType}")
        
        # Store the order
        self.orders[order_id] = {
            "contract": contract,
            "order": order,
            "status": "Submitted"
        }
        
        # Schedule order updates
        asyncio.create_task(self._process_order(order_id))
        
    def cancelOrder(self, order_id):
        """Simulate cancelling an order."""
        if order_id in self.orders:
            logger.info(f"Mock: Cancelling order #{order_id}")
            self.orders[order_id]["status"] = "Cancelled"
            
            # Notify via callback
            self.orderStatus(
                order_id, 
                "Cancelled", 
                0, 
                self.orders[order_id]["order"].totalQuantity,
                0, 0, 0, 0, 0, ""
            )
        else:
            logger.error(f"Mock: Order #{order_id} not found")
            self.error(order_id, 404, "Order not found")
            
    async def _process_order(self, order_id):
        """Simulate order processing with status updates."""
        if order_id not in self.orders:
            return
            
        # Simulate pending status
        await asyncio.sleep(0.5)
        self.orders[order_id]["status"] = "Pending Submit"
        self.orderStatus(
            order_id, 
            "PendingSubmit", 
            0, 
            self.orders[order_id]["order"].totalQuantity,
            0, 0, 0, 0, 0, ""
        )
        
        # Simulate submitted status
        await asyncio.sleep(0.5)
        self.orders[order_id]["status"] = "Submitted"
        self.orderStatus(
            order_id, 
            "Submitted", 
            0, 
            self.orders[order_id]["order"].totalQuantity,
            0, 0, 0, 0, 0, ""
        )
        
        # Simulate filled status
        await asyncio.sleep(1.0)
        price = 150.25  # Mock price for AAPL
        quantity = self.orders[order_id]["order"].totalQuantity
        self.orders[order_id]["status"] = "Filled"
        self.orderStatus(
            order_id, 
            "Filled", 
            quantity, 
            0,  # remaining
            price, 0, 0, price, 0, ""
        )


async def buy_aapl_shares():
    """Test function to buy 1 share of AAPL using the mock connection."""
    # Create mock connection
    connection = MockIBKRConnection()
    
    # Track the order ID and status
    next_order_id = None
    order_status = {}
    order_filled = asyncio.Event()
    
    # Define callbacks for order updates
    def nextValidId_callback(order_id):
        nonlocal next_order_id
        next_order_id = order_id
        logger.info(f"Received next valid order ID: {order_id}")
    
    def orderStatus_callback(orderId, status, filled, remaining, avgFillPrice, 
                           permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice=""):
        nonlocal order_status
        order_status = {
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "lastFillPrice": lastFillPrice
        }
        logger.info(f"Order status update: ID={orderId}, Status={status}, Filled={filled}/{filled+remaining} @ ${avgFillPrice}")
        
        # If the order is filled or done, set the event
        if status in ["Filled", "Cancelled", "ApiCancelled"]:
            order_filled.set()
    
    def error_callback(reqId, errorCode, errorString, advancedOrderRejectJson=""):
        logger.error(f"Error {errorCode}: {errorString} (reqId: {reqId})")
        
        # If this is a serious error related to our order, set the event to avoid hanging
        if reqId == next_order_id and errorCode >= 400:
            order_filled.set()
    
    try:
        # Set our callbacks
        connection.nextValidId = nextValidId_callback
        connection.orderStatus = orderStatus_callback
        connection.error = error_callback
        
        # Connect to mock TWS
        logger.info("Connecting to mock TWS...")
        connected = await connection.connect_async()
        
        if not connected:
            logger.error("Failed to connect to mock TWS")
            return False
            
        logger.info("Successfully connected to mock TWS")
        
        # We should already have received the next valid order ID
        # from the connect process, but let's request it again to be sure
        logger.info("Requesting next valid order ID...")
        connection.reqIds(1)
        
        # Wait for next valid order ID
        timeout = datetime.now() + timedelta(seconds=5)
        while next_order_id is None and datetime.now() < timeout:
            await asyncio.sleep(0.1)
        
        if next_order_id is None:
            logger.error("Did not receive valid order ID from mock TWS")
            return False
        
        # Create stock contract for AAPL
        symbol = "AAPL"
        contract = create_stock_contract(symbol)
        
        # Create a market order to buy 1 share
        quantity = 1
        buy_order = create_market_order("BUY", quantity)
        
        # Place the order
        logger.info(f"Placing order to BUY {quantity} share(s) of {symbol}")
        connection.placeOrder(next_order_id, contract, buy_order)
        
        # Wait for order to be filled or cancelled
        try:
            # Wait up to 30 seconds for the order to complete
            await asyncio.wait_for(order_filled.wait(), timeout=30)
            
            # Check final order status
            if order_status.get("status") == "Filled":
                logger.info(f"Order successfully filled: {quantity} share(s) of {symbol} @ ${order_status.get('avgFillPrice')}")
                logger.info(f"Order reference: {buy_order.orderRef}")
                return True
            else:
                logger.warning(f"Order not filled. Final status: {order_status.get('status')}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for order status updates")
            return False
            
    except Exception as e:
        logger.error(f"Error in buy AAPL test: {e}")
        return False
        
    finally:
        # Disconnect
        if connection.is_connected():
            logger.info("Disconnecting from mock TWS...")
            connection.disconnect()
            logger.info("Disconnected from mock TWS")


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(buy_aapl_shares())
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)