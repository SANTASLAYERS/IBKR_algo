#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Direct TWS connection test without threading.
"""

import logging
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

logger = logging.getLogger("direct_tws_test")


class DirectTWS(EWrapper, EClient):
    """Direct TWS connection without threading."""
    
    def __init__(self):
        EClient.__init__(self, self)
        EWrapper.__init__(self)
        self.connected = False
        self.next_order_id = None
        self.errors = []
    
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


def test_direct_connection():
    """Test direct connection without threading."""
    logger.info("=== Direct TWS Connection Test ===")
    
    tws = DirectTWS()
    
    host = "127.0.0.1"
    port = 7497
    client_id = 888
    
    logger.info(f"Attempting direct connection to {host}:{port} with client ID {client_id}")
    
    try:
        # Try direct connection
        logger.info("Calling tws.connect()...")
        tws.connect(host, port, client_id)
        logger.info(f"Connect call completed. isConnected(): {tws.isConnected()}")
        
        if tws.isConnected():
            logger.info("✅ Connection established")
            
            # Try to process a few messages
            logger.info("Processing messages...")
            for i in range(10):
                logger.info(f"Message loop iteration {i}")
                tws.checkMessages()
                if tws.connected:
                    logger.info("Received nextValidId - connection is ready!")
                    break
            
            logger.info(f"Final state - connected: {tws.connected}, next_order_id: {tws.next_order_id}")
            logger.info(f"Errors: {tws.errors}")
            
        else:
            logger.error("❌ Connection failed")
            logger.error(f"Errors: {tws.errors}")
    
    except Exception as e:
        logger.error(f"Exception during connection: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if tws.isConnected():
            logger.info("Disconnecting...")
            tws.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_direct_connection() 