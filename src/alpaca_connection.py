#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca Connection Management

Direct connection handling for Alpaca Markets API.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import uuid

from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, StopOrderRequest, 
    StopLimitOrderRequest, TrailingStopOrderRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from .alpaca_config import AlpacaConfig
from .logger import get_logger
from .event.alpaca_adapter import AlpacaEventAdapter
from .event.bus import EventBus

logger = get_logger(__name__)


class AlpacaConnection:
    """
    Alpaca connection handler that provides direct connection to Alpaca Markets API.
    
    This class handles the connection lifecycle, API communication,
    and provides a foundation for trading operations with Alpaca.
    """

    def __init__(self, config: AlpacaConfig, event_bus: Optional[EventBus] = None):
        """
        Initialize Alpaca connection.
        
        Args:
            config: Alpaca configuration settings
            event_bus: Optional event bus for event-driven updates
        """
        self.config = config
        self.event_bus = event_bus
        self._connected = False
        self._trading_client: Optional[TradingClient] = None
        self._trading_stream: Optional[TradingStream] = None
        self._data_client: Optional[StockHistoricalDataClient] = None
        self._data_stream: Optional[StockDataStream] = None
        self._start_time: Optional[float] = None
        
        # Order tracking
        self._next_client_order_id = 1
        self._pending_orders: Dict[str, Any] = {}
        self._order_id_map: Dict[str, str] = {}  # client_order_id -> alpaca_order_id
        
        # Initialize minute bar manager for historical data
        from src.minute_data.alpaca_manager import AlpacaMinuteBarManager
        self.minute_bar_manager = AlpacaMinuteBarManager(connection=self)
        
        # Initialize event adapter if event bus provided
        self.event_adapter: Optional[AlpacaEventAdapter] = None
        if event_bus:
            self.event_adapter = AlpacaEventAdapter(event_bus)
        
        # Connection state callbacks
        self._on_connected: Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        # Trade update callbacks (for backward compatibility)
        self.orderStatus = None  # Will be overridden by OrderManager
        self.execDetails = None  # Will be overridden by OrderManager
    
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
        Connect to Alpaca asynchronously.
        
        Returns:
            bool: True if connection was successful
        """
        if self._connected:
            logger.warning("Already connected to Alpaca")
            return True
            
        logger.info(f"Connecting to Alpaca ({self.config.trading_mode} mode)")
        
        # Reset state
        self._connected = False
        self._start_time = time.time()
        
        try:
            # Initialize REST API clients
            self._trading_client = TradingClient(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key,
                paper=self.config.is_paper_trading
            )
            
            # Initialize data client
            self._data_client = StockHistoricalDataClient(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key
            )
            
            # Test connection by getting account info
            account = self._trading_client.get_account()
            logger.info(f"Connected to Alpaca - Account: {account.account_number}")
            logger.info(f"Buying Power: ${account.buying_power}")
            logger.info(f"Portfolio Value: ${account.portfolio_value}")
            
            # Initialize WebSocket streams
            await self._initialize_streams()
            
            self._connected = True
            
            # Call user callback if set
            if self._on_connected:
                try:
                    self._on_connected()
                except Exception as e:
                    logger.error(f"Error in connected callback: {e}")
            
            return True
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._connected = False
            return False
    
    async def _initialize_streams(self):
        """Initialize WebSocket streams for real-time updates."""
        try:
            # Initialize trading stream for order updates
            self._trading_stream = TradingStream(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key,
                paper=self.config.is_paper_trading
            )
            
            # Subscribe to trade updates
            async def on_trade_update(data):
                """Handle trade updates from Alpaca."""
                logger.debug(f"Trade update received: {data}")
                
                # Use event adapter if available
                if self.event_adapter:
                    await self.event_adapter.handle_trade_update(data)
                
                # Also handle legacy callbacks for backward compatibility
                # Handle fill events
                if data.event == "fill" or data.event == "partial_fill":
                    if self.execDetails:
                        # Create execution object
                        execution = {
                            'orderId': data.order.client_order_id,
                            'execId': str(uuid.uuid4()),
                            'shares': data.qty,
                            'price': data.price,
                            'side': data.order.side.value,
                            'symbol': data.order.symbol
                        }
                        self.execDetails(execution)
                
                # Handle order status updates
                if self.orderStatus:
                    filled_qty = float(data.order.filled_qty) if data.order.filled_qty else 0.0
                    remaining = float(data.order.qty) - filled_qty
                    avg_fill_price = float(data.order.filled_avg_price) if data.order.filled_avg_price else 0.0
                    
                    self.orderStatus(
                        orderId=data.order.client_order_id,
                        status=data.order.status.value,
                        filled=filled_qty,
                        remaining=remaining,
                        avgFillPrice=avg_fill_price,
                        lastFillPrice=float(data.price) if hasattr(data, 'price') and data.price else 0.0
                    )
            
            self._trading_stream.subscribe_trade_updates(on_trade_update)
            
            # Start the trading stream in a background thread
            def run_trading_stream():
                try:
                    logger.info("Starting Alpaca trading stream...")
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    self._trading_stream.run()
                except Exception as e:
                    logger.error(f"Trading stream error: {e}")
            
            trading_thread = threading.Thread(target=run_trading_stream, daemon=True)
            trading_thread.start()
            
            # Initialize data stream for market data
            self._data_stream = StockDataStream(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key
            )
            
            logger.info("WebSocket streams initialized")
            
        except Exception as e:
            logger.error(f"Error initializing streams: {e}")
            raise
    
    def disconnect(self) -> None:
        """Disconnect from Alpaca safely."""
        if not self._connected:
            logger.warning("Not connected to Alpaca")
            return
            
        logger.info("Disconnecting from Alpaca")
        
        try:
            # Reset connection state
            self._connected = False
            
            # Close streams
            if self._trading_stream:
                try:
                    self._trading_stream.stop()
                except Exception as e:
                    logger.debug(f"Error stopping trading stream: {e}")
            
            if self._data_stream:
                try:
                    self._data_stream.stop()
                except Exception as e:
                    logger.debug(f"Error stopping data stream: {e}")
            
            # Clear clients
            self._trading_client = None
            self._data_client = None
            
            logger.info("Disconnected from Alpaca")
            
            # Call user callback if set
            if self._on_disconnected:
                try:
                    self._on_disconnected()
                except Exception as e:
                    logger.error(f"Error in disconnected callback: {e}")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """
        Check if connected to Alpaca.
        
        Returns:
            bool: True if connected
        """
        return self._connected and self._trading_client is not None
    
    def get_next_order_id(self) -> str:
        """
        Get the next valid order ID.
        
        Returns:
            str: Next order ID
        """
        if not self._connected:
            return None
        
        # Generate a unique client order ID
        order_id = f"ORD_{int(time.time())}_{self._next_client_order_id}"
        self._next_client_order_id += 1
        return order_id
    
    def get_next_request_id(self) -> int:
        """
        Get the next request ID for API calls.
        
        Returns:
            int: Next request ID
        """
        return int(time.time())
    
    # Trading methods
    def placeOrder(self, orderId: str, symbol: str, quantity: float, 
                   order_type: str, side: str, limit_price: Optional[float] = None,
                   stop_price: Optional[float] = None, time_in_force: str = "DAY") -> None:
        """
        Place an order with Alpaca.
        
        Args:
            orderId: Client order ID
            symbol: Stock symbol
            quantity: Order quantity
            order_type: Order type (MKT, LMT, STP, STP_LMT)
            side: Order side (BUY or SELL)
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: Time in force (DAY, GTC, IOC, FOK)
        """
        if not self._connected or not self._trading_client:
            logger.error("Cannot place order - not connected")
            return
        
        try:
            # Determine order side
            order_side = OrderSide.BUY if side == 'BUY' else OrderSide.SELL
            
            # Determine time in force
            tif_map = {
                'DAY': TimeInForce.DAY,
                'GTC': TimeInForce.GTC,
                'IOC': TimeInForce.IOC,
                'FOK': TimeInForce.FOK
            }
            tif = tif_map.get(time_in_force, TimeInForce.DAY)
            
            # Create appropriate order request based on order type
            if order_type == 'MKT':
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    client_order_id=str(orderId)
                )
            elif order_type == 'LMT':
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    limit_price=limit_price,
                    client_order_id=str(orderId)
                )
            elif order_type == 'STP':
                order_request = StopOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    stop_price=stop_price,
                    client_order_id=str(orderId)
                )
            elif order_type == 'STP_LMT':
                order_request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    stop_price=stop_price,
                    limit_price=limit_price,
                    client_order_id=str(orderId)
                )
            else:
                logger.error(f"Unsupported order type: {order_type}")
                return
            
            # Submit order
            logger.info(f"Submitting order to Alpaca: {order_request}")
            alpaca_order = self._trading_client.submit_order(order_request)
            logger.info(f"Order submitted successfully: {alpaca_order.id}")
            
            # Store order for tracking
            self._pending_orders[str(orderId)] = alpaca_order
            self._order_id_map[str(orderId)] = alpaca_order.id
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            if self._on_error:
                self._on_error(orderId, -1, str(e))
    
    def cancelOrder(self, orderId: str) -> None:
        """
        Cancel an order with Alpaca.
        
        Args:
            orderId: Client order ID to cancel
        """
        if not self._connected or not self._trading_client:
            logger.error("Cannot cancel order - not connected")
            return
        
        try:
            # Try to get the Alpaca order ID from our mapping
            alpaca_order_id = self._order_id_map.get(str(orderId))
            
            if alpaca_order_id:
                # Cancel by Alpaca order ID
                self._trading_client.cancel_order_by_id(alpaca_order_id)
                logger.info(f"Cancel request sent for order {orderId} (Alpaca ID: {alpaca_order_id})")
            else:
                # Try to get all open orders and find by client order ID
                open_orders = self._trading_client.get_orders()
                for order in open_orders:
                    if order.client_order_id == str(orderId):
                        self._trading_client.cancel_order_by_id(order.id)
                        logger.info(f"Cancel request sent for order {orderId}")
                        return
                
                logger.warning(f"Order {orderId} not found in open orders")
                
        except Exception as e:
            logger.error(f"Error cancelling order {orderId}: {e}")
            if self._on_error:
                self._on_error(orderId, -1, str(e))
    
    # Account methods
    def get_account(self):
        """Get account information."""
        if not self._connected or not self._trading_client:
            return None
        
        try:
            return self._trading_client.get_account()
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None
    
    def get_positions(self):
        """Get all positions."""
        if not self._connected or not self._trading_client:
            return []
        
        try:
            return self._trading_client.get_all_positions()
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_position(self, symbol: str):
        """Get position for a specific symbol."""
        if not self._connected or not self._trading_client:
            return None
        
        try:
            return self._trading_client.get_position(symbol)
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None 