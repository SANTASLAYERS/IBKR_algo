#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simplified test for connection manager.
"""

import asyncio
import logging
import sys

from src.config import Config
from src.connection import IBKRConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_direct_connections():
    """Test direct connections to TWS."""
    print("\n=== Testing Direct TWS Connections ===\n")

    # Create configs for different client IDs
    config1 = Config()
    config1.host = "172.28.64.1"   # WSL to Windows host IP
    config1.port = 7497            # TWS paper trading port
    config1.client_id = 10

    config2 = Config()
    config2.host = "172.28.64.1"
    config2.port = 7497
    config2.client_id = 11

    connections = []

    try:
        # Create first connection
        print("Creating connection 1...")
        connection1 = IBKRConnection(config1)
        connected1 = await connection1.connect_async()
        print(f"Connection 1 established: {connected1}")
        if connected1:
            connections.append(connection1)

            # Test requesting current time
            connection1.req_current_time()
            print("Current time requested (response is async and will arrive later)")

        # Create second connection with different client ID
        print("\nCreating connection 2...")
        connection2 = IBKRConnection(config2)
        connected2 = await connection2.connect_async()
        print(f"Connection 2 established: {connected2}")
        if connected2:
            connections.append(connection2)

            # Test requesting current time on second connection
            connection2.req_current_time()
            print("Current time requested on connection 2 (response is async and will arrive later)")

        # Verify we have unique connections
        print(f"\nConnections are different objects: {connection1 is not connection2}")

        # Allow some time for operations
        await asyncio.sleep(2)

    finally:
        # Clean up
        print("\nCleaning up connections...")
        for connection in connections:
            connection.disconnect()

    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_direct_connections())
    sys.exit(0 if success else 1)