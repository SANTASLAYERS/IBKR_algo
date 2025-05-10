#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import socket
import time
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from .heartbeat import HeartbeatMonitor
from .config import Config
from .error_handler import ErrorHandler
from .logger import get_logger

logger = get_logger(__name__)

class IBKRConnection(EWrapper, EClient):
    """
    Main connection class that handles the connection to IBKR's TWS or Gateway.
    Implements heartbeat monitoring and connection recovery.
    """
    
    def __init__(self, config: Config, error_handler: ErrorHandler = None):
        """
        Initialize the IBKR connection with configuration.
        
        Args:
            config: Configuration object with connection parameters
            error_handler: Optional custom error handler
        """
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        
        self.config = config
        self.error_handler = error_handler or ErrorHandler()
        self.heartbeat_monitor = HeartbeatMonitor(
            heartbeat_timeout=self.config.heartbeat_timeout,
            on_timeout=self._handle_heartbeat_timeout
        )
        
        self.connection_state = "disconnected"
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = self.config.max_reconnect_attempts
        self._reconnect_delay = self.config.reconnect_delay
        
        # Callbacks for connection events
        self.on_connected_callbacks: List[Callable] = []
        self.on_disconnected_callbacks: List[Callable] = []
        
    async def connect_async(self) -> bool:
        """
        Connect to TWS/Gateway asynchronously
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        logger.info(f"Connecting to {self.config.host}:{self.config.port} (clientId: {self.config.client_id})")
        
        try:
            # Use non-blocking connect
            self.connection_state = "connecting"
            loop = asyncio.get_event_loop()
            
            # Connect using EClient's connect method (modified to work with asyncio)
            # We need to capture self for the lambda to handle super() correctly
            self_copy = self
            await loop.run_in_executor(
                None,
                lambda: EClient.connect(
                    self_copy,
                    self.config.host,
                    self.config.port,
                    self.config.client_id
                )
            )
            
            # Start heartbeat monitor
            self.heartbeat_monitor.start()
            
            # Set connection state and notify callbacks
            self.connection_state = "connected"
            self._notify_connected()
            logger.info("Successfully connected to IBKR")
            
            return True
            
        except socket.error as e:
            logger.error(f"Failed to connect: {str(e)}")
            self.connection_state = "disconnected"
            return False
            
    def disconnect(self):
        """Disconnect from TWS/Gateway"""
        if self.connection_state != "disconnected":
            logger.info("Disconnecting from IBKR")
            self.heartbeat_monitor.stop()
            super().disconnect()
            self.connection_state = "disconnected"
            self._notify_disconnected()
    
    async def reconnect(self):
        """
        Attempt to reconnect with exponential backoff
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Maximum reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False
            
        self._reconnect_attempts += 1
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        
        logger.info(f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} "
                   f"in {delay} seconds")
        
        await asyncio.sleep(delay)
        return await self.connect_async()
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.connection_state == "connected" and super().isConnected()
        
    def reset_reconnect_attempts(self):
        """Reset reconnection attempts counter"""
        self._reconnect_attempts = 0
        
    def register_connected_callback(self, callback: Callable):
        """Register a callback for when connection is established"""
        self.on_connected_callbacks.append(callback)
        
    def register_disconnected_callback(self, callback: Callable):
        """Register a callback for when connection is lost"""
        self.on_disconnected_callbacks.append(callback)
    
    def _notify_connected(self):
        """Notify all connected callbacks"""
        for callback in self.on_connected_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in connected callback: {str(e)}")
                
    def _notify_disconnected(self):
        """Notify all disconnected callbacks"""
        for callback in self.on_disconnected_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in disconnected callback: {str(e)}")
    
    def _handle_heartbeat_timeout(self):
        """Handle heartbeat timeout - connection may be lost"""
        logger.warning("Heartbeat timeout detected - connection may be lost")
        self.connection_state = "reconnecting"
        self.disconnect()
        
        # Schedule reconnection in event loop
        asyncio.create_task(self._attempt_reconnection())
    
    async def _attempt_reconnection(self):
        """Attempt to reconnect after connection loss"""
        logger.info("Attempting to reconnect...")
        
        while not self.is_connected() and self._reconnect_attempts < self._max_reconnect_attempts:
            if await self.reconnect():
                logger.info("Reconnection successful")
                self.reset_reconnect_attempts()
                return True
        
        if not self.is_connected():
            logger.error("Failed to reconnect after multiple attempts")
            return False
            
        return True
            
    # EWrapper overrides for heartbeat and error handling
    def connectAck(self):
        """Called when connection is acknowledged"""
        super().connectAck()
        self.heartbeat_monitor.received_heartbeat()
        logger.debug("Connection acknowledged")
    
    def connectionClosed(self):
        """Called when connection is closed by server"""
        super().connectionClosed()
        logger.warning("Connection closed by server")
        self.connection_state = "disconnected"
        self._notify_disconnected()
        
        # Schedule reconnection
        asyncio.create_task(self._attempt_reconnection())
    
    def currentTime(self, timestamp: int):
        """Process server time message as heartbeat"""
        super().currentTime(timestamp)
        self.heartbeat_monitor.received_heartbeat()
        logger.debug(f"Received server time: {timestamp}")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors from TWS"""
        # Pass only the parameters compatible with the parent class
        super().error(reqId, errorCode, errorString)

        # Let error handler process the error
        self.error_handler.handle_error(reqId, errorCode, errorString, advancedOrderRejectJson)
        
        # Certain error codes indicate connection issues
        connection_error_codes = [1100, 1101, 1102, 1300, 2103, 2104, 2105, 2106, 2107, 2108]
        
        if errorCode in connection_error_codes:
            if errorCode == 1102:  # Reconnected - reset heartbeat
                logger.info("Reconnected to IBKR server")
                self.connection_state = "connected"
                self.heartbeat_monitor.received_heartbeat()
                self.reset_reconnect_attempts()
                self._notify_connected()
            elif errorCode in [1101, 1300]:  # Connectivity restored
                logger.info("Connectivity with IBKR server restored")
                self.connection_state = "connected"  
                self.heartbeat_monitor.received_heartbeat()
                self.reset_reconnect_attempts()
        
    def managedAccounts(self, accountsList: str):
        """Process managed accounts - indicates successful login"""
        super().managedAccounts(accountsList)
        logger.info(f"Managed accounts: {accountsList}")
        
        # Update connection state and reset heartbeat
        self.connection_state = "connected"
        self.heartbeat_monitor.received_heartbeat()
        self.reset_reconnect_attempts()
        
    def reqHeartbeat(self):
        """Request a heartbeat from server"""
        if self.is_connected():
            self.reqCurrentTime()
            logger.debug("Heartbeat requested")