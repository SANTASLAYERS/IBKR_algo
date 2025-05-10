#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import asyncio
import os
import signal
import sys
import time
from typing import Optional

from ibapi.contract import Contract

from src.connection import IBKRConnection
from src.event_loop import IBKREventLoop
from src.error_handler import ErrorHandler
from src.config import Config, create_default_config
from src.logger import get_logger, configure_logging_from_config

logger = get_logger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='IBKR Connection Example')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--host', type=str, help='TWS/Gateway hostname or IP')
    parser.add_argument('--port', type=int, help='TWS/Gateway port')
    parser.add_argument('--client-id', type=int, help='Client ID')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    parser.add_argument('--log-file', type=str, help='Log file path')
    return parser.parse_args()

def load_config(args) -> Config:
    """Load configuration from file and command line arguments."""
    # Load from file if provided
    if args.config and os.path.exists(args.config):
        config = Config.from_file(args.config)
    else:
        config = create_default_config()
    
    # Override with command line arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.client_id:
        config.client_id = args.client_id
    if args.log_level:
        config.log_level = args.log_level
    if args.log_file:
        config.log_file = args.log_file
    
    return config

def create_sample_contract() -> Contract:
    """Create a sample contract for testing."""
    contract = Contract()
    contract.symbol = "AAPL"
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract

async def run_example(config: Config):
    """Run the example application."""
    # Set up the event loop
    event_loop = IBKREventLoop()
    event_loop.start()
    
    # Set up the error handler
    error_handler = ErrorHandler()
    
    # Set up the connection
    connection = IBKRConnection(config, error_handler)
    
    # Add message processor to event loop
    event_loop.add_message_processor(connection.run)
    
    # Register callbacks
    connection.register_connected_callback(lambda: logger.info("Connection established callback triggered"))
    connection.register_disconnected_callback(lambda: logger.info("Connection lost callback triggered"))
    
    # Register error handler callbacks
    error_handler.register_callback(
        lambda error: logger.warning(f"Connection error: {error}"),
        category="connection"
    )
    
    # Connect to TWS/Gateway
    logger.info(f"Connecting to IBKR at {config.host}:{config.port} (client ID: {config.client_id})")
    connected = await connection.connect_async()
    
    if not connected:
        logger.error("Failed to connect to IBKR")
        event_loop.stop()
        return
    
    logger.info("Connected to IBKR")
    
    try:
        # Request account updates
        connection.reqAccountUpdates(True, "")
        
        # Request market data for sample contract
        contract = create_sample_contract()
        connection.reqMktData(1, contract, "", False, False, [])
        
        # Keep the program running until interrupted
        while connection.is_connected():
            # Request heartbeat every 5 seconds
            connection.reqHeartbeat()
            await asyncio.sleep(5)
            
    except asyncio.CancelledError:
        logger.info("Example cancelled")
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
    finally:
        # Cleanup
        if connection.is_connected():
            logger.info("Disconnecting from IBKR")
            connection.disconnect()
        
        # Stop the event loop
        logger.info("Stopping event loop")
        event_loop.stop()

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration
    config = load_config(args)
    
    # Configure logging
    configure_logging_from_config(config)
    
    logger.info(f"Starting IBKR connection example (v0.1.0)")
    logger.info(f"Using configuration: {config}")
    
    # Set up asyncio event loop
    loop = asyncio.get_event_loop()
    
    # Set up signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(loop)))
    
    try:
        # Run the example
        loop.run_until_complete(run_example(config))
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
    finally:
        loop.close()
        logger.info("Example completed")

async def shutdown(loop):
    """Shutdown the asyncio event loop gracefully."""
    logger.info("Shutdown signal received, closing tasks")
    
    # Get all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    # Cancel all tasks
    for task in tasks:
        task.cancel()
    
    # Wait for all tasks to complete with a timeout
    if tasks:
        await asyncio.wait(tasks, timeout=5)
    
    # Stop the event loop
    loop.stop()

if __name__ == "__main__":
    main()