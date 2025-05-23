#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Connection Management

Direct connection handling for TWS (Trader Workstation).
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Callable

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from .tws_config import TWSConfig
from .logger import get_logger

logger = get_logger(__name__)


class TWSConnection(EWrapper, EClient):
    """
    TWS connection handler that provides direct connection to TWS.
    
    This class handles the connection lifecycle, basic API communication,
    and provides a foundation for trading operations with TWS.
    """

    def __init__(self, config: TWSConfig):
        """
        Initialize TWS connection.
        
        Args:
            config: TWS configuration settings
        """
        EClient.__init__(self, self)
        EWrapper.__init__(self)
        
        self.config = config
        self._connected = False
        self._connection_thread: Optional[threading.Thread] = None
        self._next_order_id: Optional[int] = None
        self._start_time: Optional[float] = None
        
        # Connection state callbacks
        self._on_connected: Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
    
    def set_callbacks(self, 
                     on_connected: Optional[Callable] = None,
                     on_disconnected: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """
        Set connection event callbacks.
        
        Args:
            on_connected: Called when connection is established
            on_disconnected: Called when connection is lost
            on_error: Called when an error occurs
        """
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_error = on_error
    
    async def connect(self) -> bool:
        """
        Connect to TWS asynchronously.
        
        Returns:
            bool: True if connection was successful
        """
        if self._connected:
            logger.warning("Already connected to TWS")
            return True
            
        logger.info(f"Connecting to TWS at {self.config.host}:{self.config.port}")
        
        try:
            # Reset connection state
            self._connected = False
            self._start_time = time.time()
            
            # Start connection in separate thread
            self._connection_thread = threading.Thread(target=self._run_connection)
            self._connection_thread.daemon = True
            self._connection_thread.start()
            
            # Wait for connection with timeout
            timeout = self.config.connection_timeout
            start_time = time.time()
            
            while not self._connected and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
            
            if self._connected:
                logger.info("Successfully connected to TWS")
                return True
            else:
                logger.error("Failed to connect to TWS within timeout")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to TWS: {e}")
            return False
    
    def _run_connection(self):
        """Run the connection in a separate thread."""
        try:
            # Connect to TWS
            logger.debug(f"Starting connection to {self.config.host}:{self.config.port}")
            super().connect(self.config.host, self.config.port, self.config.client_id)
            
            # Start the message loop - this will block until disconnected
            self.run()
            
        except Exception as e:
            logger.error(f"Connection thread error: {e}")
        finally:
            self._connected = False
            if self._on_disconnected:
                try:
                    self._on_disconnected()
                except Exception as e:
                    logger.error(f"Error in disconnected callback: {e}")
    
    def disconnect(self):
        """Disconnect from TWS."""
        if self._connected:
            logger.info("Disconnecting from TWS")
            self._connected = False
            super().disconnect()
    
    def is_connected(self) -> bool:
        """
        Check if connected to TWS.
        
        Returns:
            bool: True if connected
        """
        return self._connected and self.isConnected()
    
    def get_next_order_id(self) -> Optional[int]:
        """
        Get the next valid order ID.
        
        Returns:
            Optional[int]: Next order ID if available
        """
        return self._next_order_id
    
    # EWrapper callback implementations
    def connectAck(self):
        """Called when connection is acknowledged."""
        logger.debug("Connection acknowledged by TWS")
        # Start the API
        self.startApi()
    
    def nextValidId(self, orderId: int):
        """Called when TWS sends the next valid order ID."""
        logger.debug(f"Next valid order ID: {orderId}")
        self._next_order_id = orderId
        
        # Mark as connected when we receive the first valid ID
        if not self._connected:
            self._connected = True
            logger.info("TWS connection established")
            if self._on_connected:
                try:
                    self._on_connected()
                except Exception as e:
                    logger.error(f"Error in connected callback: {e}")
    
    def connectionClosed(self):
        """Called when connection is closed."""
        logger.info("Connection to TWS closed")
        self._connected = False
        if self._on_disconnected:
            try:
                self._on_disconnected()
            except Exception as e:
                logger.error(f"Error in disconnected callback: {e}")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors from TWS."""
        logger.error(f"TWS Error {errorCode}: {errorString} (reqId: {reqId})")
        
        # Handle connection-related errors
        if errorCode in [502, 503, 504]:
            logger.error("TWS connection error - check if TWS is running and API is enabled")
            self._connected = False
        elif errorCode == 2104:
            # Market data farm connection is OK - this is normal
            logger.debug("Market data farm connection is OK")
            return
        elif errorCode == 2106:
            # Historical data farm connection is OK - this is normal
            logger.debug("Historical data farm connection is OK")
            return
        
        if self._on_error:
            try:
                self._on_error(reqId, errorCode, errorString)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def managedAccounts(self, accountsList: str):
        """Called when TWS sends the list of managed accounts."""
        logger.info(f"Managed accounts: {accountsList}")
    
    def currentTime(self, time: int):
        """Called when TWS sends current time."""
        logger.debug(f"TWS current time: {time}")
    
    # Basic API methods
    def request_current_time(self):
        """Request current time from TWS."""
        if self.is_connected():
            self.reqCurrentTime()
    
    def request_managed_accounts(self):
        """Request list of managed accounts."""
        if self.is_connected():
            self.reqManagedAccts()
    
    def request_next_order_id(self, num_ids: int = 1):
        """Request next valid order ID."""
        if self.is_connected():
            self.reqIds(num_ids) 