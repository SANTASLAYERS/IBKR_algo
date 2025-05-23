#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple Direct API TWS Connection Test

This script performs a basic test to connect to TWS and retrieve positions
using the IBAPI directly (without ib_insync) for maximum reliability.

Usage:
    python3 simple_direct_test.py [--host HOST] [--port PORT] [--client-id CLIENT_ID]
"""

import logging
import sys
import threading
import time
import argparse
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simple_direct_test")

class SimpleTwsApp(EWrapper, EClient):
    """Simple application that connects to TWS using direct API."""
    
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.connection_confirmed = False
        self.positions = []
        self.connection_event = threading.Event()
        
    def nextValidId(self, orderId):
        """Called when connection is established."""
        logger.info(f"✅ Connection confirmed (next valid order ID: {orderId})")
        self.connection_confirmed = True
        self.connected = True
        self.connection_event.set()
    
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle errors from TWS."""
        # Ignore certain informational messages
        if errorCode in [2104, 2106, 2108]:
            return
            
        if errorCode == 502:
            logger.error(f"❌ Connection error: {errorString}")
            self.connected = False
        else:
            logger.error(f"Error {errorCode}: {errorString}")
    
    def connectionClosed(self):
        """Called when connection is closed."""
        logger.info("Connection to TWS closed")
        self.connected = False
        
    def position(self, account, contract, position, avgCost):
        """Handle position updates."""
        pos_info = {
            'account': account,
            'symbol': contract.symbol,
            'secType': contract.secType,
            'exchange': contract.exchange,
            'currency': contract.currency,
            'position': position,
            'avgCost': avgCost
        }
        self.positions.append(pos_info)
        logger.info(f"Position: {contract.symbol}, {position} shares @ {avgCost}")
    
    def positionEnd(self):
        """Called when all positions are received."""
        logger.info(f"✅ Position updates completed. Total positions: {len(self.positions)}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Simple Direct API TWS Connection Test")
    parser.add_argument("--host", type=str, default="172.28.64.1",
                      help="TWS hostname or IP (default: 172.28.64.1 for WSL)")
    parser.add_argument("--port", type=int, default=7497,
                      help="TWS port (default: 7497 for paper trading)")
    parser.add_argument("--client-id", type=int, default=1,
                      help="Client ID (default: 1)")
    parser.add_argument("--timeout", type=int, default=10,
                      help="Connection timeout in seconds (default: 10)")
    parser.add_argument("--wait", type=int, default=3,
                      help="Wait time for position data in seconds (default: 3)")
    return parser.parse_args()

def main():
    """Run the simple TWS direct API test."""
    # Parse command line arguments
    args = parse_args()

    app = SimpleTwsApp()

    # Connection parameters from command line arguments
    host = args.host
    port = args.port
    client_id = args.client_id

    logger.info(f"Connecting to TWS at {host}:{port} with client ID {client_id}...")
    
    try:
        # Connect to TWS
        app.connect(host, port, client_id)
        
        # Start the client thread
        client_thread = threading.Thread(target=app.run)
        client_thread.daemon = True
        client_thread.start()
        
        # Wait for connection confirmation
        connection_timeout = args.timeout
        logger.info(f"Waiting up to {connection_timeout} seconds for connection confirmation...")

        connected = app.connection_event.wait(timeout=connection_timeout)
        if not connected:
            logger.error("❌ Connection not confirmed within timeout period")
            app.disconnect()
            return False
        
        # Request positions
        logger.info("Requesting positions...")
        app.reqPositions()
        
        # Wait for positions to be received
        time.sleep(args.wait)
        
        # Display results
        if app.positions:
            logger.info("\n=== Current Positions ===")
            for pos in app.positions:
                logger.info(f"{pos['symbol']}: {pos['position']} shares @ {pos['avgCost']}")
        else:
            logger.info("No positions found in the account.")
        
        # Disconnect
        logger.info("Disconnecting from TWS...")
        app.disconnect()
        logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return False
    
    finally:
        # Ensure cleanup
        try:
            if getattr(app, 'connected', False):
                app.disconnect()
        except:
            pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)