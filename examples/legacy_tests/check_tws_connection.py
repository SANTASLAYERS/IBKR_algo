#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TWS Connection Test

Simple script to test if we can connect to TWS,
including verifying client ID, account details, and API handshake.

Notes:
- This script has been updated to test the direct IBKRConnection implementation
- The script still includes the older tests for comparison
- For WSL users, use host=172.28.64.1, port=7497
"""

import asyncio
import logging
import sys
import socket
import time

# Import our IBKRConnection components
try:
    from src.connection import IBKRConnection
    from src.config import Config
    from src.error_handler import ErrorHandler
    HAS_IBKR_CONNECTION = True
except ImportError:
    HAS_IBKR_CONNECTION = False
    logging.warning("Failed to import IBKRConnection. Will only run basic tests.")

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tws_connection_test')

def test_basic_socket():
    """Test basic socket connection to TWS"""
    logger.info("Testing basic socket connection to TWS")
    
    # Windows host IP when connecting from WSL
    host = "172.28.64.1"
    port = 7497  # Paper trading port
    
    try:
        # Create socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        
        # Try to connect
        logger.info(f"Connecting to {host}:{port}...")
        result = s.connect_ex((host, port))
        
        if result == 0:
            logger.info("✅ Socket connection successful")
            # Successfully connected, now try to send/receive a few bytes
            try:
                # A very simple message that would be the start of an IBAPI handshake
                test_msg = b"API\0"
                logger.info(f"Sending {len(test_msg)} test bytes")
                s.sendall(test_msg)
                
                # Try to receive response
                logger.info("Waiting for response...")
                response = s.recv(128)
                logger.info(f"Received {len(response)} bytes: {response}")
                
                return True
            except socket.error as se:
                logger.error(f"Socket send/receive error: {se}")
        else:
            logger.error(f"❌ Socket connection failed with error code: {result}")
            
        return False
        
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return False
        
    finally:
        try:
            s.close()
        except:
            pass

def test_ping():
    """Test if we can ping the Windows host"""
    host = "172.28.64.1"
    logger.info(f"Testing ICMP ping to {host}")
    
    try:
        # Using socket instead of system ping to avoid shell dependencies
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        s.settimeout(1)
        
        # Send a simple ping packet
        s.sendto(b'', (host, 0))
        
        # Wait for response
        data, addr = s.recvfrom(1024)
        logger.info(f"✅ Ping response received from {addr}")
        return True
    except Exception as e:
        logger.info(f"❌ Ping failed: {e}")
        return False
    finally:
        try:
            s.close()
        except:
            pass

def test_ib_insync():
    """Test connection using ib_insync"""
    try:
        from ib_insync import IB, util
        util.logToConsole(logging.INFO)
        
        host = "172.28.64.1"
        port = 7497
        client_id = 1
        
        logger.info(f"Testing ib_insync connection to {host}:{port} with client ID {client_id}")
        
        # No direct way to set connect timeout in newer versions of ib_insync
        # We'll rely on the default timeout
        
        # Create IB instance
        ib = IB()
        
        try:
            # Try to connect
            logger.info("Connecting...")
            ib.connect(host, port, clientId=client_id, readonly=True)
            
            # Check if connected
            if ib.isConnected():
                logger.info("✅ Successfully connected via ib_insync")
                
                # Get account info for verification
                if ib.managedAccounts():
                    logger.info(f"Managed accounts: {ib.managedAccounts()}")
                
                # Get next valid order ID
                next_id = ib.client.getReqId()
                logger.info(f"Next request ID: {next_id}")
                
                time.sleep(1)  # Allow time for messages to process
                return True
            else:
                logger.error("❌ ib_insync connection failed")
                return False
                
        except Exception as e:
            logger.error(f"ib_insync connection error: {e}")
            return False
            
        finally:
            # Disconnect
            if ib.isConnected():
                logger.info("Disconnecting...")
                ib.disconnect()
                
    except ImportError:
        logger.error("ib_insync not installed. Run: pip install ib_insync")
        return False

async def test_ibkr_connection():
    """Test connection using our IBKRConnection implementation"""
    if not HAS_IBKR_CONNECTION:
        logger.error("❌ Cannot run IBKRConnection test due to import failure")
        return False

    logger.info("Testing connection using IBKRConnection")

    # Windows host IP when connecting from WSL
    host = "172.28.64.1"
    port = 7497  # Paper trading port
    client_id = 999  # Unique for testing

    try:
        # Create configuration
        config = Config(
            host=host,
            port=port,
            client_id=client_id,
            heartbeat_timeout=10.0,
            reconnect_delay=1.0,
            max_reconnect_attempts=1
        )

        # Create connection
        error_handler = ErrorHandler()
        connection = IBKRConnection(config, error_handler)

        # Try to connect
        logger.info(f"Connecting to {host}:{port} with client ID {client_id}...")
        connected = await connection.connect_async()

        if not connected:
            logger.error("❌ IBKRConnection failed to connect")
            return False

        logger.info("✅ Successfully connected via IBKRConnection")

        # Wait a bit for initialization
        await asyncio.sleep(2)

        # Request server time to test communication
        logger.info("Requesting current time...")
        connection.req_current_time()

        # Wait a bit more
        await asyncio.sleep(2)

        # Check account ID
        if connection.account_id:
            logger.info(f"Account received: {connection.account_id}")
        else:
            logger.warning("No account ID received")

        return True

    except Exception as e:
        logger.error(f"IBKRConnection error: {e}")
        return False
    finally:
        try:
            # Disconnect
            logger.info("Disconnecting...")
            connection.disconnect()
        except:
            pass

async def async_main():
    """Run all async connection tests"""
    # Test our IBKRConnection implementation
    ibkr_result = await test_ibkr_connection()
    return ibkr_result

def main():
    """Run all connection tests"""
    logger.info("=== Starting TWS connection tests ===")

    # Test socket connection
    socket_result = test_basic_socket()

    # Test ping (likely to fail due to Windows firewall)
    ping_result = test_ping()

    # Test ib_insync connection
    ib_insync_result = test_ib_insync()

    # Test our IBKRConnection (async)
    ibkr_connection_result = False
    if HAS_IBKR_CONNECTION:
        try:
            ibkr_connection_result = asyncio.run(async_main())
        except Exception as e:
            logger.error(f"Error running async tests: {e}")

    # Summarize results
    logger.info("\n=== Connection Test Results ===")
    logger.info(f"Basic socket test: {'✅ PASS' if socket_result else '❌ FAIL'}")
    logger.info(f"Ping test: {'✅ PASS' if ping_result else '❌ FAIL'} (Expected to fail if ICMP blocked)")
    logger.info(f"ib_insync test: {'✅ PASS' if ib_insync_result else '❌ FAIL'}")
    logger.info(f"IBKRConnection test: {'✅ PASS' if ibkr_connection_result else '❌ FAIL'}")

    # Overall success - at least one connection method should work
    success = socket_result or ib_insync_result or ibkr_connection_result
    logger.info(f"\nOverall connection status: {'✅ PASS' if success else '❌ FAIL'}")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)