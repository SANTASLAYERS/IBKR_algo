#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple TWS Test using the approach from the solution

This follows the recommended approach using ib_insync with a fixed client ID
for reliable connection to TWS from WSL.
"""

from ib_insync import IB, Stock, MarketOrder, util
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('simple_tws_test')

# Enable ib_insync logging
util.logToConsole()

def main():
    """Main function to connect to TWS and check account information"""
    logger.info("Starting simple TWS test")
    
    # Windows host IP when connecting from WSL
    host = "172.28.64.1"
    port = 7497  # TWS paper trading port
    client_id = 1  # Fixed client ID
    
    # Create IB instance
    ib = IB()
    
    try:
        # Connect to TWS
        logger.info(f"Connecting to TWS at {host}:{port} with client ID {client_id}")
        ib.connect(host, port, clientId=client_id)
        
        # Check connection
        if ib.isConnected():
            logger.info("✅ Successfully connected to TWS")
            
            # Get account information
            accounts = ib.managedAccounts()
            logger.info(f"Managed accounts: {accounts}")
            
            # Get next valid order ID
            next_id = ib.client.getReqId()
            logger.info(f"Next request ID: {next_id}")
            
            # Check positions
            positions = ib.positions()
            logger.info(f"Current positions: {len(positions)}")
            for pos in positions:
                logger.info(f"Position: {pos.contract.symbol} - {pos.position} shares")
            
            # Create contract for AAPL (if we want to place an order)
            aapl = Stock('AAPL', 'SMART', 'USD')
            
            # Request market data to check connectivity
            logger.info("Requesting AAPL market data...")
            ib.reqMktData(aapl)
            ib.sleep(2)  # Wait for some data to arrive
            
            logger.info("Test completed successfully")
            return True
        else:
            logger.error("❌ Failed to connect to TWS")
            return False
            
    except Exception as e:
        logger.error(f"Error in TWS test: {e}")
        return False
        
    finally:
        # Disconnect when done
        if ib and ib.isConnected():
            logger.info("Disconnecting from TWS")
            ib.disconnect()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)