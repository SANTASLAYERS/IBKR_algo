#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple TWS connection test for debugging.
"""

import time
import threading
import logging
import socket
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

logger = logging.getLogger("simple_tws_test")


class SimpleTWS(EWrapper, EClient):
    """Very simple TWS connection for debugging."""
    
    def __init__(self):
        EClient.__init__(self, self)
        EWrapper.__init__(self)
        self.connected = False
        self.next_order_id = None
        self.errors = []
        self.connection_started = False
    
    def connectAck(self):
        logger.info("✅ Connection acknowledged")
        self.startApi()
    
    def nextValidId(self, orderId: int):
        logger.info(f"✅ Received next valid order ID: {orderId}")
        self.next_order_id = orderId
        self.connected = True
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        error_msg = f"Error {errorCode}: {errorString} (reqId: {reqId})"
        logger.error(error_msg)
        self.errors.append((reqId, errorCode, errorString))
    
    def managedAccounts(self, accountsList: str):
        logger.info(f"✅ Managed accounts: {accountsList}")
    
    def currentTime(self, time_val: int):
        logger.info(f"✅ Current time: {time_val}")


def test_socket_connection():
    """Test basic socket connection first."""
    host = "127.0.0.1"
    port = 7497
    
    logger.info(f"Testing socket connection to {host}:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.info("✅ Socket connection successful")
            return True
        else:
            logger.error(f"❌ Socket connection failed with code: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Socket connection error: {e}")
        return False


def test_simple_tws_connection():
    """Test simple TWS connection."""
    logger.info("=== Simple TWS Connection Test ===")
    
    # First test socket connection
    if not test_socket_connection():
        logger.error("Socket connection failed - TWS may not be running")
        return False
    
    # Create connection
    tws = SimpleTWS()
    
    # Connect
    host = "127.0.0.1"
    port = 7497
    client_id = 999  # Use different client ID to avoid conflicts
    
    logger.info(f"Connecting to TWS at {host}:{port} with client ID {client_id}")
    
    connection_exception = None
    
    try:
        # Start connection in thread
        def run_connection():
            nonlocal connection_exception
            try:
                logger.info("Starting IBAPI connection...")
                tws.connect(host, port, client_id)
                tws.connection_started = True
                logger.info("IBAPI connection started, entering message loop...")
                tws.run()
                logger.info("Message loop ended")
            except Exception as e:
                connection_exception = e
                logger.error(f"Connection error: {e}")
        
        thread = threading.Thread(target=run_connection)
        thread.daemon = True
        thread.start()
        
        # Wait for connection
        timeout = 10
        start_time = time.time()
        
        logger.info("Waiting for connection...")
        while not tws.connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)
            if connection_exception:
                logger.error(f"Connection thread exception: {connection_exception}")
                break
        
        if tws.connected:
            logger.info("✅ Successfully connected!")
            
            # Test basic functionality
            logger.info("Testing reqCurrentTime...")
            tws.reqCurrentTime()
            time.sleep(1)
            
            logger.info("Testing reqManagedAccts...")
            tws.reqManagedAccts()
            time.sleep(1)
            
            logger.info(f"Next order ID: {tws.next_order_id}")
            logger.info(f"Errors: {tws.errors}")
            return True
            
        else:
            logger.error("❌ Failed to connect within timeout")
            logger.error(f"Connection started: {tws.connection_started}")
            logger.error(f"isConnected(): {tws.isConnected()}")
            logger.error(f"Errors: {tws.errors}")
            if connection_exception:
                logger.error(f"Exception: {connection_exception}")
            return False
        
    finally:
        if tws.isConnected():
            logger.info("Disconnecting...")
            tws.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    success = test_simple_tws_connection()
    if success:
        logger.info("🎉 Connection test PASSED!")
    else:
        logger.error("💥 Connection test FAILED!") 