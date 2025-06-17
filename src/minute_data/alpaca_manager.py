#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca Minute Bar Manager

Handles historical minute bar data retrieval from Alpaca Markets API.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import threading

from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.models import Bar

from .models import MinuteBar, MinuteBarCollection
from .cache import MinuteDataCache
from ..logger import get_logger

logger = get_logger(__name__)


class AlpacaMinuteBarManager:
    """
    Manager for retrieving minute bar data from Alpaca.
    
    Provides historical data retrieval and real-time streaming capabilities
    compatible with the existing minute data infrastructure.
    """
    
    def __init__(self, connection: 'AlpacaConnection'):
        """
        Initialize the minute bar manager.
        
        Args:
            connection: AlpacaConnection instance
        """
        self.connection = connection
        self.cache = MinuteDataCache()
        self._subscribed_symbols: set = set()
        self._bar_callbacks: Dict[str, List[callable]] = {}
        self._streaming_active = False
        
        logger.info("AlpacaMinuteBarManager initialized")
    
    def _convert_alpaca_bar_to_minute_bar(self, bar: Bar, symbol: str) -> MinuteBar:
        """
        Convert an Alpaca Bar to a MinuteBar.
        
        Args:
            bar: Alpaca Bar object
            symbol: Stock symbol
            
        Returns:
            MinuteBar object
        """
        return MinuteBar(
            symbol=symbol,
            timestamp=bar.timestamp,
            open_price=float(bar.open),
            high_price=float(bar.high),
            low_price=float(bar.low),
            close_price=float(bar.close),
            volume=int(bar.volume),
            count=int(bar.trade_count) if bar.trade_count else None,
            wap=float(bar.vwap) if bar.vwap else None
        )
    
    def _parse_duration_to_timedelta(self, duration: str) -> timedelta:
        """
        Parse IB-style duration string to timedelta.
        
        Args:
            duration: Duration string (e.g., "1 D", "5 D", "1 W")
            
        Returns:
            timedelta object
        """
        parts = duration.strip().split()
        if len(parts) != 2:
            raise ValueError(f"Invalid duration format: {duration}")
        
        value = int(parts[0])
        unit = parts[1].upper()
        
        if unit == 'D':
            return timedelta(days=value)
        elif unit == 'W':
            return timedelta(weeks=value)
        elif unit == 'H':
            return timedelta(hours=value)
        elif unit == 'M':
            return timedelta(days=value * 30)  # Approximate
        elif unit == 'Y':
            return timedelta(days=value * 365)  # Approximate
        else:
            raise ValueError(f"Unsupported duration unit: {unit}")
    
    def _get_alpaca_timeframe(self, bar_size: str) -> TimeFrame:
        """
        Convert IB-style bar size to Alpaca TimeFrame.
        
        Args:
            bar_size: Bar size string (e.g., "1 min", "5 mins")
            
        Returns:
            Alpaca TimeFrame object
        """
        # Parse the bar size
        parts = bar_size.strip().lower().split()
        if len(parts) < 2:
            raise ValueError(f"Invalid bar size format: {bar_size}")
        
        value = int(parts[0])
        unit = parts[1].rstrip('s')  # Remove trailing 's' if present
        
        if unit == 'min':
            if value == 1:
                return TimeFrame.Minute
            elif value == 5:
                return TimeFrame(5, TimeFrameUnit.Minute)
            elif value == 15:
                return TimeFrame(15, TimeFrameUnit.Minute)
            elif value == 30:
                return TimeFrame(30, TimeFrameUnit.Minute)
            else:
                return TimeFrame(value, TimeFrameUnit.Minute)
        elif unit == 'hour':
            if value == 1:
                return TimeFrame.Hour
            else:
                return TimeFrame(value, TimeFrameUnit.Hour)
        elif unit == 'day':
            if value == 1:
                return TimeFrame.Day
            else:
                raise ValueError(f"Multi-day timeframes not supported: {bar_size}")
        else:
            raise ValueError(f"Unsupported bar size unit: {unit}")
    
    async def get_historical_bars(self, 
                                symbol: str, 
                                start: Optional[datetime] = None, 
                                end: Optional[datetime] = None,
                                duration: Optional[str] = None,
                                bar_size: str = "1 min",
                                use_cache: bool = True) -> MinuteBarCollection:
        """
        Get historical bars from Alpaca.
        
        Args:
            symbol: Stock symbol
            start: Start datetime (optional if duration provided)
            end: End datetime (defaults to now)
            duration: IB-style duration string (e.g., "5 D")
            bar_size: Bar size (e.g., "1 min", "5 mins")
            use_cache: Whether to use cache
            
        Returns:
            MinuteBarCollection with historical data
        """
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to Alpaca")
        
        # Set default end time if not provided
        if end is None:
            end = datetime.now(timezone.utc)
        
        # Calculate start time from duration if not provided
        if start is None and duration:
            delta = self._parse_duration_to_timedelta(duration)
            start = end - delta
        elif start is None:
            # Default to 1 day of data
            start = end - timedelta(days=1)
        
        # Ensure timezone awareness
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        # Check cache first if enabled
        if use_cache:
            # Create a Windows-compatible cache key
            start_str = start.isoformat().replace(':', '-').replace('+', '_')
            end_str = end.isoformat().replace(':', '-').replace('+', '_')
            bar_size_str = bar_size.replace(' ', '_')
            cache_key = f"{symbol}_{start_str}_{end_str}_{bar_size_str}"
            cached_data = self.cache.retrieve(cache_key)
            if cached_data is not None:
                logger.debug(f"Using cached data for {symbol}")
                return cached_data
        
        try:
            # Create the request
            timeframe = self._get_alpaca_timeframe(bar_size)
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                start=start,
                end=end,
                timeframe=timeframe,
                adjustment='all',  # Include all adjustments
                feed='iex'  # Use IEX feed for paper trading
            )
            
            # Get the data
            logger.debug(f"Requesting historical bars for {symbol} from {start} to {end}")
            bars_response = self.connection._data_client.get_stock_bars(request)
            
            # Debug: Log the response
            logger.debug(f"API Response type: {type(bars_response)}")
            logger.debug(f"API Response keys: {bars_response.keys() if hasattr(bars_response, 'keys') else 'N/A'}")
            
            # Convert to MinuteBarCollection
            collection = MinuteBarCollection(symbol=symbol)
            
            # The response has a 'data' attribute that contains the bars
            if hasattr(bars_response, 'data'):
                bars_data = bars_response.data
                if symbol in bars_data:
                    bars = bars_data[symbol]
                    logger.debug(f"Found {len(bars)} bars in response.data[{symbol}]")
                    for bar in bars:
                        minute_bar = self._convert_alpaca_bar_to_minute_bar(bar, symbol)
                        collection.add_bar(minute_bar)
                else:
                    logger.debug(f"No bars found for {symbol} in response.data")
            else:
                logger.debug(f"Response has no 'data' attribute")
            
            logger.info(f"Retrieved {len(collection)} bars for {symbol}")
            
            # Store in cache if enabled
            if use_cache and len(collection) > 0:
                self.cache.store(cache_key, collection)
            
            return collection
            
        except Exception as e:
            logger.error(f"Error fetching historical bars for {symbol}: {e}")
            raise
    
    async def get_historical_data(self,
                                symbol: str,
                                days: int = 5,
                                bar_size: str = "1 min",
                                use_cache: bool = True) -> List[MinuteBar]:
        """
        Get historical data for a symbol - convenience method for indicator calculations.
        
        Args:
            symbol: The ticker symbol
            days: Number of days of data to fetch
            bar_size: Size of each bar (e.g., "1 min", "5 mins")
            use_cache: Whether to use cache
            
        Returns:
            List of MinuteBar objects
        """
        # Calculate time range
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        
        # Fetch the data
        collection = await self.get_historical_bars(
            symbol=symbol,
            start=start,
            end=end,
            bar_size=bar_size,
            use_cache=use_cache
        )
        
        # Return the bars as a list
        return collection._bars if collection else []
    
    def subscribe_bars(self, symbols: List[str], callback: Optional[callable] = None) -> None:
        """
        Subscribe to real-time bar updates.
        
        Args:
            symbols: List of symbols to subscribe to
            callback: Optional callback function for bar updates
        """
        if not self.connection._data_stream:
            logger.warning("Data stream not initialized, cannot subscribe to bars")
            return
        
        try:
            # Add symbols to subscribed set
            for symbol in symbols:
                self._subscribed_symbols.add(symbol)
                if callback:
                    if symbol not in self._bar_callbacks:
                        self._bar_callbacks[symbol] = []
                    self._bar_callbacks[symbol].append(callback)
            
            # Define the handler for bar updates
            async def on_bar_update(data):
                """Handle incoming bar data."""
                symbol = data.symbol
                minute_bar = self._convert_alpaca_bar_to_minute_bar(data, symbol)
                
                # Call any registered callbacks
                if symbol in self._bar_callbacks:
                    for cb in self._bar_callbacks[symbol]:
                        try:
                            cb(minute_bar)
                        except Exception as e:
                            logger.error(f"Error in bar callback for {symbol}: {e}")
            
            # Subscribe to bars
            self.connection._data_stream.subscribe_bars(on_bar_update, *symbols)
            
            # Start streaming if not already active
            if not self._streaming_active:
                self._start_streaming()
            
            logger.info(f"Subscribed to bar updates for: {', '.join(symbols)}")
            
        except Exception as e:
            logger.error(f"Error subscribing to bars: {e}")
    
    def unsubscribe_bars(self, symbols: List[str]) -> None:
        """
        Unsubscribe from real-time bar updates.
        
        Args:
            symbols: List of symbols to unsubscribe from
        """
        if not self.connection._data_stream:
            return
        
        try:
            # Remove symbols from subscribed set
            for symbol in symbols:
                self._subscribed_symbols.discard(symbol)
                if symbol in self._bar_callbacks:
                    del self._bar_callbacks[symbol]
            
            # Unsubscribe from bars
            self.connection._data_stream.unsubscribe_bars(*symbols)
            
            logger.info(f"Unsubscribed from bar updates for: {', '.join(symbols)}")
            
            # Stop streaming if no more subscriptions
            if not self._subscribed_symbols and self._streaming_active:
                self._stop_streaming()
                
        except Exception as e:
            logger.error(f"Error unsubscribing from bars: {e}")
    
    def _start_streaming(self):
        """Start the data streaming thread."""
        if self._streaming_active:
            return
        
        def run_stream():
            try:
                logger.info("Starting Alpaca data stream...")
                asyncio.set_event_loop(asyncio.new_event_loop())
                self.connection._data_stream.run()
            except Exception as e:
                logger.error(f"Data stream error: {e}")
                self._streaming_active = False
        
        stream_thread = threading.Thread(target=run_stream, daemon=True)
        stream_thread.start()
        self._streaming_active = True
        logger.info("Data streaming started")
    
    def _stop_streaming(self):
        """Stop the data streaming."""
        if not self._streaming_active:
            return
        
        try:
            if self.connection._data_stream:
                self.connection._data_stream.stop()
            self._streaming_active = False
            logger.info("Data streaming stopped")
        except Exception as e:
            logger.error(f"Error stopping data stream: {e}")
    
    async def get_latest_bar(self, symbol: str) -> Optional[MinuteBar]:
        """
        Get the latest bar for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Latest MinuteBar or None if not available
        """
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            request = StockLatestBarRequest(symbol_or_symbols=symbol, feed='iex')
            response = self.connection._data_client.get_stock_latest_bar(request)
            
            if symbol in response:
                bar = response[symbol]
                return self._convert_alpaca_bar_to_minute_bar(bar, symbol)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching latest bar for {symbol}: {e}")
            return None 