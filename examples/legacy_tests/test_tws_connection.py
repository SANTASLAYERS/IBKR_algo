#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple script to test TWS connection from WSL.

This script connects to TWS running on Windows host from WSL and 
verifies that basic functionality works.
"""

import asyncio
import logging
import sys
from datetime import datetime

from src.connection import IBKRConnection
from src.config import Config
from src.error_handler import ErrorHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_tws_connection")


async def test_connection():
    """Test connection to TWS from WSL."""
    # Check if we're in WSL
    is_wsl = False
    try:
        with open('/proc/sys/fs/binfmt_misc/WSLInterop', 'r'):
            is_wsl = True
    except:
        pass
    
    # Default host - use WSL-to-Windows IP if in WSL environment
    host = "172.28.64.1" if is_wsl else "127.0.0.1"
    port = 7497  # TWS paper trading port
    
    logger.info(f"Testing connection to TWS at {host}:{port}")
    
    # Create configuration
    config = Config(
        host=host,
        port=port,
        client_id=1,  # Use fixed client ID
        heartbeat_timeout=10.0,
        heartbeat_interval=5.0
    )
    
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create connection
    connection = IBKRConnection(config, error_handler)
    
    try:
        # Connect to TWS
        logger.info("Connecting to TWS...")
        connected = await connection.connect_async()
        
        if not connected:
            logger.error("Failed to connect to TWS")
            return False
            
        logger.info("Successfully connected to TWS!")
        
        # Request current time as a basic test
        logger.info("Requesting current time...")
        
        # Set up a callback to receive the time
        time_received = False
        server_time = None
        
        def currentTime_callback(time_value):
            nonlocal time_received, server_time
            time_received = True
            server_time = datetime.fromtimestamp(time_value)
            logger.info(f"Received server time: {server_time}")
        
        # Store original callback and set our callback
        original_callback = connection.currentTime
        connection.currentTime = currentTime_callback
        
        # Request current time
        connection.reqCurrentTime()
        
        # Wait for response with timeout
        timeout = 5  # 5 seconds
        start_time = datetime.now()
        
        while not time_received and (datetime.now() - start_time).total_seconds() < timeout:
            await asyncio.sleep(0.1)
        
        # Check if we received the time
        if time_received:
            logger.info("Connection test successful!")
            success = True
        else:
            logger.error("Did not receive server time response")
            success = False
            
        # Restore original callback
        connection.currentTime = original_callback
        
        # Return success status
        return success
        
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return False
        
    finally:
        # Disconnect even if an error occurred
        if connection.is_connected():
            logger.info("Disconnecting from TWS...")
            connection.disconnect()
            logger.info("Disconnected from TWS")


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_connection())
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)