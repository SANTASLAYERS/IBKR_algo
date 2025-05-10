#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable, Tuple

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.execution import Execution
from ibapi.commission_report import CommissionReport

from .connection import IBKRConnection
from .config import Config
from .error_handler import ErrorHandler
from .logger import get_logger

logger = get_logger(__name__)

class IBGatewayConfig(Config):
    """Extended configuration for IB Gateway connection."""
    
    def __init__(
        self, 
        host: str = "127.0.0.1", 
        port: int = 4002,  # Default to Gateway paper trading port
        client_id: int = 1,
        account_id: str = "",
        read_only: bool = True,
        gateway_path: str = "",
        user_id: str = "",
        password: str = "",
        trading_mode: str = "paper",  # 'paper' or 'live'
        **kwargs
    ):
        """
        Initialize Gateway-specific configuration.
        
        Args:
            host: Gateway hostname or IP
            port: Gateway port (4001 for live, 4002 for paper)
            client_id: TWS/Gateway client ID
            account_id: IB account ID
            read_only: Whether to connect in read-only mode
            gateway_path: Path to IB Gateway installation
            user_id: IB Gateway user ID (username)
            password: IB Gateway password
            trading_mode: 'paper' or 'live'
        """
        super().__init__(host=host, port=port, client_id=client_id, **kwargs)
        
        self.account_id = account_id
        self.read_only = read_only
        self.gateway_path = gateway_path
        self.user_id = user_id
        self.password = password
        self.trading_mode = trading_mode
        
        # Adjust port based on trading mode if not explicitly set
        if port == 4002 and 'port' not in kwargs:
            self.port = 4002 if trading_mode == 'paper' else 4001


