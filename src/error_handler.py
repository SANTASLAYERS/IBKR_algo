#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

from .logger import get_logger

logger = get_logger(__name__)

# IBKR error code categories
CONNECTION_ERRORS = {1100, 1101, 1102, 1300, 2103, 2104, 2105, 2106, 2107, 2108}
ORDER_ERRORS = {103, 104, 105, 106, 107, 109, 110, 111, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 129, 131, 132, 133, 134, 135, 136, 137, 140, 141, 142, 143, 144, 145, 146, 147, 148, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 201, 202, 203}
MARKET_DATA_ERRORS = {300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330}
HISTORICAL_DATA_ERRORS = {162, 165, 166, 200, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379}
SOCKET_ERRORS = {500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530}
AUTHORIZATION_ERRORS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17}
SEVERE_ERRORS = {401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436}
WARNING_ERRORS = {2100, 2101, 2102, 2103, 2104, 2105, 2106, 2107, 2108, 2109, 2110, 2111, 2112, 2113, 2114, 2115, 2116, 2117, 2118, 2119, 2120, 2121, 2122, 2123, 2124, 2125, 2126, 2127, 2128, 2129, 2130, 2131, 2132, 2133, 2134, 2135, 2136, 2137, 2138, 2139, 2140, 2141, 2142, 2143, 2144, 2145, 2146, 2147, 2148, 2149, 2150, 2151, 2152, 2153, 2154, 2155, 2156, 2157, 2158, 2159, 2160}

class IBKRError:
    """
    Represents an error from IBKR API.
    """
    
    def __init__(
        self, 
        req_id: int, 
        error_code: int, 
        error_string: str,
        advanced_order_reject_json: str = ""
    ):
        """
        Initialize an IBKR error.
        
        Args:
            req_id: Request ID associated with the error
            error_code: Error code from IBKR
            error_string: Error message from IBKR
            advanced_order_reject_json: Advanced order rejection details (JSON string)
        """
        self.req_id = req_id
        self.error_code = error_code
        self.error_string = error_string
        self.advanced_order_reject_json = advanced_order_reject_json
        self.timestamp = None  # Will be set by the error handler
        
        # Parse advanced order reject JSON if provided
        self.advanced_order_reject = None
        if advanced_order_reject_json:
            try:
                self.advanced_order_reject = json.loads(advanced_order_reject_json)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse advanced order reject JSON: {advanced_order_reject_json}")
    
    def is_connection_error(self) -> bool:
        """Check if this is a connection-related error"""
        return self.error_code in CONNECTION_ERRORS
    
    def is_order_error(self) -> bool:
        """Check if this is an order-related error"""
        return self.error_code in ORDER_ERRORS
    
    def is_market_data_error(self) -> bool:
        """Check if this is a market data-related error"""
        return self.error_code in MARKET_DATA_ERRORS
    
    def is_historical_data_error(self) -> bool:
        """Check if this is a historical data-related error"""
        return self.error_code in HISTORICAL_DATA_ERRORS
    
    def is_socket_error(self) -> bool:
        """Check if this is a socket-related error"""
        return self.error_code in SOCKET_ERRORS
    
    def is_authorization_error(self) -> bool:
        """Check if this is an authorization-related error"""
        return self.error_code in AUTHORIZATION_ERRORS
    
    def is_severe(self) -> bool:
        """Check if this is a severe error"""
        return self.error_code in SEVERE_ERRORS
    
    def is_warning(self) -> bool:
        """Check if this is a warning"""
        return self.error_code in WARNING_ERRORS
    
    def __str__(self) -> str:
        return f"IBKRError(reqId={self.req_id}, code={self.error_code}, message='{self.error_string}')"


