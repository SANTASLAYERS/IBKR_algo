#!/usr/bin/env python3
"""
Price Service
=============

Simple price service that gets real-time stock prices from TWS.
No caching, no external APIs - just clean, direct TWS price requests.
"""

import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceService:
    """Service for getting real-time stock prices from TWS."""
    
    def __init__(self, tws_connection):
        """
        Initialize price service.
        
        Args:
            tws_connection: Active TWS connection instance
        """
        self.tws_connection = tws_connection
        self._price_requests = {}  # Track pending requests
        self._request_id_counter = 1000  # Start from 1000 to avoid conflicts
    
    async def get_price(self, symbol: str, timeout: float = 5.0) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeout: Timeout in seconds
            
        Returns:
            Current price or None if unavailable
        """
        if not self.tws_connection.is_connected():
            logger.warning("TWS not connected - cannot get price")
            return None
            
        try:
            # Create contract for the symbol
            from ibapi.contract import Contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Get next request ID
            req_id = self._request_id_counter
            self._request_id_counter += 1
            
            # Create event to wait for price
            price_event = asyncio.Event()
            price_data = {"price": None, "error": None}
            
            # Store request info
            self._price_requests[req_id] = {
                "symbol": symbol,
                "event": price_event,
                "data": price_data
            }
            
            # Set up temporary callback for market data
            original_tickPrice = self.tws_connection.tickPrice
            original_error = self.tws_connection.error
            
            def handle_tick_price(reqId: int, tickType: int, price: float, attrib):
                """Handle incoming price tick."""
                if reqId in self._price_requests and tickType in [1, 2, 4]:  # Bid, Ask, Last
                    request = self._price_requests[reqId]
                    request["data"]["price"] = price
                    request["event"].set()
                # Call original handler
                original_tickPrice(reqId, tickType, price, attrib)
            
            def handle_error(reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
                """Handle price request errors."""
                if reqId in self._price_requests:
                    request = self._price_requests[reqId]
                    request["data"]["error"] = f"Error {errorCode}: {errorString}"
                    request["event"].set()
                # Call original handler
                original_error(reqId, errorCode, errorString, advancedOrderRejectJson)
            
            # Override callbacks temporarily
            self.tws_connection.tickPrice = handle_tick_price
            self.tws_connection.error = handle_error
            
            try:
                # Request market data
                self.tws_connection.reqMktData(req_id, contract, "", False, False, [])
                
                # Wait for price or timeout
                await asyncio.wait_for(price_event.wait(), timeout=timeout)
                
                # Get the price
                price = price_data["price"]
                error = price_data["error"]
                
                if error:
                    logger.warning(f"Error getting price for {symbol}: {error}")
                    return None
                    
                if price and price > 0:
                    logger.debug(f"Got price for {symbol}: ${price:.2f}")
                    return float(price)
                else:
                    logger.warning(f"Invalid price received for {symbol}: {price}")
                    return None
                    
            finally:
                # Always cancel market data request
                try:
                    self.tws_connection.cancelMktData(req_id)
                except:
                    pass  # Ignore errors during cleanup
                
                # Restore original callbacks
                self.tws_connection.tickPrice = original_tickPrice
                self.tws_connection.error = original_error
                
                # Clean up request tracking
                if req_id in self._price_requests:
                    del self._price_requests[req_id]
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting price for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    async def get_multiple_prices(self, symbols: list, timeout: float = 10.0) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple symbols concurrently.
        
        Args:
            symbols: List of symbols
            timeout: Total timeout for all requests
            
        Returns:
            Dictionary mapping symbol to price (or None)
        """
        tasks = [self.get_price(symbol, timeout) for symbol in symbols]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for symbol, price in zip(symbols, prices):
            if isinstance(price, Exception):
                logger.error(f"Exception getting price for {symbol}: {price}")
                result[symbol] = None
            else:
                result[symbol] = price
                
        return result 