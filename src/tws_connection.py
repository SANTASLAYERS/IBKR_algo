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
        self._connection_ack_received = False
        self._api_started = False
        self._connection_thread: Optional[threading.Thread] = None
        self._next_order_id: Optional[int] = None
        self._start_time: Optional[float] = None
        self._request_id_counter = 1000  # Start from 1000 to avoid conflicts
        
        # Initialize minute bar manager for historical data
        from src.minute_data.manager import MinuteBarManager
        self.minute_bar_manager = MinuteBarManager(gateway=self)
        
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
        
        # Reset state
        self._connected = False
        self._connection_ack_received = False
        self._api_started = False
        self._next_order_id = None
        self._start_time = time.time()
        
        # Simple connection event (like working MinimalTWS and direct test)
        connection_event = threading.Event()
        
        # Simple callback to detect connection success
        original_nextValidId = self.nextValidId
        def signal_connection_success(orderId: int):
            """Signal that connection is successful."""
            original_nextValidId(orderId)  # Call original method
            connection_event.set()
        
        # Temporarily override nextValidId (like working test)
        self.nextValidId = signal_connection_success
        
        try:
            # Use the EXACT working pattern from direct test
            def run_connection():
                try:
                    logger.info(f"Connection thread: Connecting to {self.config.host}:{self.config.port} (client ID: {self.config.client_id})")
                    
                    # Direct call to base IBAPI (EXACT copy of working approach)
                    from ibapi.client import EClient
                    EClient.connect(self, self.config.host, self.config.port, self.config.client_id)
                    logger.info("Connection thread: Socket connected, starting message loop")
                    
                    # Start message loop (EXACT copy of working approach)  
                    EClient.run(self)
                    logger.info("Connection thread: Message loop ended")
                    
                except Exception as e:
                    logger.error(f"Connection thread: Error - {e}")
            
            # Start connection thread (EXACT working pattern)
            self._connection_thread = threading.Thread(target=run_connection, daemon=True)
            self._connection_thread.start()
            
            # Simple async wait (EXACT copy of working approach)
            loop = asyncio.get_event_loop()
            timeout = self.config.connection_timeout
            
            success = await loop.run_in_executor(
                None, 
                lambda: connection_event.wait(timeout)
            )
            
            if success and self._connected:
                logger.info("✅ Successfully connected to TWS")
                return True
            else:
                logger.error("❌ Connection failed or timed out")
                logger.error(f"Connected: {self._connected}, Next ID: {self._next_order_id}")
                self._force_cleanup()
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self._force_cleanup()
            return False
        finally:
            # Restore original callback
            self.nextValidId = original_nextValidId
    
    def _force_cleanup(self):
        """Force cleanup of connection resources."""
        logger.info("Forcing connection cleanup")
        self._connected = False
        self._connection_ack_received = False
        self._api_started = False
        
        try:
            super().disconnect()
        except Exception as e:
            logger.debug(f"Error during forced disconnect: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from TWS safely without joining threads."""
        if not self._connected:
            logger.warning("Not connected to TWS")
            return
            
        logger.info("Disconnecting from TWS")
        
        try:
            # Reset connection state first
            self._connected = False
            self._connection_ack_received = False
            self._api_started = False
            
            # Call IBAPI disconnect (this triggers connectionClosed)
            EClient.disconnect(self)
            
            # DON'T JOIN THE THREAD - let it clean up naturally
            # The daemon thread will exit when the main process exits
            
            logger.info("✅ Disconnect request sent")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
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
        if self._next_order_id is None:
            return None
        
        # Return current ID and increment for next use
        current_id = self._next_order_id
        self._next_order_id += 1
        return current_id
    
    def get_next_request_id(self) -> int:
        """
        Get the next request ID for API calls.
        
        Returns:
            int: Next request ID
        """
        # Use a simple counter for request IDs
        current_id = self._request_id_counter
        self._request_id_counter += 1
        return current_id
    
    # EWrapper callback implementations
    def connectAck(self):
        """Called when connection is acknowledged."""
        logger.info("✅ Connection acknowledged by TWS")
        self._connection_ack_received = True
        # Start API like MinimalTWS
        self.startApi()
        self._api_started = True
    
    def nextValidId(self, orderId: int):
        """Called when TWS sends the next valid order ID."""
        logger.info(f"✅ Next valid order ID received: {orderId}")
        self._next_order_id = orderId
        
        # Mark as connected when we receive the first valid ID (like MinimalTWS)
        if not self._connected:
            self._connected = True
            logger.info("✅ TWS connection fully established")
            
            # Request more order IDs proactively
            logger.info("Requesting additional order IDs from TWS")
            self.reqIds(50)  # Request 50 order IDs upfront
            
            # Call user callback if set
            if self._on_connected:
                try:
                    self._on_connected()
                except Exception as e:
                    logger.error(f"Error in connected callback: {e}")
    
    def connectionClosed(self):
        """Called when connection is closed."""
        logger.info("⚠️ Connection to TWS closed")
        self._connected = False
        self._connection_ack_received = False
        self._api_started = False
        if self._on_disconnected:
            try:
                self._on_disconnected()
            except Exception as e:
                logger.error(f"Error in disconnected callback: {e}")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors from TWS."""
        # Handle connection-related errors
        if errorCode in [502, 503, 504]:
            logger.error(f"❌ TWS connection error {errorCode}: {errorString}")
            self._connected = False
            self._connection_ack_received = False
            self._api_started = False
        elif errorCode == 2104:
            # Market data farm connection is OK - this is normal
            logger.debug("✅ Market data farm connection is OK")
            return
        elif errorCode == 2106:
            # Historical data farm connection is OK - this is normal
            logger.debug("✅ Historical data farm connection is OK")
            return
        elif errorCode == 2158:
            # Sec-def data farm connection is OK - this is normal  
            logger.debug("✅ Sec-def data farm connection is OK")
            return
        else:
            logger.warning(f"⚠️ TWS Error {errorCode}: {errorString} (reqId: {reqId})")
        
        # Call user error callback if set
        if self._on_error:
            try:
                self._on_error(reqId, errorCode, errorString)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def managedAccounts(self, accountsList: str):
        """Called when TWS sends the list of managed accounts."""
        logger.debug(f"Managed accounts: {accountsList}")
    
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
    
    # Order-related callbacks
    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float, 
                   avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, 
                   clientId: int, whyHeld: str, mktCapPrice: float):
        """Called when order status is updated."""
        logger.info(f"Order Status Update - ID: {orderId}, Status: {status}, Filled: {filled}, Remaining: {remaining}")
        # The OrderManager will override this method to handle status updates
    
    def openOrder(self, orderId: int, contract, order, orderState):
        """Called when an order is opened."""
        logger.info(f"Open Order - ID: {orderId}, Symbol: {contract.symbol}, Action: {order.action}, Quantity: {order.totalQuantity}")
        # The OrderManager can use this for order tracking
    
    def execDetails(self, reqId: int, contract, execution):
        """Called when an order is executed."""
        logger.info(f"Execution - Order ID: {execution.orderId}, Symbol: {contract.symbol}, Shares: {execution.shares}, Price: {execution.price}")
        # The OrderManager will override this method to handle executions 