class ErrorHandler:
    """
    Handles errors from IBKR API.
    """
    
    def __init__(self):
        """
        Initialize the error handler.
        """
        # Error callback registry - mapping error categories to callback functions
        self._callbacks: Dict[str, List[Callable[[IBKRError], None]]] = {
            "any": [],
            "connection": [],
            "order": [],
            "market_data": [],
            "historical_data": [],
            "socket": [],
            "authorization": [],
            "severe": [],
            "warning": [],
        }
        
        # Error history - keeps track of recent errors
        self._error_history: List[IBKRError] = []
        self._max_history_size = 100
    
    def handle_error(
        self, 
        req_id: int, 
        error_code: int, 
        error_string: str,
        advanced_order_reject_json: str = ""
    ):
        """
        Handle an error from IBKR API.
        
        Args:
            req_id: Request ID associated with the error
            error_code: Error code from IBKR
            error_string: Error message from IBKR
            advanced_order_reject_json: Advanced order rejection details (JSON string)
        """
        # Create error object
        error = IBKRError(req_id, error_code, error_string, advanced_order_reject_json)
        
        # Log the error
        self._log_error(error)
        
        # Add to history
        self._add_to_history(error)
        
        # Call appropriate callbacks
        self._call_callbacks(error)
    
    def _log_error(self, error: IBKRError):
        """
        Log the error with appropriate level based on severity.
        
        Args:
            error: The error to log
        """
        if error.error_code == 2104 or error.error_code == 2106:
            # Market data farm connection is OK
            logger.info(f"IBKR Info: {error}")
        elif error.is_warning():
            logger.warning(f"IBKR Warning: {error}")
        elif error.is_severe():
            logger.error(f"IBKR Severe Error: {error}")
        else:
            log_level = "error"
            
            # Determine log level based on error category
            if error.is_connection_error():
                if error.error_code in {1101, 1102, 1300}:  # Connection restored
                    log_level = "info"
                else:
                    log_level = "warning"
            elif error.error_code == 202:  # Order cancelled
                log_level = "info"
            elif error.error_code == 399:  # No recent historical data
                log_level = "warning"
            elif error.error_code == 10167:  # Duplicate ticker ID
                log_level = "warning"
            
            # Log with appropriate level
            if log_level == "info":
                logger.info(f"IBKR: {error}")
            elif log_level == "warning":
                logger.warning(f"IBKR: {error}")
            else:
                logger.error(f"IBKR: {error}")
    
    def _add_to_history(self, error: IBKRError):
        """
        Add error to history, maintaining maximum size.
        
        Args:
            error: The error to add to history
        """
        import datetime
        
        # Set timestamp
        error.timestamp = datetime.datetime.now()
        
        # Add to history
        self._error_history.append(error)
        
        # Maintain maximum history size
        if len(self._error_history) > self._max_history_size:
            self._error_history.pop(0)
    
    def _call_callbacks(self, error: IBKRError):
        """
        Call registered callbacks for the error.
        
        Args:
            error: The error to process
        """
        # Call "any" callbacks
        for callback in self._callbacks["any"]:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {str(e)}")
        
        # Call category-specific callbacks
        categories = []
        
        if error.is_connection_error():
            categories.append("connection")
        if error.is_order_error():
            categories.append("order")
        if error.is_market_data_error():
            categories.append("market_data")
        if error.is_historical_data_error():
            categories.append("historical_data")
        if error.is_socket_error():
            categories.append("socket")
        if error.is_authorization_error():
            categories.append("authorization")
        if error.is_severe():
            categories.append("severe")
        if error.is_warning():
            categories.append("warning")
        
        for category in categories:
            for callback in self._callbacks[category]:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"Error in {category} error callback: {str(e)}")
    
    def register_callback(self, callback: Callable[[IBKRError], None], category: str = "any"):
        """
        Register a callback function for errors.
        
        Args:
            callback: Function to call when an error occurs
            category: Error category to register for (default: "any")
        """
        if category not in self._callbacks:
            logger.warning(f"Unknown error category: {category}")
            return
            
        if callback not in self._callbacks[category]:
            self._callbacks[category].append(callback)
    
    def unregister_callback(self, callback: Callable[[IBKRError], None], category: str = "any"):
        """
        Unregister a callback function.
        
        Args:
            callback: Function to unregister
            category: Error category to unregister from (default: "any")
        """
        if category not in self._callbacks:
            logger.warning(f"Unknown error category: {category}")
            return
            
        if callback in self._callbacks[category]:
            self._callbacks[category].remove(callback)
    
    def get_error_history(self) -> List[IBKRError]:
        """
        Get the error history.
        
        Returns:
            List of errors
        """
        return self._error_history.copy()
    
    def clear_error_history(self):
        """
        Clear the error history.
        """
        self._error_history.clear()