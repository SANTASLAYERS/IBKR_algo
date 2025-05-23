#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from src.connection import IBKRConnection
from src.config import Config
from src.error_handler import ErrorHandler
from src.logger import get_logger

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = get_logger("debug_order_test")

async def main():
    """Test order submission with TWS"""
    # Create configuration
    config = Config()
    config.host = "172.28.64.1"  # WSL host for Windows connection
    config.port = 7497  # TWS port
    config.client_id = 1234  # Unique client ID
    config.heartbeat_timeout = 30  # 30 second timeout
    config.max_reconnect_attempts = 3
    config.reconnect_delay = 1.0  # 1 second delay

    # Create error handler
    error_handler = ErrorHandler()

    # Create connection
    connection = IBKRConnection(config, error_handler)
    
    # Initialize tracking variables
    order_status = {}
    order_id = None
    
    # Define callbacks to track order status
    def order_status_callback(status_update):
        nonlocal order_status
        order_status = status_update
        logger.info(f"Order status update: {status_update}")

    # Register callback
    connection.register_order_status_callback(order_status_callback)

    # Override the TWS orderStatus method directly for debugging
    original_order_status = connection.orderStatus

    def order_status_debug(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        logger.info(f"DIRECT ORDER STATUS: orderId={orderId}, status={status}, filled={filled}, remaining={remaining}")
        # Call the original method
        original_order_status(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)

    # Replace the method
    connection.orderStatus = order_status_debug
    
    try:
        # Connect to TWS
        logger.info("Connecting to TWS...")
        connected = await connection.connect_async()
        
        if not connected:
            logger.error("Failed to connect to TWS")
            return
        
        logger.info(f"Connected to TWS. Client ID: {connection.client_id}, Account ID: {connection.account_id}")
        
        # Wait for account information to be received
        await asyncio.sleep(2)
        
        if not connection.account_id:
            logger.warning("No account ID received yet. Waiting longer...")
            await asyncio.sleep(3)
        
        logger.info(f"Using account ID: {connection.account_id}")
        
        # Create a contract for testing
        symbol = "SPY"
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Create a very small limit order (1 share) at a low price to avoid execution
        # This will just test order submission, not actual execution
        iborder = IBOrder()
        iborder.action = "BUY"
        iborder.orderType = "LMT"
        iborder.totalQuantity = 1
        iborder.lmtPrice = 100.0  # Set a low price that won't execute

        # Make sure we only set properties that TWS supports
        # Set eTradeOnly to False - it's True by default and causing the error
        iborder.eTradeOnly = False
        iborder.firmQuoteOnly = False  # This is also True by default

        iborder.transmit = True
        iborder.outsideRth = False
        iborder.tif = "DAY"  # Time in force - good for the day

        # Add a unique client ID for tracking
        iborder.orderId = 0  # Let IB assign ID
        iborder.clientId = connection.client_id
        if connection.account_id:
            iborder.account = connection.account_id
        
        # Submit the order
        logger.info(f"Submitting limit order for {symbol} at $100: {iborder}")
        order_id = connection.submit_order(contract, iborder)
        
        if not order_id or order_id <= 0:
            logger.error(f"Order submission failed, received invalid ID: {order_id}")
            return
        
        logger.info(f"Order submitted successfully, ID: {order_id}")
        
        # Wait for order status updates
        timeout = 15  # 15 seconds
        start_time = datetime.now()
        
        while datetime.now() - start_time < timedelta(seconds=timeout):
            # Check if we've received any status updates
            if order_status and order_status.get('order_id') == order_id:
                logger.info(f"Received order status: {order_status}")
                
                # Check if order is acknowledged by IB
                status = order_status.get('status')
                if status in ['Submitted', 'PreSubmitted', 'Filled', 'Cancelled']:
                    logger.info(f"Order {order_id} status: {status}")
                    break
            
            # Wait a bit before checking again
            await asyncio.sleep(0.5)
            logger.info("Waiting for order status update...")
        
        # Validate order status
        if not order_status:
            logger.error(f"No order status received for order {order_id}")
        elif order_status.get('order_id') != order_id:
            logger.error(f"Order ID mismatch: {order_status.get('order_id')} != {order_id}")
        else:
            # Consider these statuses acceptable for a limit order
            acceptable_statuses = ['Submitted', 'PreSubmitted', 'Filled']
            status = order_status.get('status')
            
            if status in acceptable_statuses:
                logger.info(f"Order test successful! Status: {status}")
            else:
                logger.warning(f"Unexpected order status: {status}, expected one of {acceptable_statuses}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        raise
    
    finally:
        # Always try to cancel the order if it was submitted
        if order_id and order_id > 0:
            try:
                connection.cancel_order(order_id)
                logger.info(f"Cancelled test order {order_id}")
            except Exception as e:
                logger.warning(f"Error cancelling order {order_id}: {str(e)}")
        
        # Disconnect from TWS
        logger.info("Disconnecting from TWS")
        connection.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Test interrupted by user")
    except Exception as e:
        print(f"Error in main: {str(e)}")
        sys.exit(1)