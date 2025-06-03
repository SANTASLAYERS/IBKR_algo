#!/usr/bin/env python3
"""
Simple Order Test
=================

Test placing a single order and monitoring its status.
"""

import asyncio
import logging
from datetime import datetime

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleOrderTest:
    def __init__(self):
        self.tws_connection = None
        self.order_placed = False
        
    async def run(self):
        """Run the simple order test."""
        # Setup TWS connection
        config = TWSConfig.from_env()
        self.tws_connection = TWSConnection(config)
        
        # Override orderStatus callback
        original_orderStatus = self.tws_connection.orderStatus
        def on_order_status(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
            logger.info(f"ORDER STATUS: ID={orderId}, Status={status}, Filled={filled}, Remaining={remaining}")
            original_orderStatus(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
        
        self.tws_connection.orderStatus = on_order_status
        
        # Connect to TWS
        logger.info("Connecting to TWS...")
        connected = await self.tws_connection.connect()
        if not connected:
            logger.error("Failed to connect to TWS")
            return
            
        logger.info("Connected to TWS")
        
        # Wait a bit for connection to stabilize
        await asyncio.sleep(2)
        
        # Get order ID
        order_id = self.tws_connection.get_next_order_id()
        if not order_id:
            logger.error("No order ID available")
            return
            
        logger.info(f"Using order ID: {order_id}")
        
        # Create contract
        contract = Contract()
        contract.symbol = "SLV"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Create order
        order = IBOrder()
        order.action = "BUY"
        order.totalQuantity = 100
        order.orderType = "MKT"
        order.tif = "DAY"
        
        # Place order
        logger.info(f"Placing order: BUY 100 SLV @ MARKET")
        self.tws_connection.placeOrder(order_id, contract, order)
        self.order_placed = True
        
        # Wait for order updates
        logger.info("Waiting for order updates...")
        await asyncio.sleep(10)
        
        # Cancel if still active
        if self.order_placed:
            logger.info(f"Cancelling order {order_id}")
            self.tws_connection.cancelOrder(order_id)
            await asyncio.sleep(2)
        
        # Disconnect
        logger.info("Disconnecting...")
        self.tws_connection.disconnect()
        

async def main():
    test = SimpleOrderTest()
    await test.run()


if __name__ == "__main__":
    print("\nSIMPLE ORDER TEST")
    print("=================")
    print("This will place a BUY 100 SLV @ MARKET order")
    print("NOTE: This is a REAL order (use paper trading!)")
    print()
    
    response = input("Proceed? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 