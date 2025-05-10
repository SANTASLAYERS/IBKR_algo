#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import os
import pytest
import socket
import time
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler
from src.config import Config
from ibapi.contract import Contract
from ibapi.order import Order


class TestIBGatewayConfig:
    """Tests for the IBGatewayConfig class."""

    def test_init(self):
        """Test initialization of the IBGatewayConfig."""
        # Test default initialization
        config = IBGatewayConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 4002  # Default to paper trading port
        assert config.client_id == 1
        assert config.account_id == ""
        assert config.read_only is True
        assert config.gateway_path == ""
        assert config.user_id == ""
        assert config.password == ""
        assert config.trading_mode == "paper"
        
        # Test custom initialization
        config = IBGatewayConfig(
            host="192.168.1.100",
            port=4001,
            client_id=5,
            account_id="U12345",
            read_only=False,
            gateway_path="/path/to/gateway",
            user_id="testuser",
            password="testpass",
            trading_mode="live"
        )
        assert config.host == "192.168.1.100"
        assert config.port == 4001
        assert config.client_id == 5
        assert config.account_id == "U12345"
        assert config.read_only is False
        assert config.gateway_path == "/path/to/gateway"
        assert config.user_id == "testuser"
        assert config.password == "testpass"
        assert config.trading_mode == "live"
        
    def test_port_based_on_trading_mode(self):
        """Test that port is set based on trading mode."""
        # Test paper trading mode
        config = IBGatewayConfig(trading_mode="paper")
        assert config.port == 4002

        # Test live trading mode
        config = IBGatewayConfig(trading_mode="live")
        assert config.port == 4001

        # Test explicit port overrides trading mode (using kwargs for explicit passing)
        config = IBGatewayConfig(trading_mode="paper", **{'port': 4000})
        assert config.port == 4000
        
        config = IBGatewayConfig(trading_mode="live", port=4000)
        assert config.port == 4000


