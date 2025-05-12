#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct test script for WSL to Windows IB Gateway connection.
This script bypasses the pytest fixture system to directly test the connection.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import IBKR components
from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler
from ibapi.contract import Contract
from ibapi.order import Order

async def test_connection():
    """Test direct connection to IB Gateway from WSL."""
    print("Starting direct connection test...")
    
    # Create gateway configuration
    config = IBGatewayConfig(
        host="172.28.64.1",  # WSL to Windows host IP
        port=4002,           # Paper trading port
        client_id=10,
        account_id="DEMO",   # Replace with your account ID
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
        print(f"Connecting to IB Gateway at {config.host}:{config.port}...")
        connected = await gateway.connect_async()
        
        if not connected:
            print("❌ Failed to connect to IB Gateway")
            return False
            
        print("✅ Successfully connected to IB Gateway!")
        
        # Request current time to verify connection
        gateway.reqCurrentTime()
        
        # Wait for heartbeat
        await asyncio.sleep(2)
        
        # Check connection is still alive
        if not gateway.is_connected():
            print("❌ Connection was established but then lost")
            return False
        
        # Print connection status
        print(f"Gateway connection state: {gateway.connection_state}")
        
        # Create a test order
        print("\nCreating test market order...")
        
        # Define test symbols
        test_symbols = ["SPY", "IWM", "QQQ"]
        symbol = test_symbols[0]
        
        # Create a contract for testing
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Create a very small market order (1 share) to minimize cost
        iborder = Order()
        iborder.action = "BUY"
        iborder.orderType = "MKT"
        iborder.totalQuantity = 1
        iborder.transmit = True
        iborder.outsideRth = False
        
        # Add a unique client ID for tracking
        iborder.orderId = 0  # Let IB assign ID
        iborder.clientId = gateway.config.client_id
        iborder.account = gateway.account_id
        iborder.orderRef = f"test_{int(time.time())}"
        
        # Check if read-only mode is enabled
        if gateway.read_only:
            print("⚠️ Gateway is in read-only mode, skipping order submission")
        else:
            # Submit the order
            print(f"Submitting market order for {symbol}: {iborder}")
            order_id = gateway.submit_order(contract, iborder)
            
            if order_id > 0:
                print(f"✅ Order submitted successfully, ID: {order_id}")
                
                # Wait for order updates
                await asyncio.sleep(3)
                
                # Cancel the order
                print(f"Cancelling order {order_id}")
                gateway.cancel_order(order_id)
            else:
                print("❌ Order submission failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        return False
        
    finally:
        # Clean up
        if gateway.is_connected():
            print("Disconnecting from IB Gateway...")
            gateway.disconnect()
            print("Disconnected")

if __name__ == "__main__":
    import time
    
    # Run the test
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)