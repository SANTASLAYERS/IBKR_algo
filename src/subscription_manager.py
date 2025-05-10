#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Subscription manager for maintaining market data subscriptions across reconnections.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Union, Callable, Any

from ibapi.contract import Contract

from .logger import get_logger

logger = get_logger(__name__)

class SubscriptionManager:
    """
    Manages market data subscriptions and handles reconnection scenarios by automatically
    resubscribing to lost subscriptions when the connection is restored.
    """
    
    def __init__(self, gateway):
        """
        Initialize the subscription manager with a gateway instance.
        
        Args:
            gateway: IBGateway instance
        """
        self.gateway = gateway
        self.active_subscriptions: Dict[str, Dict[str, Any]] = {}  # Symbol -> subscription details
        self.subscription_ids: Dict[int, str] = {}  # Request ID -> Symbol
        
        # Register for gateway connection events
        self.gateway.register_connected_callback(self._on_connection_restored)
        self.gateway.register_disconnected_callback(self._on_connection_lost)
        
        # Used to limit log messages during reconnection
        self._reconnecting = False
    
    def subscribe(
        self, 
        contract: Contract, 
        callback: Optional[Callable] = None,
        generic_tick_list: str = "", 
        snapshot: bool = False
    ) -> int:
        """
        Subscribe to market data for a contract with persistent reconnection handling.
        
        Args:
            contract: Contract to subscribe to
            callback: Optional callback function for market data updates
            generic_tick_list: Optional list of generic tick types
            snapshot: Whether to request a snapshot
            
        Returns:
            int: Request ID for the subscription
        """
        # Generate a unique symbol key
        symbol_key = self._create_symbol_key(contract)
        
        # Create subscription configuration
        subscription_config = {
            "contract": contract,
            "callback": callback,
            "generic_tick_list": generic_tick_list,
            "snapshot": snapshot,
            "active": False,
            "req_id": None,
        }
        
        # Store in our active subscriptions
        self.active_subscriptions[symbol_key] = subscription_config
        
        # Create a wrapper callback for data updates
        wrapped_callback = self._create_callback_wrapper(symbol_key, callback)
        
        # Subscribe to market data
        req_id = self.gateway.subscribe_market_data(
            contract,
            callback=wrapped_callback,
            generic_tick_list=generic_tick_list,
            snapshot=snapshot
        )
        
        # Update subscription with request ID
        subscription_config["req_id"] = req_id
        subscription_config["active"] = True
        self.subscription_ids[req_id] = symbol_key
        
        logger.info(f"Added persistent subscription for {symbol_key} with req_id: {req_id}")
        
        return req_id
    
    def unsubscribe(self, symbol_key: str) -> bool:
        """
        Unsubscribe from market data for a symbol.
        
        Args:
            symbol_key: Symbol key to unsubscribe from
            
        Returns:
            bool: True if unsubscribed, False if symbol not found
        """
        if symbol_key in self.active_subscriptions:
            subscription = self.active_subscriptions[symbol_key]
            req_id = subscription["req_id"]
            
            # Only unsubscribe if currently active
            if subscription["active"] and req_id is not None:
                self.gateway.unsubscribe_market_data(req_id)
                
                # Remove from subscription IDs mapping
                if req_id in self.subscription_ids:
                    del self.subscription_ids[req_id]
            
            # Remove from active subscriptions
            del self.active_subscriptions[symbol_key]
            logger.info(f"Removed subscription for {symbol_key}")
            
            return True
        else:
            logger.warning(f"No subscription found for {symbol_key}")
            return False
    
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all market data subscriptions."""
        symbols = list(self.active_subscriptions.keys())
        for symbol_key in symbols:
            self.unsubscribe(symbol_key)
        
        logger.info(f"Unsubscribed from all {len(symbols)} subscriptions")
    
    def is_subscribed(self, symbol_key: str) -> bool:
        """
        Check if a symbol is currently subscribed.
        
        Args:
            symbol_key: Symbol key to check
            
        Returns:
            bool: True if subscribed, False otherwise
        """
        return symbol_key in self.active_subscriptions and self.active_subscriptions[symbol_key]["active"]
    
    def get_subscription_count(self) -> int:
        """
        Get the number of active subscriptions.
        
        Returns:
            int: Number of active subscriptions
        """
        return len(self.active_subscriptions)
    
    def get_subscription_symbols(self) -> List[str]:
        """
        Get a list of currently subscribed symbols.
        
        Returns:
            List[str]: List of subscribed symbol keys
        """
        return list(self.active_subscriptions.keys())
    
    def _create_symbol_key(self, contract: Contract) -> str:
        """
        Create a unique key for a contract.
        
        Args:
            contract: Contract to create key for
            
        Returns:
            str: Unique key for this contract
        """
        # Create basic key with symbol and secType
        key = f"{contract.symbol}_{contract.secType}"
        
        # Add additional details for derivatives
        if contract.secType in ["OPT", "FUT", "FOP"]:
            # Add expiry if available
            if hasattr(contract, "lastTradeDateOrContractMonth") and contract.lastTradeDateOrContractMonth:
                key += f"_{contract.lastTradeDateOrContractMonth}"
                
            # Add strike and right for options
            if contract.secType in ["OPT", "FOP"]:
                if hasattr(contract, "strike") and contract.strike:
                    key += f"_{contract.strike}"
                if hasattr(contract, "right") and contract.right:
                    key += f"_{contract.right}"
        
        # Add exchange and currency
        key += f"_{contract.exchange}_{contract.currency}"
        
        return key
    
    def _create_callback_wrapper(self, symbol_key: str, original_callback: Optional[Callable]) -> Callable:
        """
        Create a wrapper around the original callback to track subscription status.
        
        Args:
            symbol_key: Symbol key for this subscription
            original_callback: Original callback function provided by the user
            
        Returns:
            Callable: Wrapped callback function
        """
        def wrapped_callback(data: Dict) -> None:
            # Pass the data to the original callback if provided
            if original_callback:
                try:
                    original_callback(data)
                except Exception as e:
                    logger.error(f"Error in market data callback for {symbol_key}: {str(e)}")
            
            # Check for error in market data
            if "error" in data:
                # Update subscription status if certain errors occur
                error_code = data.get("error_code", 0)
                
                # List of error codes that indicate the subscription is no longer valid
                invalid_subscription_errors = [10225, 10192, 10193, 200, 201, 203, 300, 301, 302, 303, 308, 354, 10167]
                
                if error_code in invalid_subscription_errors:
                    if symbol_key in self.active_subscriptions:
                        req_id = self.active_subscriptions[symbol_key].get("req_id")
                        logger.warning(f"Subscription for {symbol_key} invalid due to error {error_code}")
                        
                        # Mark subscription as inactive
                        self.active_subscriptions[symbol_key]["active"] = False
                        
                        # Clear from req_id mapping
                        if req_id in self.subscription_ids:
                            del self.subscription_ids[req_id]
        
        return wrapped_callback
    
    async def _on_connection_restored(self) -> None:
        """Handle connection restored event by resubscribing to all active subscriptions."""
        # Only process if we were previously reconnecting
        if not self._reconnecting:
            return
            
        logger.info(f"Connection restored, resubscribing to {len(self.active_subscriptions)} market data feeds")
        self._reconnecting = False
        
        # Create a copy of subscriptions to resubscribe
        subscriptions_to_restore = list(self.active_subscriptions.items())
        
        # Resubscribe to all market data feeds
        for symbol_key, subscription in subscriptions_to_restore:
            try:
                contract = subscription["contract"]
                callback = subscription["callback"]
                generic_tick_list = subscription["generic_tick_list"]
                snapshot = subscription["snapshot"]
                
                # Create wrapped callback
                wrapped_callback = self._create_callback_wrapper(symbol_key, callback)
                
                # Mark old subscription as inactive
                subscription["active"] = False
                
                # Subscribe with the same parameters
                req_id = self.gateway.subscribe_market_data(
                    contract,
                    callback=wrapped_callback,
                    generic_tick_list=generic_tick_list,
                    snapshot=snapshot
                )
                
                # Update subscription with new request ID
                subscription["req_id"] = req_id
                subscription["active"] = True
                self.subscription_ids[req_id] = symbol_key
                
                logger.info(f"Resubscribed to {symbol_key} with new req_id: {req_id}")
                
                # Small delay to avoid flooding the connection
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error resubscribing to {symbol_key}: {str(e)}")
    
    def _on_connection_lost(self) -> None:
        """Handle connection lost event by marking all subscriptions as inactive."""
        if not self._reconnecting:
            logger.info(f"Connection lost, marked {len(self.active_subscriptions)} subscriptions as pending resubscription")
            self._reconnecting = True
            
            # Mark all subscriptions as inactive
            for symbol_key, subscription in self.active_subscriptions.items():
                subscription["active"] = False
            
            # Clear request ID mappings
            self.subscription_ids.clear()