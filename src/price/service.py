#!/usr/bin/env python3
"""
Price Service
=============

Simple price service that gets real-time stock prices from Alpaca.
Provides clean, direct price requests using Alpaca's REST API.
"""

import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceService:
    """Service for getting real-time stock prices from Alpaca."""
    
    def __init__(self, alpaca_connection):
        """
        Initialize price service.
        
        Args:
            alpaca_connection: Active AlpacaConnection instance
        """
        self.alpaca_connection = alpaca_connection
    
    async def get_price(self, symbol: str, timeout: float = 5.0) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeout: Timeout in seconds
            
        Returns:
            Current price or None if unavailable
        """
        if not self.alpaca_connection.is_connected():
            logger.warning("Alpaca not connected - cannot get price")
            return None
            
        try:
            # Use the data client to get latest quote
            data_client = self.alpaca_connection._data_client
            if not data_client:
                logger.error("No data client available")
                return None
            
            # Get latest quote for the symbol
            from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            
            # Get the quote
            quotes = data_client.get_stock_latest_quote(request)
            
            if symbol in quotes:
                quote = quotes[symbol]
                # Use midpoint of bid/ask if available, otherwise last trade price
                if quote.bid_price and quote.ask_price:
                    price = (quote.bid_price + quote.ask_price) / 2.0
                else:
                    # Try to get last trade price
                    trades = data_client.get_stock_latest_trade(
                        StockLatestTradeRequest(symbol_or_symbols=symbol)
                    )
                    if symbol in trades:
                        price = trades[symbol].price
                    else:
                        logger.warning(f"No price data available for {symbol}")
                        return None
                
                if price and price > 0:
                    logger.debug(f"Got price for {symbol}: ${price:.2f}")
                    return float(price)
                else:
                    logger.warning(f"Invalid price received for {symbol}: {price}")
                    return None
            else:
                logger.warning(f"No quote data for {symbol}")
                return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting price for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    async def get_multiple_prices(self, symbols: list, timeout: float = 10.0) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple symbols efficiently.
        
        Args:
            symbols: List of symbols
            timeout: Total timeout for all requests
            
        Returns:
            Dictionary mapping symbol to price (or None)
        """
        if not self.alpaca_connection.is_connected():
            logger.warning("Alpaca not connected - cannot get prices")
            return {symbol: None for symbol in symbols}
        
        try:
            # Use the data client to get latest quotes for all symbols at once
            data_client = self.alpaca_connection._data_client
            if not data_client:
                logger.error("No data client available")
                return {symbol: None for symbol in symbols}
            
            # Get latest quotes for all symbols
            from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            
            # Get the quotes
            quotes = data_client.get_stock_latest_quote(quote_request)
            
            # Also get latest trades as fallback
            trade_request = StockLatestTradeRequest(symbol_or_symbols=symbols)
            trades = data_client.get_stock_latest_trade(trade_request)
            
            result = {}
            for symbol in symbols:
                try:
                    price = None
                    
                    # Try to get price from quote
                    if symbol in quotes:
                        quote = quotes[symbol]
                        if quote.bid_price and quote.ask_price:
                            price = (quote.bid_price + quote.ask_price) / 2.0
                    
                    # Fallback to last trade price
                    if not price and symbol in trades:
                        price = trades[symbol].price
                    
                    if price and price > 0:
                        result[symbol] = float(price)
                        logger.debug(f"Got price for {symbol}: ${price:.2f}")
                    else:
                        result[symbol] = None
                        logger.warning(f"No valid price for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error processing price for {symbol}: {e}")
                    result[symbol] = None
                    
            return result
            
        except Exception as e:
            logger.error(f"Error getting multiple prices: {e}")
            return {symbol: None for symbol in symbols} 