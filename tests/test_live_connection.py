#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Live connection test for IBKR Gateway connection.
This test script verifies our custom IBGateway implementation connection to a real IBKR Gateway instance.

Usage:
    python tests/test_live_connection.py [--host HOST] [--port PORT] [--client-id CLIENT_ID]

Example:
    python tests/test_live_connection.py --host 172.28.64.1 --port 4002 --client-id 1
"""

import argparse
import asyncio
import logging
import sys
import traceback
from datetime import datetime

# Import our custom implementation
from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler
from ibapi.contract import Contract

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default connection parameters
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 1

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Test IBKR Gateway connection')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help='Gateway hostname or IP')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Gateway port')
    parser.add_argument('--client-id', type=int, dest='client_id', default=DEFAULT_CLIENT_ID, help='Client ID')
    return parser.parse_args()

async def test_custom_gateway(host, port, client_id):
    """
    Test connection using our custom gateway implementation.
    
    Args:
        host: Gateway hostname or IP
        port: Gateway port
        client_id: Client ID
        
    Returns:
        bool: True if test succeeded, False otherwise
    """
    logger.info("=== Testing connection with our custom IBGateway ===")
    
    # Create configuration
    config = IBGatewayConfig(
        host=host,
        port=port,
        client_id=client_id,
        trading_mode="paper" if port == 4002 else "live",
        heartbeat_timeout=10.0,
        heartbeat_interval=5.0,
        reconnect_delay=1.0,
        max_reconnect_attempts=3
    )
    
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create gateway
    gateway = IBGateway(config, error_handler)
    
    try:
        # Connect to IBKR Gateway
        logger.info(f"Connecting to {host}:{port} (clientId: {client_id})...")
        connected = await gateway.connect_gateway()
        
        # Verify connection
        if connected and gateway.is_connected():
            logger.info("✅ Connected to IBKR API using custom gateway!")
            
            # Request current time (also serves as heartbeat)
            gateway.reqHeartbeat()
            logger.info("Heartbeat requested")
            
            # Wait a bit for data to be processed
            await asyncio.sleep(3)
            
            # We can't directly get account information, but we can check the connection state
            if gateway.connection_state == "connected":
                logger.info("Connection is in 'connected' state")
            else:
                logger.warning(f"Connection state is: {gateway.connection_state}")
            
            # Create contract for Apple
            apple_contract = Contract()
            apple_contract.symbol = "AAPL"
            apple_contract.secType = "STK"
            apple_contract.exchange = "SMART"
            apple_contract.currency = "USD"
            
            # Define callback for market data
            def market_data_callback(data):
                logger.info(f"Market data received: {data}")
            
            # Subscribe to market data
            logger.info("Subscribing to AAPL market data...")
            req_id = gateway.subscribe_market_data(apple_contract, callback=market_data_callback)
            logger.info(f"Subscription ID: {req_id}")
            
            # Wait for market data
            await asyncio.sleep(5)
            
            # Get current market data
            market_data = gateway.get_market_data(req_id)
            if market_data:
                logger.info(f"Market data: {market_data}")
            else:
                logger.warning("No market data received")
            
            # Unsubscribe
            gateway.unsubscribe_market_data(req_id)
            logger.info("Unsubscribed from market data")
            
            return True
        else:
            logger.error("❌ Failed to connect to IBKR API using custom gateway")
            return False
            
    except Exception as e:
        logger.error(f"❌ Connection error with custom gateway: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        # Disconnect
        if gateway.is_connected():
            logger.info("Disconnecting from IBKR API...")
            gateway.disconnect()
            logger.info("Disconnected")

async def main():
    """Main test function."""
    # Parse command-line arguments
    args = parse_args()
    
    logger.info(f"Starting IBKR connection tests at {datetime.now()}")
    logger.info(f"Connection parameters: host={args.host}, port={args.port}, client_id={args.client_id}")
    
    # Test our custom gateway connection
    gateway_success = await test_custom_gateway(args.host, args.port, args.client_id)
    
    # Report results
    logger.info("\n=== Test Results ===")
    logger.info(f"Custom gateway connection: {'✅ Success' if gateway_success else '❌ Failed'}")
    
    # Return overall success
    return gateway_success

if __name__ == "__main__":
    # Enable asyncio debugging (helps with coroutines that never get awaited)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the tests
    success = asyncio.run(main())
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)