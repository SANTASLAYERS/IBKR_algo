#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple TWS position query test.
This script tests basic TWS connectivity and position retrieval.
"""

import asyncio
import logging
from ibapi.contract import Contract
from src.connection import IBKRConnection
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_position_query():
    """Test querying positions from TWS"""
    print("\n=== Testing TWS Position Query ===\n")
    
    # Create connection configuration
    config = Config()
    config.host = "172.28.64.1"  # WSL to Windows IP
    config.port = 7497           # TWS paper trading port
    config.client_id = 15        # Use a unique client ID
    
    # Create connection
    connection = IBKRConnection(config)
    
    # Dictionary to store positions
    positions = {}

    # Override the position method
    def handle_position(account, contract, position, avg_cost):
        if hasattr(contract, 'symbol'):
            symbol = contract.symbol
            positions[symbol] = {
                "account": account,
                "position": position,
                "avg_cost": avg_cost
            }
            print(f"Position: {symbol}, Size: {position}, Avg Cost: {avg_cost}")

    # Save original method
    original_position = connection.position

    # Override position method
    connection.position = handle_position
    
    try:
        # Connect to TWS
        print("Connecting to TWS...")
        connected = await connection.connect_async()
        
        if not connected:
            print("❌ Failed to connect to TWS")
            return False
            
        print("✅ Connected to TWS")
        
        # Request positions
        print("Requesting positions...")
        connection.reqPositions()
        
        # Wait for positions data
        await asyncio.sleep(3)
        
        # Print what we received
        if positions:
            print(f"\nReceived {len(positions)} positions:")
            for symbol, data in positions.items():
                print(f"  {symbol}: {data['position']} shares @ ${data['avg_cost']:.2f}")
        else:
            print("No positions found or position data not received")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False
        
    finally:
        # Restore original method and disconnect
        if connection:
            # Restore original method
            connection.position = original_position

            if connection.is_connected():
                print("Disconnecting from TWS...")
                connection.disconnect()
                print("Disconnected")

if __name__ == "__main__":
    asyncio.run(test_position_query())