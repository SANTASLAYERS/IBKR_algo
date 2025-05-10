#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the subscription manager.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from src.subscription_manager import SubscriptionManager
from ibapi.contract import Contract


class TestSubscriptionManager:
    """Tests for the SubscriptionManager class."""

    @pytest.fixture
    def mock_gateway(self):
        """Create a mock gateway for testing."""
        gateway = MagicMock()
        gateway.subscribe_market_data = MagicMock(return_value=1001)
        gateway.unsubscribe_market_data = MagicMock()
        gateway.register_connected_callback = MagicMock()
        gateway.register_disconnected_callback = MagicMock()
        return gateway
    
    @pytest.fixture
    def subscription_manager(self, mock_gateway):
        """Create a subscription manager for testing."""
        manager = SubscriptionManager(mock_gateway)
        return manager
    
    @pytest.fixture
    def test_contract(self):
        """Create a test contract for testing."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    def test_init(self, mock_gateway):
        """Test initialization of the subscription manager."""
        manager = SubscriptionManager(mock_gateway)
        
        # Check that callbacks are registered
        mock_gateway.register_connected_callback.assert_called_once()
        mock_gateway.register_disconnected_callback.assert_called_once()
        
        # Check initial state
        assert isinstance(manager.active_subscriptions, dict)
        assert isinstance(manager.subscription_ids, dict)
        assert len(manager.active_subscriptions) == 0
        assert len(manager.subscription_ids) == 0
        assert manager._reconnecting is False
    
    def test_subscribe(self, subscription_manager, test_contract):
        """Test subscribing to market data."""
        # Create a callback
        callback = MagicMock()
        
        # Subscribe
        req_id = subscription_manager.subscribe(test_contract, callback)
        
        # Check that gateway.subscribe_market_data was called
        subscription_manager.gateway.subscribe_market_data.assert_called_once()
        
        # Check that subscription was added to active_subscriptions
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        assert symbol_key in subscription_manager.active_subscriptions
        assert subscription_manager.active_subscriptions[symbol_key]["contract"] == test_contract
        assert subscription_manager.active_subscriptions[symbol_key]["callback"] == callback
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is True
        assert subscription_manager.active_subscriptions[symbol_key]["req_id"] == req_id
        
        # Check that req_id was added to subscription_ids
        assert req_id in subscription_manager.subscription_ids
        assert subscription_manager.subscription_ids[req_id] == symbol_key
    
    def test_unsubscribe(self, subscription_manager, test_contract):
        """Test unsubscribing from market data."""
        # First subscribe
        callback = MagicMock()
        req_id = subscription_manager.subscribe(test_contract, callback)
        
        # Reset mock to check unsubscribe call
        subscription_manager.gateway.unsubscribe_market_data.reset_mock()
        
        # Get symbol key
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        
        # Unsubscribe
        result = subscription_manager.unsubscribe(symbol_key)
        
        # Check result
        assert result is True
        
        # Check that gateway.unsubscribe_market_data was called
        subscription_manager.gateway.unsubscribe_market_data.assert_called_once_with(req_id)
        
        # Check that subscription was removed from active_subscriptions
        assert symbol_key not in subscription_manager.active_subscriptions
        
        # Check that req_id was removed from subscription_ids
        assert req_id not in subscription_manager.subscription_ids
        
        # Test unsubscribing from non-existent subscription
        result = subscription_manager.unsubscribe("NONEXISTENT")
        assert result is False
        # No additional call to unsubscribe_market_data
        assert subscription_manager.gateway.unsubscribe_market_data.call_count == 1
    
    def test_unsubscribe_all(self, subscription_manager, test_contract):
        """Test unsubscribing from all market data."""
        # Create multiple subscriptions
        callback = MagicMock()
        
        contract1 = test_contract
        contract2 = Contract()
        contract2.symbol = "MSFT"
        contract2.secType = "STK"
        contract2.exchange = "SMART"
        contract2.currency = "USD"
        
        subscription_manager.subscribe(contract1, callback)
        subscription_manager.subscribe(contract2, callback)
        
        # Reset mock to check unsubscribe calls
        subscription_manager.gateway.unsubscribe_market_data.reset_mock()
        
        # Unsubscribe all
        subscription_manager.unsubscribe_all()
        
        # Check that gateway.unsubscribe_market_data was called twice
        assert subscription_manager.gateway.unsubscribe_market_data.call_count == 2
        
        # Check that no subscriptions remain
        assert len(subscription_manager.active_subscriptions) == 0
        assert len(subscription_manager.subscription_ids) == 0
    
    def test_is_subscribed(self, subscription_manager, test_contract):
        """Test checking if a symbol is subscribed."""
        # First subscribe
        callback = MagicMock()
        subscription_manager.subscribe(test_contract, callback)
        
        # Get symbol key
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        
        # Check if subscribed
        assert subscription_manager.is_subscribed(symbol_key) is True
        
        # Check a non-existent subscription
        assert subscription_manager.is_subscribed("NONEXISTENT") is False
        
        # Check an inactive subscription
        subscription_manager.active_subscriptions[symbol_key]["active"] = False
        assert subscription_manager.is_subscribed(symbol_key) is False
    
    def test_get_subscription_count(self, subscription_manager, test_contract):
        """Test getting the number of active subscriptions."""
        # Initial count should be 0
        assert subscription_manager.get_subscription_count() == 0
        
        # Add a subscription
        callback = MagicMock()
        subscription_manager.subscribe(test_contract, callback)
        
        # Count should be 1
        assert subscription_manager.get_subscription_count() == 1
        
        # Add another subscription
        contract2 = Contract()
        contract2.symbol = "MSFT"
        contract2.secType = "STK"
        contract2.exchange = "SMART"
        contract2.currency = "USD"
        
        subscription_manager.subscribe(contract2, callback)
        
        # Count should be 2
        assert subscription_manager.get_subscription_count() == 2
    
    def test_get_subscription_symbols(self, subscription_manager, test_contract):
        """Test getting the list of subscribed symbols."""
        # Initial list should be empty
        assert subscription_manager.get_subscription_symbols() == []
        
        # Add a subscription
        callback = MagicMock()
        subscription_manager.subscribe(test_contract, callback)
        
        # List should contain one symbol key
        symbols = subscription_manager.get_subscription_symbols()
        assert len(symbols) == 1
        assert symbols[0] == subscription_manager._create_symbol_key(test_contract)
        
        # Add another subscription
        contract2 = Contract()
        contract2.symbol = "MSFT"
        contract2.secType = "STK"
        contract2.exchange = "SMART"
        contract2.currency = "USD"
        
        subscription_manager.subscribe(contract2, callback)
        
        # List should contain two symbol keys
        symbols = subscription_manager.get_subscription_symbols()
        assert len(symbols) == 2
        assert subscription_manager._create_symbol_key(test_contract) in symbols
        assert subscription_manager._create_symbol_key(contract2) in symbols
    
    def test_create_symbol_key(self, subscription_manager):
        """Test creating a symbol key."""
        # Test stock
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        key = subscription_manager._create_symbol_key(contract)
        assert key == "AAPL_STK_SMART_USD"
        
        # Test option
        option_contract = Contract()
        option_contract.symbol = "SPY"
        option_contract.secType = "OPT"
        option_contract.exchange = "SMART"
        option_contract.currency = "USD"
        option_contract.lastTradeDateOrContractMonth = "20230721"
        option_contract.strike = 400.0
        option_contract.right = "C"
        
        key = subscription_manager._create_symbol_key(option_contract)
        assert key == "SPY_OPT_20230721_400.0_C_SMART_USD"
        
        # Test future
        future_contract = Contract()
        future_contract.symbol = "ES"
        future_contract.secType = "FUT"
        future_contract.exchange = "CME"
        future_contract.currency = "USD"
        future_contract.lastTradeDateOrContractMonth = "202309"
        
        key = subscription_manager._create_symbol_key(future_contract)
        assert key == "ES_FUT_202309_CME_USD"
    
    def test_create_callback_wrapper(self, subscription_manager, test_contract):
        """Test creating a callback wrapper."""
        # Create a mock callback
        original_callback = MagicMock()
        
        # Get symbol key
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        
        # Create wrapper
        wrapped_callback = subscription_manager._create_callback_wrapper(symbol_key, original_callback)
        
        # Test wrapper with normal data
        data = {"last_price": 150.0, "bid_price": 149.5, "ask_price": 150.5}
        wrapped_callback(data)
        
        # Original callback should be called once with data
        original_callback.assert_called_once_with(data)
        original_callback.reset_mock()
        
        # Test wrapper with error data - should still call original callback
        error_data = {"error": "Subscription not found", "error_code": 10225}
        wrapped_callback(error_data)
        
        # Original callback should be called with error data
        original_callback.assert_called_once_with(error_data)
        
        # Add a subscription to test error handling
        subscription_manager.active_subscriptions[symbol_key] = {
            "contract": test_contract,
            "callback": original_callback,
            "active": True,
            "req_id": 1001
        }
        subscription_manager.subscription_ids[1001] = symbol_key
        
        # Test wrapper with subscription invalidation error
        invalidation_error = {"error": "Subscription invalidated", "error_code": 10225}
        wrapped_callback(invalidation_error)
        
        # Subscription should be marked as inactive
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is False
        
        # req_id should be removed from subscription_ids
        assert 1001 not in subscription_manager.subscription_ids
    
    @pytest.mark.asyncio
    async def test_on_connection_restored(self, subscription_manager, test_contract):
        """Test handling connection restored event."""
        # Setup a subscription
        callback = MagicMock()
        req_id = subscription_manager.subscribe(test_contract, callback)
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        
        # Initial call
        subscription_manager.gateway.subscribe_market_data.reset_mock()
        
        # Only resubscribe if reconnecting flag is True
        subscription_manager._reconnecting = False
        await subscription_manager._on_connection_restored()
        
        # Should not resubscribe if not reconnecting
        subscription_manager.gateway.subscribe_market_data.assert_not_called()
        
        # Set reconnecting flag and try again
        subscription_manager._reconnecting = True
        
        # Reset subscription to inactive
        subscription_manager.active_subscriptions[symbol_key]["active"] = False
        
        # Call the on_connection_restored method
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await subscription_manager._on_connection_restored()
        
        # Should resubscribe
        subscription_manager.gateway.subscribe_market_data.assert_called_once()
        
        # Should set subscription to active with new req_id
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is True
        
        # Should sleep to avoid flooding
        mock_sleep.assert_called_once()
    
    def test_on_connection_lost(self, subscription_manager, test_contract):
        """Test handling connection lost event."""
        # Setup a subscription
        callback = MagicMock()
        req_id = subscription_manager.subscribe(test_contract, callback)
        symbol_key = subscription_manager._create_symbol_key(test_contract)
        
        # Call the on_connection_lost method
        subscription_manager._on_connection_lost()
        
        # Should set reconnecting flag
        assert subscription_manager._reconnecting is True
        
        # Should mark subscription as inactive
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is False
        
        # Should clear subscription_ids
        assert len(subscription_manager.subscription_ids) == 0
        
        # Calling again should do nothing (already reconnecting)
        subscription_manager.active_subscriptions[symbol_key]["active"] = True
        subscription_manager._on_connection_lost()
        
        # Should still be active (since we're already in reconnecting state)
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is True