class IBGateway(IBKRConnection):
    """
    Enhanced IBKR connection specifically for IB Gateway.
    Adds Gateway-specific functionality and improved market data handling.
    """

    def __init__(
        self,
        config: Union[Config, IBGatewayConfig],
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize the IB Gateway connection.

        Args:
            config: Configuration for the connection
            error_handler: Optional custom error handler
        """
        # Convert regular Config to IBGatewayConfig if needed
        if not isinstance(config, IBGatewayConfig):
            gateway_config = IBGatewayConfig(
                host=config.host,
                port=config.port,
                client_id=config.client_id,
                heartbeat_timeout=config.heartbeat_timeout,
                heartbeat_interval=config.heartbeat_interval,
                reconnect_delay=config.reconnect_delay,
                max_reconnect_attempts=config.max_reconnect_attempts
            )
            config = gateway_config

        super().__init__(config, error_handler)

        # Gateway-specific attributes
        self.config = config
        self.account_id = config.account_id
        self.read_only = config.read_only

        # Market data storage
        self._market_data: Dict[int, Dict] = {}
        self._market_data_subscribers: Dict[int, List[Callable]] = {}
        self._next_request_id = 1000  # Start IDs at 1000 to avoid conflicts

        # Contract and order tracking
        self._contracts: Dict[int, Contract] = {}
        self._orders: Dict[int, Order] = {}
        self._positions: Dict[str, Dict] = {}
        self._account_values: Dict[str, Dict] = {}

        # Gateway process management
        self._gateway_process = None
        self._gateway_path = config.gateway_path

        # Initialize MinuteBarManager for historical minute data
        from src.minute_data.manager import MinuteBarManager
        self.minute_bar_manager = MinuteBarManager(self)
        
    async def start_gateway(self) -> bool:
        """
        Start the IB Gateway process if path is provided.
        
        Returns:
            bool: True if Gateway was started or already running
        """
        if not self._gateway_path:
            logger.warning("No Gateway path provided, skipping Gateway startup")
            return False
            
        gateway_path = Path(self._gateway_path)
        if not gateway_path.exists():
            logger.error(f"Gateway path does not exist: {gateway_path}")
            return False
            
        # Check if Gateway is already running
        if await self._is_gateway_running():
            logger.info("IB Gateway is already running")
            return True
            
        logger.info(f"Starting IB Gateway from {gateway_path}")
        
        try:
            import subprocess
            
            # Determine Gateway script based on platform
            if os.name == 'nt':  # Windows
                gateway_script = gateway_path / "ibgateway.bat"
            else:  # Unix/Linux/Mac
                gateway_script = gateway_path / "ibgateway"
                
            if not gateway_script.exists():
                logger.error(f"Gateway script not found: {gateway_script}")
                return False
                
            # Prepare environment variables for auto-login
            env = os.environ.copy()
            if self.config.user_id and self.config.password:
                env["IB_USERNAME"] = self.config.user_id
                env["IB_PASSWORD"] = self.config.password
            
            # Start Gateway process (non-blocking)
            mode = "paper" if self.config.trading_mode == "paper" else "live"
            self._gateway_process = subprocess.Popen(
                [str(gateway_script), f"--mode={mode}"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for Gateway to start
            logger.info("Waiting for IB Gateway to start...")
            for _ in range(30):  # Wait up to 30 seconds
                if await self._is_gateway_running():
                    logger.info("IB Gateway started successfully")
                    return True
                await asyncio.sleep(1)
                
            logger.error("Timeout waiting for IB Gateway to start")
            return False
            
        except Exception as e:
            logger.error(f"Error starting IB Gateway: {str(e)}")
            return False
    
    async def stop_gateway(self) -> bool:
        """
        Stop the IB Gateway process if it was started by us.
        
        Returns:
            bool: True if Gateway was stopped
        """
        if not self._gateway_process:
            logger.info("No Gateway process to stop")
            return False
            
        logger.info("Stopping IB Gateway process")
        try:
            # Try to gracefully terminate
            self._gateway_process.terminate()
            
            # Wait for process to terminate
            for _ in range(5):  # Wait up to 5 seconds
                if self._gateway_process.poll() is not None:
                    logger.info("IB Gateway process terminated")
                    self._gateway_process = None
                    return True
                await asyncio.sleep(1)
                
            # Force kill if still running
            logger.warning("Gateway process not responding, force killing")
            self._gateway_process.kill()
            self._gateway_process = None
            return True
            
        except Exception as e:
            logger.error(f"Error stopping Gateway process: {str(e)}")
            return False
    
    async def _is_gateway_running(self) -> bool:
        """
        Check if the IB Gateway is running by trying to connect to its port.
        
        Returns:
            bool: True if Gateway is running
        """
        try:
            # Try to connect to the Gateway port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((self.config.host, self.config.port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def connect_gateway(self) -> bool:
        """
        Start Gateway if needed and connect to it.
        
        Returns:
            bool: True if connection was successful
        """
        # Start Gateway if path is provided
        if self._gateway_path:
            gateway_started = await self.start_gateway()
            if not gateway_started:
                logger.error("Failed to start IB Gateway")
                return False
                
        # Connect to Gateway
        connected = await self.connect_async()
        
        if connected:
            # Request account updates once connected
            if self.account_id:
                self.reqAccountUpdates(True, self.account_id)
            
            # Set read-only mode if configured
            if self.read_only:
                logger.info("Connection established in read-only mode")
        
        return connected
    
    async def disconnect_gateway(self) -> None:
        """Disconnect from Gateway and optionally stop the Gateway process."""
        # First disconnect from the API
        self.disconnect()
        
        # Then stop the Gateway process if we started it
        if self._gateway_process:
            await self.stop_gateway()
    
    def get_next_request_id(self) -> int:
        """
        Get a unique request ID for API calls.
        
        Returns:
            int: Unique ID
        """
        req_id = self._next_request_id
        self._next_request_id += 1
        return req_id
    
    def subscribe_market_data(
        self, 
        contract: Contract, 
        generic_tick_list: str = "", 
        snapshot: bool = False,
        callback: Optional[Callable] = None
    ) -> int:
        """
        Subscribe to market data for a contract.
        
        Args:
            contract: Contract to subscribe for
            generic_tick_list: Additional tick types
            snapshot: Whether to request a snapshot
            callback: Callback function when data is received
            
        Returns:
            int: Request ID for the subscription
        """
        req_id = self.get_next_request_id()
        
        # Store contract
        self._contracts[req_id] = contract
        
        # Initialize data structure
        self._market_data[req_id] = {
            "last_price": None,
            "bid_price": None,
            "ask_price": None,
            "high": None,
            "low": None,
            "volume": None,
            "last_timestamp": None,
            "halted": False,
            "contract": contract,
        }
        
        # Register callback if provided
        if callback:
            if req_id not in self._market_data_subscribers:
                self._market_data_subscribers[req_id] = []
            self._market_data_subscribers[req_id].append(callback)
        
        # Request market data
        self.reqMktData(
            req_id, 
            contract, 
            generic_tick_list, 
            snapshot, 
            False,  # regulatorySnapshot
            []  # mktDataOptions
        )
        
        logger.info(f"Subscribed to market data for {contract.symbol} (ID: {req_id})")
        return req_id
    
    def unsubscribe_market_data(self, req_id: int) -> None:
        """
        Unsubscribe from market data.
        
        Args:
            req_id: Request ID of the subscription
        """
        if req_id in self._market_data:
            contract = self._contracts.get(req_id)
            symbol = contract.symbol if contract else f"ID:{req_id}"
            
            # Cancel market data request
            self.cancelMktData(req_id)
            
            # Clean up data structures
            del self._market_data[req_id]
            if req_id in self._market_data_subscribers:
                del self._market_data_subscribers[req_id]
            if req_id in self._contracts:
                del self._contracts[req_id]
                
            logger.info(f"Unsubscribed from market data for {symbol}")
    
    def get_market_data(self, req_id: int) -> Optional[Dict]:
        """
        Get current market data for a subscription.
        
        Args:
            req_id: Request ID of the subscription
            
        Returns:
            Optional[Dict]: Market data or None if not found
        """
        return self._market_data.get(req_id)
    
    def submit_order(
        self, 
        contract: Contract, 
        order: Order
    ) -> int:
        """
        Submit an order for a contract.
        
        Args:
            contract: Contract to trade
            order: Order details
            
        Returns:
            int: Order ID
        """
        if self.read_only:
            logger.warning("Cannot submit order in read-only mode")
            return -1
            
        # Generate order ID if not provided
        if not order.orderId or order.orderId <= 0:
            order.orderId = self.get_next_request_id()
            
        # Store order and contract
        self._orders[order.orderId] = order
        self._contracts[order.orderId] = contract
        
        # Submit order
        logger.info(f"Submitting order: {order.action} {order.totalQuantity} {contract.symbol} @ {order.lmtPrice if order.orderType == 'LMT' else 'MKT'}")
        self.placeOrder(order.orderId, contract, order)
        
        return order.orderId
    
    def cancel_order(self, order_id: int) -> None:
        """
        Cancel an open order.
        
        Args:
            order_id: ID of the order to cancel
        """
        if self.read_only:
            logger.warning("Cannot cancel order in read-only mode")
            return
            
        if order_id in self._orders:
            logger.info(f"Cancelling order {order_id}")
            self.cancelOrder(order_id)
        else:
            logger.warning(f"Order ID {order_id} not found")
    
    # EWrapper overrides for market data
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib: int) -> None:
        """Process price tick data."""
        super().tickPrice(reqId, tickType, price, attrib)
        
        if reqId in self._market_data:
            data = self._market_data[reqId]
            
            # Process different tick types
            if tickType == 1:  # Bid
                data["bid_price"] = price
            elif tickType == 2:  # Ask
                data["ask_price"] = price
            elif tickType == 4:  # Last
                data["last_price"] = price
                data["last_timestamp"] = time.time()
            elif tickType == 6:  # High
                data["high"] = price
            elif tickType == 7:  # Low
                data["low"] = price
                
            # Notify subscribers
            self._notify_market_data_subscribers(reqId, data)
    
    def tickSize(self, reqId: int, tickType: int, size: int) -> None:
        """Process size tick data."""
        super().tickSize(reqId, tickType, size)
        
        if reqId in self._market_data:
            data = self._market_data[reqId]
            
            # Process different tick types
            if tickType == 8:  # Volume
                data["volume"] = size
                
            # Notify subscribers
            self._notify_market_data_subscribers(reqId, data)
    
    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Process string tick data."""
        super().tickString(reqId, tickType, value)
        
        if reqId in self._market_data:
            data = self._market_data[reqId]
            
            # Process different tick types
            if tickType == 45:  # Last timestamp
                try:
                    data["last_timestamp"] = float(value)
                except ValueError:
                    pass
                
            # Notify subscribers
            self._notify_market_data_subscribers(reqId, data)
    
    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Process generic tick data."""
        super().tickGeneric(reqId, tickType, value)
        
        if reqId in self._market_data:
            data = self._market_data[reqId]
            
            # Process different tick types
            if tickType == 23:  # Halted
                data["halted"] = value == 1
                
            # Notify subscribers
            self._notify_market_data_subscribers(reqId, data)
    
    def _notify_market_data_subscribers(self, req_id: int, data: Dict) -> None:
        """Notify subscribers of market data updates."""
        if req_id in self._market_data_subscribers:
            for callback in self._market_data_subscribers[req_id]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in market data callback: {str(e)}")
    
    # Account and position tracking
    def updateAccountValue(self, key: str, value: str, currency: str, accountName: str) -> None:
        """Process account value updates."""
        super().updateAccountValue(key, value, currency, accountName)
        
        if accountName not in self._account_values:
            self._account_values[accountName] = {}
            
        # Store account value
        currency_key = currency if currency else "BASE"
        full_key = f"{key}_{currency_key}"
        self._account_values[accountName][full_key] = value
        
        logger.debug(f"Account {accountName}: {key} = {value} {currency}")
    
    def updatePortfolio(
        self, 
        contract: Contract, 
        position: float, 
        marketPrice: float, 
        marketValue: float,
        averageCost: float, 
        unrealizedPNL: float, 
        realizedPNL: float, 
        accountName: str
    ) -> None:
        """Process portfolio/position updates."""
        super().updatePortfolio(
            contract, position, marketPrice, marketValue,
            averageCost, unrealizedPNL, realizedPNL, accountName
        )
        
        # Create unique key for the position
        symbol = contract.symbol
        sectype = contract.secType
        exchange = contract.exchange if contract.exchange != "SMART" else contract.primaryExchange
        currency = contract.currency
        position_key = f"{symbol}_{sectype}_{exchange}_{currency}"
        
        # Store position data
        if accountName not in self._positions:
            self._positions[accountName] = {}
            
        if position == 0:
            # Remove closed positions
            if position_key in self._positions[accountName]:
                del self._positions[accountName][position_key]
        else:
            # Update or add position
            self._positions[accountName][position_key] = {
                "contract": contract,
                "position": position,
                "market_price": marketPrice,
                "market_value": marketValue,
                "average_cost": averageCost,
                "unrealized_pnl": unrealizedPNL,
                "realized_pnl": realizedPNL,
            }
            
        logger.debug(f"Position update - {accountName}: {position} {symbol} @ {marketPrice}")
    
    def get_positions(self, account_id: Optional[str] = None) -> Dict:
        """
        Get current positions.
        
        Args:
            account_id: Optional account ID, defaults to all accounts
            
        Returns:
            Dict: Positions by account
        """
        if account_id:
            return {account_id: self._positions.get(account_id, {})}
        return self._positions
    
    def get_account_values(self, account_id: Optional[str] = None) -> Dict:
        """
        Get current account values.
        
        Args:
            account_id: Optional account ID, defaults to all accounts
            
        Returns:
            Dict: Account values by account
        """
        if account_id:
            return {account_id: self._account_values.get(account_id, {})}
        return self._account_values
    
    # Order status tracking
    def orderStatus(
        self, 
        orderId: int, 
        status: str, 
        filled: float,
        remaining: float, 
        avgFillPrice: float, 
        permId: int,
        parentId: int, 
        lastFillPrice: float, 
        clientId: int,
        whyHeld: str, 
        mktCapPrice: float
    ) -> None:
        """Process order status updates."""
        super().orderStatus(
            orderId, status, filled, remaining, avgFillPrice,
            permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice
        )
        
        if orderId in self._orders:
            # Update order status
            order = self._orders[orderId]
            
            # Store status in the order object for convenience
            order.status = status
            order.filled = filled
            order.remaining = remaining
            order.avgFillPrice = avgFillPrice
            order.lastFillPrice = lastFillPrice
            
            # Log status change
            contract = self._contracts.get(orderId)
            symbol = contract.symbol if contract else f"Order {orderId}"
            logger.info(f"Order status: {symbol} - {status}, Filled: {filled}/{order.totalQuantity} @ {avgFillPrice}")
    
    def execDetails(self, reqId: int, contract: Contract, execution: Execution) -> None:
        """Process execution details."""
        super().execDetails(reqId, contract, execution)
        
        order_id = execution.orderId
        if order_id in self._orders:
            # Log execution
            order = self._orders[order_id]
            logger.info(
                f"Execution: {contract.symbol} - {execution.side} {execution.shares} @ {execution.price}, "
                f"Commission: {execution.commission if hasattr(execution, 'commission') else 'N/A'}"
            )
    
    def commissionReport(self, commissionReport: CommissionReport) -> None:
        """Process commission report."""
        super().commissionReport(commissionReport)
        
        # Log commission
        logger.info(
            f"Commission report: Execution ID: {commissionReport.execId}, "
            f"Commission: {commissionReport.commission} {commissionReport.currency}"
        )
    
    # Error handling override
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        """Enhanced error handling with better logging for common Gateway errors."""
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        
        # Handle specific Gateway errors
        if errorCode == 1100:
            logger.warning("Gateway disconnected from TWS")
        elif errorCode == 1101:
            logger.info("Gateway reconnected to TWS")
        elif errorCode == 1102:
            logger.info("Gateway connection to TWS restored, data lost")
        elif errorCode == 2104:
            logger.info("Market data farm connection is OK")
        elif errorCode == 2106:
            logger.info("Historical data farm connection is OK")
        elif errorCode == 2108:
            logger.warning("Market data farm connection failed")
        elif errorCode == 2110:
            logger.warning("Historical data farm connection failed")
            
        # Handle order-related errors
        if reqId in self._orders:
            contract = self._contracts.get(reqId)
            symbol = contract.symbol if contract else f"Order {reqId}"
            logger.error(f"Order error for {symbol}: ({errorCode}) {errorString}")
            
        # Handle market data errors
        if reqId in self._market_data:
            contract = self._contracts.get(reqId)
            symbol = contract.symbol if contract else f"ID:{reqId}"
            
            if errorCode == 10167:  # Already subscribed
                logger.warning(f"Already subscribed to {symbol}")
            else:
                logger.error(f"Market data error for {symbol}: ({errorCode}) {errorString}")
                
                # Mark data as stale/invalid
                if reqId in self._market_data:
                    self._market_data[reqId]["error"] = errorString
                    self._market_data[reqId]["error_code"] = errorCode
                    self._notify_market_data_subscribers(reqId, self._market_data[reqId])