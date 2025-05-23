#!/usr/bin/env python3
"""
Simplified test script for IB Gateway connection using direct IB API with threading.
"""

import sys
import threading
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

class IBSimpleClient(EWrapper, EClient):
    """Simple client for testing IB Gateway connection."""
    
    def __init__(self):
        EClient.__init__(self, self)
        self.nextValidOrderId = None
        self.connected = False
    
    def nextValidId(self, orderId):
        print(f"✅ Connected to IB Gateway! Order ID: {orderId}")
        self.nextValidOrderId = orderId
        self.connected = True
    
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        # Skip non-critical status messages
        if errorCode in [2104, 2106, 2108, 2158, 2107]:
            print(f"Status: {errorString}")
            return
            
        print(f"Error {errorCode}: {errorString}")
    
    def currentTime(self, timestamp):
        print(f"Server time: {time.ctime(timestamp)}")

def run_client(client):
    """Run the client in a thread."""
    client.run()

def test_connection():
    """Test connection to IB Gateway."""
    print("\n=== Testing IB Gateway Connection ===\n")
    
    # Create client
    client = IBSimpleClient()
    
    # Connection parameters
    host = "172.28.64.1"  # WSL to Windows IP
    port = 4002           # Paper trading port
    client_id = 10
    
    try:
        # Connect
        print(f"Connecting to {host}:{port}...")
        client.connect(host, port, client_id)
        
        # Start client thread
        thread = threading.Thread(target=run_client, args=(client,))
        thread.daemon = True
        thread.start()
        
        # Wait for connection confirmation (short timeout)
        print("Waiting for connection confirmation...")
        for i in range(3):  # Only wait 3 seconds
            if client.connected:
                break
            time.sleep(1)
            print(".", end="", flush=True)
        print()
        
        if not client.connected:
            print("❌ Connection not confirmed!")
            return False
            
        # Request current time
        print("Requesting server time...")
        client.reqCurrentTime()
        
        # Wait briefly
        time.sleep(1)
        
        print("Connection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
        
    finally:
        print("Disconnecting...")
        client.disconnect()
        print("Test completed")

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)