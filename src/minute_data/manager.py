#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Manager for handling IB historical minute bar data.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Union

from ibapi.contract import Contract
from ibapi.common import BarData

from .models import MinuteBar, MinuteBarCollection
from .cache import MinuteDataCache


logger = logging.getLogger(__name__)


class MinuteBarManager:
    """
    Manager for requesting and processing minute bar data from IB API.
    """
    
    def __init__(self, gateway):
        """
        Initialize the minute bar manager.
        
        Args:
            gateway: IBGateway instance
        """
        self.gateway = gateway
        
        # Store for temporary bar data
        self._temp_bars: Dict[int, List[MinuteBar]] = {}
        
        # Store for request futures
        self._data_futures: Dict[int, asyncio.Future] = {}
        
        # Map request IDs to symbols
        self._request_symbols: Dict[int, str] = {}
        
        # Initialize cache
        self.cache = MinuteDataCache()
        
        # Inject our callback handlers into the gateway
        self._inject_callbacks()
    
    def _inject_callbacks(self) -> None:
        """Inject our callback handlers into the gateway."""
        # Save original callbacks if they exist
        self._original_historical_data = getattr(self.gateway, "historicalData", None)
        self._original_historical_data_end = getattr(self.gateway, "historicalDataEnd", None)
        self._original_error = getattr(self.gateway, "error", None)
        
        # Inject our callbacks
        self.gateway.historicalData = self.historicalData
        self.gateway.historicalDataEnd = self.historicalDataEnd
        
        # For error handling, we need special handling to call the original error handler
        if self._original_error:
            orig_error = self._original_error
            
            def error_wrapper(reqId, errorCode, errorString, advancedOrderRejectJson=""):
                # Call our error handler first
                self.error(reqId, errorCode, errorString, advancedOrderRejectJson)
                # Then call the original error handler
                return orig_error(reqId, errorCode, errorString, advancedOrderRejectJson)
                
            self.gateway.error = error_wrapper
        else:
            self.gateway.error = self.error
    
    def request_historical_minute_data(
        self,
        contract: Contract,
        end_date: Optional[datetime] = None,
        duration: str = "1 D",
        bar_size: str = "1 min",
        what_to_show: str = "TRADES",
        use_rth: bool = True
    ) -> int:
        """
        Request historical minute bar data.
        
        Args:
            contract: Contract for the data
            end_date: End date/time for the data request (defaults to now)
            duration: Time duration to go back from end_date
            bar_size: Size of each bar
            what_to_show: Type of data to request
            use_rth: Use regular trading hours only
            
        Returns:
            Request ID
        """
        # Get a unique request ID
        req_id = self.gateway.get_next_request_id()
        
        # Store the symbol for this request
        self._request_symbols[req_id] = contract.symbol
        
        # Format the end date/time
        if end_date is None:
            end_date = datetime.now(timezone.utc)
            
        # Convert to IB format: yyyyMMdd HH:mm:ss
        end_date_str = end_date.strftime("%Y%m%d %H:%M:%S")
        
        # Request the data
        self.gateway.reqHistoricalData(
            req_id,
            contract,
            end_date_str,
            duration,
            bar_size,
            what_to_show,
            use_rth,
            2,  # dateFormat: 2 = seconds since epoch
            False,  # keepUpToDate: False = historical only
            []  # chartOptions
        )
        
        logger.debug(
            f"Requested historical data for {contract.symbol}: "
            f"reqId={req_id}, end={end_date_str}, duration={duration}, bar_size={bar_size}"
        )
        
        return req_id
    
    def request_historical_minute_data_async(
        self,
        contract: Contract,
        end_date: Optional[datetime] = None,
        duration: str = "1 D",
        bar_size: str = "1 min",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        use_cache: bool = True
    ) -> asyncio.Future:
        """
        Request historical minute bar data asynchronously.
        
        Args:
            contract: Contract for the data
            end_date: End date/time for the data request (defaults to now)
            duration: Time duration to go back from end_date
            bar_size: Size of each bar
            what_to_show: Type of data to request
            use_rth: Use regular trading hours only
            use_cache: Use cache if available
            
        Returns:
            Future that will be resolved with MinuteBarCollection
        """
        # If end_date is None, set it to now
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        
        # Check cache first if enabled
        if use_cache:
            cache_key = self.cache.generate_cache_key(
                contract, end_date, duration, bar_size
            )
            
            cached_data = self.cache.retrieve(cache_key)
            if cached_data is not None:
                logger.debug(f"Using cached data for {contract.symbol}")
                # Create a future and resolve it immediately with the cached data
                future = asyncio.Future()
                future.set_result(cached_data)
                return future
        
        # Create a future for this request
        future = asyncio.Future()
        
        # Make the request
        req_id = self.request_historical_minute_data(
            contract, end_date, duration, bar_size, what_to_show, use_rth
        )
        
        # Store the future
        self._data_futures[req_id] = future
        
        # If using cache, store the cache key for later
        if use_cache:
            future.cache_key = cache_key
            future.use_cache = True
        else:
            future.use_cache = False
        
        return future
    
    def cancel_historical_data_request(self, req_id: int) -> None:
        """
        Cancel a historical data request.
        
        Args:
            req_id: Request ID to cancel
        """
        # Cancel the request in IB API
        self.gateway.cancelHistoricalData(req_id)
        
        # Cancel the future if it exists
        if req_id in self._data_futures:
            self._data_futures[req_id].cancel()
            del self._data_futures[req_id]
        
        # Clean up any temporary data
        if req_id in self._temp_bars:
            del self._temp_bars[req_id]
            
        if req_id in self._request_symbols:
            del self._request_symbols[req_id]
        
        logger.debug(f"Cancelled historical data request {req_id}")
    
    async def fetch_minute_bars(
        self,
        contract: Contract,
        end_date: Optional[datetime] = None,
        duration: str = "1 D",
        bar_size: str = "1 min",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        use_cache: bool = True
    ) -> MinuteBarCollection:
        """
        Fetch minute bars asynchronously.
        
        Args:
            contract: Contract for the data
            end_date: End date/time for the data request (defaults to now)
            duration: Time duration to go back from end_date
            bar_size: Size of each bar
            what_to_show: Type of data to request
            use_rth: Use regular trading hours only
            use_cache: Use cache if available
            
        Returns:
            MinuteBarCollection with the requested data
            
        Raises:
            Exception: If there's an error fetching the data
        """
        future = self.request_historical_minute_data_async(
            contract, end_date, duration, bar_size, what_to_show, use_rth, use_cache
        )
        
        # Wait for the result
        return await future
    
    def _convert_ib_bar_to_minute_bar(self, bar: BarData, symbol: str) -> MinuteBar:
        """
        Convert an IB BarData to a MinuteBar.
        
        Args:
            bar: IB BarData
            symbol: Symbol for the bar
            
        Returns:
            MinuteBar
        """
        # Parse the timestamp
        if isinstance(bar.date, str):
            # Format: YYYYMMDD HH:MM:SS
            timestamp = datetime.strptime(bar.date, "%Y%m%d %H:%M:%S")
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            # Unix timestamp in seconds
            timestamp = datetime.fromtimestamp(bar.date, tz=timezone.utc)
        
        # Create and return the minute bar
        return MinuteBar(
            symbol=symbol,
            timestamp=timestamp,
            open_price=bar.open,
            high_price=bar.high,
            low_price=bar.low,
            close_price=bar.close,
            volume=int(bar.volume),
            count=getattr(bar, "barCount", None),
            wap=getattr(bar, "average", None)
        )
    
    # IB API callbacks
    def historicalData(self, reqId: int, bar: BarData) -> None:
        """
        Handle historical data callback from IB API.
        
        Args:
            reqId: Request ID
            bar: Bar data
        """
        # Check if we're tracking this request
        if reqId not in self._request_symbols:
            return
            
        # Get symbol for this request
        symbol = self._request_symbols[reqId]
        
        # Initialize temp storage if needed
        if reqId not in self._temp_bars:
            self._temp_bars[reqId] = []
        
        # Convert and store the bar
        minute_bar = self._convert_ib_bar_to_minute_bar(bar, symbol)
        self._temp_bars[reqId].append(minute_bar)
        
        logger.debug(
            f"Received historical bar for {symbol}: "
            f"time={minute_bar.timestamp.isoformat()}, "
            f"open={minute_bar.open_price}, close={minute_bar.close_price}"
        )
    
    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """
        Handle historical data end callback from IB API.
        
        Args:
            reqId: Request ID
            start: Start date of the data
            end: End date of the data
        """
        # Check if we're tracking this request
        if reqId not in self._request_symbols:
            return
            
        # Get symbol for this request
        symbol = self._request_symbols[reqId]
        
        # Create the collection from temp bars
        bars = self._temp_bars.get(reqId, [])
        collection = MinuteBarCollection(symbol=symbol, bars=bars)
        
        logger.debug(
            f"Historical data complete for {symbol}: "
            f"reqId={reqId}, bars={len(collection)}"
        )
        
        # If we have a future for this request, resolve it
        if reqId in self._data_futures:
            future = self._data_futures[reqId]
            
            # Store in cache if enabled
            if hasattr(future, "use_cache") and future.use_cache and hasattr(future, "cache_key"):
                self.cache.store(future.cache_key, collection)
            
            # Resolve the future
            if not future.done():
                future.set_result(collection)
        
        # Clean up
        if reqId in self._temp_bars:
            del self._temp_bars[reqId]
            
        if reqId in self._data_futures:
            del self._data_futures[reqId]
            
        if reqId in self._request_symbols:
            del self._request_symbols[reqId]
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        """
        Handle error callback from IB API.
        
        Args:
            reqId: Request ID
            errorCode: Error code
            errorString: Error message
            advancedOrderRejectJson: Additional error data
        """
        # Check if this is for a historical data request we're tracking
        if reqId in self._data_futures:
            # Certain error codes are expected and shouldn't cause a failure
            non_critical_errors = [2106, 2107, 2108]
            
            if errorCode not in non_critical_errors:
                logger.error(
                    f"Error for historical data request {reqId}: "
                    f"({errorCode}) {errorString}"
                )
                
                # Reject the future
                future = self._data_futures[reqId]
                if not future.done():
                    future.set_exception(
                        Exception(f"IB API Error ({errorCode}): {errorString}")
                    )
                
                # Clean up
                if reqId in self._temp_bars:
                    del self._temp_bars[reqId]
                    
                if reqId in self._data_futures:
                    del self._data_futures[reqId]
                    
                if reqId in self._request_symbols:
                    del self._request_symbols[reqId]