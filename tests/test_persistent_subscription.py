#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integration tests for persistent subscription functionality.
"""

import pytest
import asyncio
import argparse
from unittest.mock import MagicMock, patch, AsyncMock

from src.gateway import IBGateway, IBGatewayConfig
from src.subscription_manager import SubscriptionManager
from src.error_handler import ErrorHandler
from ibapi.contract import Contract

# Import the CLI functions to test
from gateway_cli import (
    create_contract,
    subscribe_persistent_market_data,
    unsubscribe_market_data,
    list_subscriptions,
    shutdown
)


class TestPersistentSubscriptionIntegration:
    """Integration tests for persistent subscriptions in gateway CLI."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock gateway configuration."""
        return IBGatewayConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="U12345",
            read_only=True,
            heartbeat_timeout=0.5,
            heartbeat_interval=0.2,
            reconnect_delay=0.1,
            max_reconnect_attempts=3
        )
    
    @pytest.fixture
    def mock_error_handler(self):
        """Create a mock error handler."""
        return MagicMock(spec=ErrorHandler)
    
    @pytest.fixture
    def mock_gateway(self, mock_config, mock_error_handler):
        """Create a mock gateway with stubbed methods."""
        with patch('src.gateway.IBKRConnection.__init__', return_value=None):
            gateway = IBGateway(mock_config, mock_error_handler)
            
            # Configure the mock gateway
            gateway.config = mock_config
            gateway.error_handler = mock_error_handler
            gateway.connection_state = "disconnected"
            gateway.heartbeat_monitor = MagicMock()
            gateway.on_connected_callbacks = []
            gateway.on_disconnected_callbacks = []
            gateway._reconnect_attempts = 0
            gateway._max_reconnect_attempts = mock_config.max_reconnect_attempts
            gateway._reconnect_delay = mock_config.reconnect_delay
            
            # Mock required methods
            gateway.connect_async = AsyncMock(return_value=True)
            gateway.disconnect = MagicMock()
            gateway.is_connected = MagicMock(return_value=True)
            gateway.reqHeartbeat = MagicMock()
            gateway.subscribe_market_data = MagicMock(return_value=1001)
            gateway.unsubscribe_market_data = MagicMock()
            gateway.register_connected_callback = MagicMock()
            gateway.register_disconnected_callback = MagicMock()
            gateway._market_data = {}
            
            return gateway
    
    @pytest.fixture
    def subscription_manager(self, mock_gateway):
        """Create a subscription manager for testing."""
        return SubscriptionManager(mock_gateway)
    
    @pytest.fixture
    def mock_args(self):
        """Create mock command-line arguments."""
        args = MagicMock(spec=argparse.Namespace)
        args.subscribe = "AAPL"
        args.watch = True
        args.duration = 5
        args.sec_type = "STK"
        args.exchange = "SMART"
        args.currency = "USD"
        args.expiry = None
        args.strike = None
        args.right = None
        args.local_symbol = None
        args.persistent = True
        args.unsubscribe = None
        args.log_level = "INFO"
        return args
    
    @pytest.mark.asyncio
    async def test_create_contract(self, mock_args):
        """Test creating a contract from arguments."""
        # Test stock contract
        contract = create_contract(mock_args, "AAPL")
        assert contract.symbol == "AAPL"
        assert contract.secType == "STK"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"
        
        # Test option contract
        mock_args.sec_type = "OPT"
        mock_args.expiry = "20230721"
        mock_args.strike = 400.0
        mock_args.right = "C"
        
        contract = create_contract(mock_args, "SPY")
        assert contract.symbol == "SPY"
        assert contract.secType == "OPT"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"
        assert contract.lastTradeDateOrContractMonth == "20230721"
        assert contract.strike == 400.0
        assert contract.right == "C"
        
        # Test with local symbol
        mock_args.local_symbol = "ESU3"
        mock_args.sec_type = "FUT"
        
        contract = create_contract(mock_args, "ES")
        assert contract.symbol == "ES"
        assert contract.secType == "FUT"
        assert contract.localSymbol == "ESU3"
    
    @pytest.mark.asyncio
    async def test_subscribe_persistent_market_data(self, mock_gateway, subscription_manager, mock_args):
        """Test subscribing to persistent market data."""
        # Test successful subscription
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await subscribe_persistent_market_data(mock_gateway, subscription_manager, mock_args)
        
        assert result is True
        
        # Check gateway methods called
        mock_gateway.connect_async.assert_called_once()
        mock_gateway.subscribe_market_data.assert_called_once()
        
        # Check subscription added
        assert len(subscription_manager.active_subscriptions) == 1
        
        # Check sleep called for duration
        mock_sleep.assert_called_once_with(mock_args.duration)
    
    @pytest.mark.asyncio
    async def test_unsubscribe_market_data(self, mock_gateway, subscription_manager, mock_args):
        """Test unsubscribing from market data."""
        # First subscribe
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await subscribe_persistent_market_data(mock_gateway, subscription_manager, mock_args)
        
        # Then unsubscribe
        mock_args.unsubscribe = "AAPL"
        result = await unsubscribe_market_data(mock_gateway, subscription_manager, mock_args)
        
        assert result is True
        
        # Check subscription removed
        assert len(subscription_manager.active_subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_list_subscriptions(self, mock_gateway, subscription_manager, mock_args):
        """Test listing subscriptions."""
        # First subscribe
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await subscribe_persistent_market_data(mock_gateway, subscription_manager, mock_args)
        
        # Then list
        with patch('builtins.print') as mock_print:
            result = await list_subscriptions(mock_gateway, subscription_manager, mock_args)
        
        assert result is True
        
        # Check print called with subscription info
        assert mock_print.call_count >= 3  # Header + separator + subscription line
    
    @pytest.mark.asyncio
    async def test_shutdown(self, mock_gateway, subscription_manager):
        """Test graceful shutdown."""
        # First add some subscriptions
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        subscription_manager.subscribe(contract, MagicMock())
        
        # Create a mock loop
        mock_loop = MagicMock()
        
        # Setup some mock tasks
        mock_tasks = [MagicMock(), MagicMock()]
        
        # Test shutdown
        with patch('asyncio.all_tasks', return_value=mock_tasks), \
             patch('asyncio.gather', new_callable=AsyncMock):
            await shutdown(mock_gateway, subscription_manager, mock_loop)
        
        # Check unsubscribe_all called
        assert len(subscription_manager.active_subscriptions) == 0
        
        # Check gateway disconnected
        mock_gateway.disconnect.assert_called_once()
        
        # Check tasks cancelled
        for task in mock_tasks:
            task.cancel.assert_called_once()
        
        # Check loop stopped
        mock_loop.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconnection_handling(self, mock_gateway, subscription_manager, mock_args):
        """Test reconnection handling for subscriptions."""
        # First subscribe
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await subscribe_persistent_market_data(mock_gateway, subscription_manager, mock_args)
        
        # Check initial state
        symbol_key = next(iter(subscription_manager.active_subscriptions.keys()))
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is True
        
        # Simulate connection loss
        subscription_manager._on_connection_lost()
        
        # Check state after connection loss
        assert subscription_manager._reconnecting is True
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is False
        assert len(subscription_manager.subscription_ids) == 0
        
        # Simulate connection restoration
        mock_gateway.subscribe_market_data.reset_mock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await subscription_manager._on_connection_restored()
        
        # Check state after connection restoration
        assert subscription_manager._reconnecting is False
        assert subscription_manager.active_subscriptions[symbol_key]["active"] is True
        assert len(subscription_manager.subscription_ids) == 1
        
        # Check resubscription
        mock_gateway.subscribe_market_data.assert_called_once()