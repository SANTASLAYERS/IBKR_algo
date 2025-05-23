#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple connectivity test for IB Gateway using our custom gateway implementation.
This script attempts to connect to IB Gateway and verify the connection.

Usage:
    python test_gateway_connectivity.py --host HOST --port PORT

Example:
    python test_gateway_connectivity.py --host 172.28.64.1 --port 4002
"""

import argparse
import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our custom Gateway implementation
from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler

# Default connection parameters
DEFAULT_HOST = '127.0.0.1'  # For local TWS/Gateway
DEFAULT_PORT = 4002          # Paper trading port
DEFAULT_CLIENT_ID = 1

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Test IB Gateway connectivity')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help='Gateway hostname or IP')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Gateway port')
    parser.add_argument('--client-id', type=int, dest='client_id', default=DEFAULT_CLIENT_ID, help='Client ID')
    return parser.parse_args()

async def test_connection(host, port, client_id):
    """Test connection to IB Gateway using custom gateway implementation."""
    logger.info(f"Testing connection to {host}:{port} with client ID {client_id}")
    
    # Create gateway configuration
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
    
    # Create gateway instance
    gateway = IBGateway(config, error_handler)
    
    try:
        # Connect to IB Gateway
        logger.info(f"Connecting to {host}:{port}...")
        connected = await gateway.connect_gateway()
        
        # Verify connection
        if connected and gateway.is_connected():
            logger.info("✅ Successfully connected to IB Gateway!")
            
            # Request current time (also serves as heartbeat)
            gateway.reqHeartbeat()
            logger.info("Heartbeat requested")
            
            # Wait a bit for data to be processed
            await asyncio.sleep(2)
            
            # Request account information from IB Gateway
            # This will be processed asynchronously through callbacks
            gateway.reqCurrentTime()  # Additional heartbeat to verify connection

            # Check if we have a connected state
            if gateway.connection_state == "connected":
                logger.info("Connection is in 'connected' state")
            else:
                logger.warning(f"Connection state is: {gateway.connection_state}")
            
            logger.info("Connection test completed successfully")
            return True
        else:
            logger.error("❌ Failed to connect to IB Gateway")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {str(e)}")
        return False
    finally:
        # Disconnect
        if gateway.is_connected():
            logger.info("Disconnecting from IB Gateway...")
            gateway.disconnect()
            logger.info("Disconnected")

async def main():
    """Main entry point."""
    args = parse_args()
    success = await test_connection(args.host, args.port, args.client_id)
    return 0 if success else 1

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)