#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Error handling for the trading system.
"""

import logging
from typing import Dict, List, Callable, Optional
from datetime import datetime

# Trading error code categories
ERROR_INFO = range(2000, 3000)  # Informational messages
ERROR_WARNING = range(1000, 2000)  # Warning messages
ERROR_SEVERE = range(0, 1000)  # Severe errors

# Common error codes
CONNECTION_ERROR = 502
MARKET_DATA_ERROR = 354
ORDER_ERROR = 201

logger = logging.getLogger(__name__)


class TradingError:
    """
    Represents an error from the trading system.
    
    Attributes:
        req_id: Request ID associated with the error
        error_code: Error code
        error_string: Error message
        timestamp: When the error occurred
        advanced_order_reject_json: Additional error details (optional)
    """
    
    def __init__(self, req_id: int, error_code: int, error_string: str, advanced_order_reject_json: str = ""):
        """
        Initialize a trading error.
        
        Args:
            req_id: Request ID (-1 for general errors)
            error_code: Error code
            error_string: Error message
            advanced_order_reject_json: Additional error details
        """
        self.req_id = req_id
        self.error_code = error_code
        self.error_string = error_string
        self.timestamp = datetime.now()
        self.advanced_order_reject_json = advanced_order_reject_json
        
    @property
    def is_info(self) -> bool:
        """Check if this is an informational message."""
        return self.error_code in ERROR_INFO
        
    @property
    def is_warning(self) -> bool:
        """Check if this is a warning."""
        return self.error_code in ERROR_WARNING
        
    @property
    def is_severe(self) -> bool:
        """Check if this is a severe error."""
        return self.error_code in ERROR_SEVERE
        
    @property
    def category(self) -> str:
        """Get the error category."""
        if self.is_info:
            return "info"
        elif self.is_warning:
            return "warning"
        else:
            return "severe"
            
    def is_connection_error(self) -> bool:
        """Check if this is a connection error."""
        return self.error_code == CONNECTION_ERROR
        
    def is_market_data_error(self) -> bool:
        """Check if this is a market data error."""
        return self.error_code == MARKET_DATA_ERROR
        
    def is_order_error(self) -> bool:
        """Check if this is an order error."""
        return self.error_code == ORDER_ERROR
        
    def __str__(self):
        """String representation."""
        return f"TradingError(reqId={self.req_id}, code={self.error_code}, message='{self.error_string}')"


class ErrorHandler:
    """
    Handles errors from the trading system.
    
    This class provides centralized error handling with:
    - Error categorization
    - Logging based on severity
    - Callback registration for custom error handling
    - Error history tracking
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the error handler.
        
        Args:
            max_history: Maximum number of errors to keep in history
        """
        self._callbacks: Dict[str, List[Callable[[TradingError], None]]] = {
            "any": [],
            "info": [],
            "warning": [],
            "severe": [],
            "connection": [],
            "market_data": [],
            "order": []
        }
        
        self._max_history = max_history
        self._error_history: List[TradingError] = []
        
    def handle_error(self, req_id: int, error_code: int, error_string: str, advanced_order_reject_json: str = ""):
        """
        Handle an error from the trading system.
        
        Args:
            req_id: Request ID (-1 for general errors)
            error_code: Error code
            error_string: Error message
            advanced_order_reject_json: Additional error details
        """
        error = TradingError(req_id, error_code, error_string, advanced_order_reject_json)
        
        # Log the error
        self._log_error(error)
        
        # Add to history
        self._add_to_history(error)
        
        # Call registered callbacks
        self._call_callbacks(error)
        
    def _log_error(self, error: TradingError):
        """
        Log error based on severity.
        
        Args:
            error: The error to log
        """
        # Special handling for specific error codes
        if error.error_code in [2104, 2106, 2107, 2108]:
            # Market data connection status messages
            logger.info(f"Trading Info: {error}")
        elif error.error_code in [2119, 2100]:
            # API connection status
            logger.warning(f"Trading Warning: {error}")
        elif error.error_code == 502:
            # Connection error
            logger.error(f"Trading Severe Error: {error}")
        else:
            # Log based on category
            if error.is_info:
                logger.info(f"Trading: {error}")
            elif error.is_warning:
                logger.warning(f"Trading: {error}")
            else:
                logger.error(f"Trading: {error}")
                
    def _add_to_history(self, error: TradingError):
        """
        Add error to history.
        
        Args:
            error: The error to add
        """
        self._error_history.append(error)
        
        # Trim history if needed
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]
            
    def _call_callbacks(self, error: TradingError):
        """
        Call registered callbacks for this error.
        
        Args:
            error: The error to process
        """
        # Call "any" callbacks
        for callback in self._callbacks["any"]:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
                
        # Call category-specific callbacks
        category = error.category
        for callback in self._callbacks.get(category, []):
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in {category} callback: {e}")
                
        # Call specific error type callbacks
        if error.is_connection_error():
            for callback in self._callbacks["connection"]:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"Error in connection callback: {e}")
                    
        if error.is_market_data_error():
            for callback in self._callbacks["market_data"]:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"Error in market data callback: {e}")
                    
        if error.is_order_error():
            for callback in self._callbacks["order"]:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"Error in order callback: {e}")
                    
    def register_callback(self, callback: Callable[[TradingError], None], category: str = "any"):
        """
        Register a callback for error handling.
        
        Args:
            callback: Function to call when an error occurs
            category: Error category to register for ("any", "info", "warning", "severe", 
                     "connection", "market_data", "order")
        """
        if category not in self._callbacks:
            raise ValueError(f"Invalid category: {category}")
            
        if callback not in self._callbacks[category]:
            self._callbacks[category].append(callback)
            
    def unregister_callback(self, callback: Callable[[TradingError], None], category: str = "any"):
        """
        Unregister a callback.
        
        Args:
            callback: Function to unregister
            category: Category to unregister from
        """
        if category in self._callbacks and callback in self._callbacks[category]:
            self._callbacks[category].remove(callback)
            
    def get_error_history(self) -> List[TradingError]:
        """
        Get error history.
        
        Returns:
            List of recent errors
        """
        return list(self._error_history)
        
    def clear_history(self):
        """Clear error history."""
        self._error_history.clear()
        
    def get_last_error(self) -> Optional[TradingError]:
        """
        Get the most recent error.
        
        Returns:
            Most recent error or None
        """
        return self._error_history[-1] if self._error_history else None