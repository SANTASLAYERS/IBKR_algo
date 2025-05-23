#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for IBKR Gateway reconnection capability.
This script tests the automatic reconnection functionality of our custom gateway implementation.

Usage:
    python test_reconnection.py --host HOST --port PORT

Example:
    python test_reconnection.py --host 172.28.64.1 --port 4002
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import List

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
    parser = argparse.ArgumentParser(description='Test IB Gateway reconnection')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help='Gateway hostname or IP')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Gateway port')
    parser.add_argument('--client-id', type=int, dest='client_id', default=DEFAULT_CLIENT_ID, help='Client ID')
    return parser.parse_args()

async def test_reconnection(host, port, client_id):
    """Test reconnection to IB Gateway."""
    logger.info(f"Testing reconnection to {host}:{port} with client ID {client_id}")
    
    # Track connection events for validation
    connection_sequence: List[str] = []
    
    # Define connection status callbacks
    def on_connected():
        logger.info("✓ Connection callback: Connected to IB Gateway")
        connection_sequence.append("connected")
    
    def on_disconnected():
        logger.info("✗ Connection callback: Disconnected from IB Gateway")
        connection_sequence.append("disconnected")
    
    # Create gateway configuration with short timeouts for testing
    config = IBGatewayConfig(
        host=host,
        port=port,
        client_id=client_id,
        trading_mode="paper" if port == 4002 else "live",
        heartbeat_timeout=5.0,     # Short timeout for testing
        heartbeat_interval=2.0,    # Short interval for testing
        reconnect_delay=1.0,       # Quick reconnection for testing
        max_reconnect_attempts=3
    )
    
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create gateway instance
    gateway = IBGateway(config, error_handler)
    
    # Register callbacks
    gateway.register_connected_callback(on_connected)
    gateway.register_disconnected_callback(on_disconnected)
    
    try:
        # Connect to IB Gateway
        logger.info(f"Establishing initial connection to {host}:{port}...")
        connected = await gateway.connect_gateway()
        
        # Verify initial connection
        if not connected or not gateway.is_connected():
            logger.error("❌ Failed to establish initial connection to IB Gateway")
            return False
            
        logger.info("✅ Successfully connected to IB Gateway!")
        
        # Request heartbeat to ensure connection is stable
        gateway.reqHeartbeat()
        
        # Wait a bit to ensure connection is stable
        await asyncio.sleep(2)
        
        # Verify we have the initial "connected" event
        if connection_sequence != ["connected"]:
            logger.error(f"❌ Expected initial connection event, but got: {connection_sequence}")
            return False
            
        # Simulate a connection loss by forcing a disconnect
        logger.info("🔌 Simulating connection loss...")
        gateway.connectionClosed()  # Should trigger reconnection process
        
        # Wait a short time for disconnection to register
        await asyncio.sleep(1)
        
        # Verify we got disconnection event
        if connection_sequence != ["connected", "disconnected"]:
            logger.error(f"❌ Did not detect disconnection event. Events: {connection_sequence}")
            return False
            
        logger.info("⏱️ Waiting for automatic reconnection...")
        
        # Wait and periodically check reconnection status
        reconnection_timeout = 15  # seconds
        start_time = time.time()
        reconnected = False
        
        while time.time() - start_time < reconnection_timeout and not reconnected:
            await asyncio.sleep(1)
            
            logger.info(f"Current connection state: {gateway.connection_state}")
            logger.info(f"Current events: {connection_sequence}")
            
            # Check for successful reconnection pattern 
            # (connected → disconnected → connected)
            if (len(connection_sequence) >= 3 and 
                connection_sequence[0] == "connected" and
                connection_sequence[1] == "disconnected" and
                connection_sequence[2] == "connected" and
                gateway.is_connected()):
                
                reconnected = True
                break
        
        # Final verification
        if reconnected:
            logger.info("✅ Reconnection test PASSED! Connection recovered automatically.")
            logger.info(f"Connection events: {connection_sequence}")
            return True
        else:
            logger.error("❌ Reconnection test FAILED! Connection did not recover in time.")
            logger.info(f"Connection events: {connection_sequence}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test error: {str(e)}")
        return False
    finally:
        # Clean up
        if gateway.is_connected():
            logger.info("Disconnecting from IB Gateway...")
            gateway.disconnect()
            logger.info("Disconnected")
        
        # Log final event sequence
        logger.info(f"Final connection events: {', '.join(connection_sequence)}")

async def main():
    """Main entry point."""
    args = parse_args()
    success = await test_reconnection(args.host, args.port, args.client_id)
    return 0 if success else 1

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)