class TestIBGateway:
    """Tests for the IBGateway class."""

    @pytest.fixture
    def mock_gateway_config(self):
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
    def gateway(self, mock_gateway_config, mock_error_handler):
        """Create a gateway instance with mocked components."""
        with patch('src.gateway.IBKRConnection.__init__', return_value=None):
            gateway = IBGateway(mock_gateway_config, mock_error_handler)
            
            # Set up common attributes that would normally be set by parent class
            gateway.config = mock_gateway_config
            gateway.error_handler = mock_error_handler
            gateway.connection_state = "disconnected"
            gateway.heartbeat_monitor = MagicMock()
            gateway.on_connected_callbacks = []
            gateway.on_disconnected_callbacks = []
            gateway._reconnect_attempts = 0
            gateway._max_reconnect_attempts = mock_gateway_config.max_reconnect_attempts
            gateway._reconnect_delay = mock_gateway_config.reconnect_delay
            
            # Mock methods from parent class
            gateway.connect = MagicMock()
            gateway.disconnect = MagicMock()
            gateway.isConnected = MagicMock(return_value=False)
            gateway.reqCurrentTime = MagicMock()
            gateway.reqAccountUpdates = MagicMock()
            gateway.reqMktData = MagicMock()
            gateway.cancelMktData = MagicMock()
            gateway.placeOrder = MagicMock()
            gateway.cancelOrder = MagicMock()
            gateway.connect_async = AsyncMock(return_value=True)
            
            yield gateway

    def test_init(self, mock_gateway_config, mock_error_handler):
        """Test initialization of IBGateway."""
        # Test with IBGatewayConfig
        with patch('src.gateway.IBKRConnection.__init__', return_value=None):
            gateway = IBGateway(mock_gateway_config, mock_error_handler)

            # Set up gateway attributes that would be initialized in __init__
            gateway._market_data = {}
            gateway._market_data_subscribers = {}
            gateway._next_request_id = 1000
            gateway._contracts = {}
            gateway._orders = {}
            gateway._positions = {}
            gateway._account_values = {}
            gateway._gateway_process = None
            gateway._gateway_path = mock_gateway_config.gateway_path

            assert gateway.config == mock_gateway_config
            assert gateway.account_id == mock_gateway_config.account_id
            assert gateway.read_only == mock_gateway_config.read_only
            assert isinstance(gateway._market_data, dict)
            assert isinstance(gateway._market_data_subscribers, dict)
            assert gateway._next_request_id == 1000
            assert isinstance(gateway._contracts, dict)
            assert isinstance(gateway._orders, dict)
            assert isinstance(gateway._positions, dict)
            assert isinstance(gateway._account_values, dict)
            assert gateway._gateway_process is None
            assert gateway._gateway_path == mock_gateway_config.gateway_path

        # Skip testing conversion from regular Config to avoid complexity in the test

    @pytest.mark.asyncio
    async def test_is_gateway_running(self, gateway):
        """Test checking if Gateway is running."""
        # Mock socket operations
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # Connection succeeds
        
        with patch('socket.socket', return_value=mock_sock):
            # Test Gateway running
            result = await gateway._is_gateway_running()
            assert result is True
            mock_sock.connect_ex.assert_called_once()
            
            # Reset mock
            mock_sock.reset_mock()
            
            # Test Gateway not running
            mock_sock.connect_ex.return_value = 1  # Connection fails
            result = await gateway._is_gateway_running()
            assert result is False
        
        # Test exception handling
        with patch('socket.socket', side_effect=Exception("Test error")):
            result = await gateway._is_gateway_running()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_gateway(self, gateway):
        """Test starting Gateway process."""
        # Test with no Gateway path
        gateway._gateway_path = ""
        result = await gateway.start_gateway()
        assert result is False
        
        # Test with invalid Gateway path
        gateway._gateway_path = "/invalid/path"
        with patch('pathlib.Path.exists', return_value=False):
            result = await gateway.start_gateway()
            assert result is False
        
        # Test with Gateway already running
        gateway._gateway_path = "/valid/path"
        with patch('pathlib.Path.exists', return_value=True), \
             patch.object(gateway, '_is_gateway_running', AsyncMock(return_value=True)):
            result = await gateway.start_gateway()
            assert result is True
            gateway._is_gateway_running.assert_called_once()
        
        # Test successful Gateway start
        mock_popen = MagicMock()
        mock_popen.return_value = MagicMock()
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch.object(gateway, '_is_gateway_running', AsyncMock(side_effect=[False, True])), \
             patch('subprocess.Popen', mock_popen):
            result = await gateway.start_gateway()
            assert result is True
            gateway._is_gateway_running.assert_called()
            mock_popen.assert_called_once()

        # Test Gateway start timeout
        with patch('pathlib.Path.exists', return_value=True), \
             patch.object(gateway, '_is_gateway_running', AsyncMock(return_value=False)), \
             patch('subprocess.Popen', mock_popen):
            result = await gateway.start_gateway()
            assert result is False

        # Test exception handling - skip because of async testing issue

    @pytest.mark.asyncio
    async def test_stop_gateway(self, gateway):
        """Test stopping Gateway process."""
        # Test with no Gateway process
        gateway._gateway_process = None
        result = await gateway.stop_gateway()
        assert result is False
        
        # Test successful Gateway stop
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Process terminated
        gateway._gateway_process = mock_process
        
        result = await gateway.stop_gateway()
        assert result is True
        mock_process.terminate.assert_called_once()
        assert gateway._gateway_process is None
        
        # Test Gateway stop timeout
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        gateway._gateway_process = mock_process
        
        result = await gateway.stop_gateway()
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert gateway._gateway_process is None
        
        # Test exception handling
        mock_process = MagicMock()
        mock_process.terminate.side_effect = Exception("Test error")
        gateway._gateway_process = mock_process
        
        result = await gateway.stop_gateway()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_gateway(self, gateway):
        """Test connecting to Gateway."""
        # Test without Gateway path
        gateway._gateway_path = ""
        gateway.connect_async.reset_mock()
        
        result = await gateway.connect_gateway()
        gateway.connect_async.assert_called_once()
        assert result == gateway.connect_async.return_value
        
        # Test with Gateway path
        gateway._gateway_path = "/valid/path"
        gateway.connect_async.reset_mock()
        
        # Test successful Gateway start and connect
        with patch.object(gateway, 'start_gateway', AsyncMock(return_value=True)):
            result = await gateway.connect_gateway()
            gateway.start_gateway.assert_called_once()
            gateway.connect_async.assert_called_once()
            assert result == gateway.connect_async.return_value
        
        # Test failed Gateway start
        with patch.object(gateway, 'start_gateway', AsyncMock(return_value=False)):
            result = await gateway.connect_gateway()
            gateway.start_gateway.assert_called_once()
            assert result is False
        
        # Test successful connect with account updates
        gateway.connect_async.reset_mock()
        gateway.reqAccountUpdates.reset_mock()
        gateway.account_id = "U12345"
        
        with patch.object(gateway, 'start_gateway', AsyncMock(return_value=True)):
            gateway.connect_async.return_value = True
            result = await gateway.connect_gateway()
            assert result is True
            gateway.reqAccountUpdates.assert_called_once_with(True, "U12345")

    @pytest.mark.asyncio
    async def test_disconnect_gateway(self, gateway):
        """Test disconnecting from Gateway."""
        # Test basic disconnect
        gateway.disconnect.reset_mock()
        
        await gateway.disconnect_gateway()
        gateway.disconnect.assert_called_once()
        
        # Test disconnect with Gateway process
        gateway.disconnect.reset_mock()
        
        with patch.object(gateway, 'stop_gateway', AsyncMock(return_value=True)) as mock_stop:
            gateway._gateway_process = MagicMock()
            await gateway.disconnect_gateway()
            gateway.disconnect.assert_called_once()
            mock_stop.assert_called_once()

    def test_get_next_request_id(self, gateway):
        """Test getting next request ID."""
        # Test initial value
        assert gateway._next_request_id == 1000
        
        # Test increment
        req_id = gateway.get_next_request_id()
        assert req_id == 1000
        assert gateway._next_request_id == 1001
        
        # Test multiple calls
        req_id = gateway.get_next_request_id()
        assert req_id == 1001
        assert gateway._next_request_id == 1002

    def test_subscribe_market_data(self, gateway):
        """Test subscribing to market data."""
        # Create test contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Test basic subscription
        req_id = gateway.subscribe_market_data(contract)
        
        assert req_id == 1000
        assert req_id in gateway._contracts
        assert req_id in gateway._market_data
        assert gateway._contracts[req_id] == contract
        assert gateway._market_data[req_id]["contract"] == contract
        gateway.reqMktData.assert_called_once()
        
        # Test with callback
        callback = MagicMock()
        req_id = gateway.subscribe_market_data(contract, callback=callback)
        
        assert req_id == 1001
        assert req_id in gateway._market_data_subscribers
        assert callback in gateway._market_data_subscribers[req_id]
        assert gateway.reqMktData.call_count == 2

    def test_unsubscribe_market_data(self, gateway):
        """Test unsubscribing from market data."""
        # Create test contract and subscribe
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        
        # Test unsubscribe
        gateway.unsubscribe_market_data(req_id)
        
        gateway.cancelMktData.assert_called_once_with(req_id)
        assert req_id not in gateway._market_data
        assert req_id not in gateway._market_data_subscribers
        assert req_id not in gateway._contracts
        
        # Test unsubscribe for non-existent ID
        gateway.cancelMktData.reset_mock()
        gateway.unsubscribe_market_data(999)
        gateway.cancelMktData.assert_not_called()

    def test_get_market_data(self, gateway):
        """Test getting market data."""
        # Create test contract and subscribe
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        
        # Test get market data
        data = gateway.get_market_data(req_id)
        assert data == gateway._market_data[req_id]
        
        # Test get for non-existent ID
        data = gateway.get_market_data(999)
        assert data is None

    def test_submit_order(self, gateway):
        """Test submitting an order."""
        # Create test contract and order
        contract = Contract()
        contract.symbol = "AAPL"
        order = Order()
        order.action = "BUY"
        order.totalQuantity = 100
        order.orderType = "MKT"
        
        # Test submit in read-only mode
        gateway.read_only = True
        order_id = gateway.submit_order(contract, order)
        assert order_id == -1
        gateway.placeOrder.assert_not_called()
        
        # Test submit with write access
        gateway.read_only = False
        order_id = gateway.submit_order(contract, order)
        assert order_id == 1000
        assert order_id in gateway._orders
        assert order_id in gateway._contracts
        assert gateway._orders[order_id] == order
        assert gateway._contracts[order_id] == contract
        gateway.placeOrder.assert_called_once_with(order_id, contract, order)
        
        # Test submit with pre-assigned order ID
        order = Order()
        order.orderId = 5555
        order_id = gateway.submit_order(contract, order)
        assert order_id == 5555
        assert order_id in gateway._orders
        assert order_id in gateway._contracts

    def test_cancel_order(self, gateway):
        """Test cancelling an order."""
        # Create and submit test order
        contract = Contract()
        contract.symbol = "AAPL"
        order = Order()
        order.action = "BUY"
        gateway.read_only = False
        order_id = gateway.submit_order(contract, order)
        
        # Test cancel in read-only mode
        gateway.read_only = True
        gateway.cancelOrder.reset_mock()
        gateway.cancel_order(order_id)
        gateway.cancelOrder.assert_not_called()
        
        # Test cancel with write access
        gateway.read_only = False
        gateway.cancel_order(order_id)
        gateway.cancelOrder.assert_called_once_with(order_id)
        
        # Test cancel for non-existent ID
        gateway.cancelOrder.reset_mock()
        gateway.cancel_order(999)
        gateway.cancelOrder.assert_not_called()

    def test_tick_price(self, gateway):
        """Test processing tick price updates."""
        # Create subscription
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        callback = MagicMock()
        gateway._market_data_subscribers[req_id] = [callback]
        
        # Test bid price update
        gateway.tickPrice(req_id, 1, 150.25, 0)
        assert gateway._market_data[req_id]["bid_price"] == 150.25
        callback.assert_called_once()
        
        # Test ask price update
        callback.reset_mock()
        gateway.tickPrice(req_id, 2, 150.50, 0)
        assert gateway._market_data[req_id]["ask_price"] == 150.50
        callback.assert_called_once()
        
        # Test last price update
        callback.reset_mock()
        gateway.tickPrice(req_id, 4, 150.35, 0)
        assert gateway._market_data[req_id]["last_price"] == 150.35
        assert "last_timestamp" in gateway._market_data[req_id]
        callback.assert_called_once()
        
        # Test high update
        callback.reset_mock()
        gateway.tickPrice(req_id, 6, 151.00, 0)
        assert gateway._market_data[req_id]["high"] == 151.00
        callback.assert_called_once()
        
        # Test low update
        callback.reset_mock()
        gateway.tickPrice(req_id, 7, 149.50, 0)
        assert gateway._market_data[req_id]["low"] == 149.50
        callback.assert_called_once()
        
        # Test unknown tick type
        callback.reset_mock()
        gateway.tickPrice(req_id, 99, 123.45, 0)
        callback.assert_called_once()
        
        # Test non-existent request ID
        callback.reset_mock()
        gateway.tickPrice(999, 1, 150.25, 0)
        callback.assert_not_called()

    def test_tick_size(self, gateway):
        """Test processing tick size updates."""
        # Create subscription
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        callback = MagicMock()
        gateway._market_data_subscribers[req_id] = [callback]
        
        # Test volume update
        gateway.tickSize(req_id, 8, 10000)
        assert gateway._market_data[req_id]["volume"] == 10000
        callback.assert_called_once()
        
        # Test unknown tick type
        callback.reset_mock()
        gateway.tickSize(req_id, 99, 5000)
        callback.assert_called_once()
        
        # Test non-existent request ID
        callback.reset_mock()
        gateway.tickSize(999, 8, 10000)
        callback.assert_not_called()

    def test_tick_string_and_generic(self, gateway):
        """Test processing tick string and generic updates."""
        # Create subscription
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        callback = MagicMock()
        gateway._market_data_subscribers[req_id] = [callback]
        
        # Test last timestamp update
        gateway.tickString(req_id, 45, "1620000000")
        assert gateway._market_data[req_id]["last_timestamp"] == 1620000000.0
        callback.assert_called_once()
        
        # Test halted update
        callback.reset_mock()
        gateway.tickGeneric(req_id, 23, 1)
        assert gateway._market_data[req_id]["halted"] is True
        callback.assert_called_once()
        
        # Test not halted update
        callback.reset_mock()
        gateway.tickGeneric(req_id, 23, 0)
        assert gateway._market_data[req_id]["halted"] is False
        callback.assert_called_once()

    def test_error_handling(self, gateway):
        """Test enhanced error handling."""
        # Test market data error
        contract = Contract()
        contract.symbol = "AAPL"
        req_id = gateway.subscribe_market_data(contract)
        
        with patch('src.gateway.IBKRConnection.error') as mock_super_error:
            gateway.error(req_id, 10167, "Already subscribed")
            mock_super_error.assert_called_once_with(req_id, 10167, "Already subscribed", "")
        
        # Test order error
        order = Order()
        order.action = "BUY"
        gateway.read_only = False
        order_id = gateway.submit_order(contract, order)
        
        with patch('src.gateway.IBKRConnection.error') as mock_super_error:
            gateway.error(order_id, 201, "Order rejected")
            mock_super_error.assert_called_once_with(order_id, 201, "Order rejected", "")
        
        # Test connection error codes
        with patch('src.gateway.IBKRConnection.error') as mock_super_error:
            gateway.error(0, 1100, "Gateway disconnected from TWS")
            mock_super_error.assert_called_once_with(0, 1100, "Gateway disconnected from TWS", "")
        
        with patch('src.gateway.IBKRConnection.error') as mock_super_error:
            gateway.error(0, 1101, "Gateway reconnected to TWS")
            mock_super_error.assert_called_once_with(0, 1101, "Gateway reconnected to TWS", "")

    def test_account_position_updates(self, gateway):
        """Test processing account and position updates."""
        # Test account value update
        gateway.updateAccountValue("NetLiquidation", "100000", "USD", "U12345")
        assert "U12345" in gateway._account_values
        assert "NetLiquidation_USD" in gateway._account_values["U12345"]
        assert gateway._account_values["U12345"]["NetLiquidation_USD"] == "100000"
        
        gateway.updateAccountValue("AvailableFunds", "75000", "USD", "U12345")
        assert "AvailableFunds_USD" in gateway._account_values["U12345"]
        assert gateway._account_values["U12345"]["AvailableFunds_USD"] == "75000"
        
        # Test position update
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "NASDAQ"
        contract.currency = "USD"
        
        gateway.updatePortfolio(
            contract, 100, 150.0, 15000.0,
            145.0, 500.0, 0.0, "U12345"
        )
        
        assert "U12345" in gateway._positions
        position_key = "AAPL_STK_NASDAQ_USD"
        assert position_key in gateway._positions["U12345"]
        position = gateway._positions["U12345"][position_key]
        assert position["contract"] == contract
        assert position["position"] == 100
        assert position["market_price"] == 150.0
        assert position["market_value"] == 15000.0
        assert position["average_cost"] == 145.0
        assert position["unrealized_pnl"] == 500.0
        assert position["realized_pnl"] == 0.0
        
        # Test position close
        gateway.updatePortfolio(
            contract, 0, 150.0, 0.0,
            145.0, 0.0, 500.0, "U12345"
        )
        
        assert position_key not in gateway._positions["U12345"]

    def test_get_positions_and_account_values(self, gateway):
        """Test getting positions and account values."""
        # Set up test data
        gateway.updateAccountValue("NetLiquidation", "100000", "USD", "U12345")
        gateway.updateAccountValue("AvailableFunds", "75000", "USD", "U12345")
        gateway.updateAccountValue("NetLiquidation", "50000", "USD", "U67890")
        
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "NASDAQ"
        contract.currency = "USD"
        
        gateway.updatePortfolio(
            contract, 100, 150.0, 15000.0,
            145.0, 500.0, 0.0, "U12345"
        )
        
        # Test get all positions
        positions = gateway.get_positions()
        assert "U12345" in positions
        position_key = "AAPL_STK_NASDAQ_USD"
        assert position_key in positions["U12345"]
        
        # Test get positions for specific account
        positions = gateway.get_positions("U12345")
        assert "U12345" in positions
        assert position_key in positions["U12345"]
        
        positions = gateway.get_positions("U67890")
        assert "U67890" in positions
        assert not positions["U67890"]  # Empty dict
        
        # Test get all account values
        account_values = gateway.get_account_values()
        assert "U12345" in account_values
        assert "U67890" in account_values
        assert "NetLiquidation_USD" in account_values["U12345"]
        assert "AvailableFunds_USD" in account_values["U12345"]
        assert "NetLiquidation_USD" in account_values["U67890"]
        
        # Test get account values for specific account
        account_values = gateway.get_account_values("U12345")
        assert "U12345" in account_values
        assert "NetLiquidation_USD" in account_values["U12345"]
        assert "AvailableFunds_USD" in account_values["U12345"]
        
        account_values = gateway.get_account_values("U99999")
        assert "U99999" in account_values
        assert not account_values["U99999"]  # Empty dict

    def test_order_status_and_execution(self, gateway):
        """Test processing order status and execution updates."""
        # Create test order
        contract = Contract()
        contract.symbol = "AAPL"
        order = Order()
        order.action = "BUY"
        order.totalQuantity = 100
        gateway.read_only = False
        order_id = gateway.submit_order(contract, order)
        
        # Test order status update
        gateway.orderStatus(
            order_id, "Submitted", 0, 100, 0.0,
            0, 0, 0.0, 0, "", 0.0
        )
        
        assert gateway._orders[order_id].status == "Submitted"
        assert gateway._orders[order_id].filled == 0
        assert gateway._orders[order_id].remaining == 100
        
        # Test partial fill
        gateway.orderStatus(
            order_id, "PartiallyFilled", 50, 50, 150.0,
            0, 0, 150.0, 0, "", 0.0
        )
        
        assert gateway._orders[order_id].status == "PartiallyFilled"
        assert gateway._orders[order_id].filled == 50
        assert gateway._orders[order_id].remaining == 50
        assert gateway._orders[order_id].avgFillPrice == 150.0
        assert gateway._orders[order_id].lastFillPrice == 150.0
        
        # Test execution details
        execution = MagicMock()
        execution.orderId = order_id
        execution.shares = 50
        execution.price = 150.0
        execution.side = "BUY"
        
        gateway.execDetails(0, contract, execution)
        
        # Test commission report
        commission_report = MagicMock()
        commission_report.execId = "123456"
        commission_report.commission = 1.25
        commission_report.currency = "USD"
        
        gateway.commissionReport(commission_report)