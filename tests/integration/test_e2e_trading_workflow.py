#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
End-to-End Trading Workflow Integration Tests.

Tests complete trading workflows integrating all system components.
"""

import pytest
import asyncio
import logging
import os
from unittest.mock import patch

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.market import PriceEvent
from src.event.api import PredictionSignalEvent
from src.position.tracker import PositionTracker
from src.order.manager import OrderManager
from tests.integration.conftest import get_tws_credentials

logger = logging.getLogger("e2e_workflow_tests")


class MockTradingWorkflow:
    """Mock trading workflow for testing without real money."""
    
    def __init__(self, tws_connection, event_bus, position_tracker, order_manager):
        self.tws_connection = tws_connection
        self.event_bus = event_bus
        self.position_tracker = position_tracker
        self.order_manager = order_manager
        self.signals_processed = []
        self.positions_created = []
        
    async def initialize(self):
        """Initialize the workflow."""
        await self.event_bus.subscribe(PredictionSignalEvent, self.handle_prediction_signal)
        await self.event_bus.subscribe(PriceEvent, self.handle_price_update)
        logger.info("Mock trading workflow initialized")
    
    async def handle_prediction_signal(self, event: PredictionSignalEvent):
        """Handle prediction signals."""
        logger.info(f"Received prediction signal: {event.signal} for {event.symbol} (confidence: {event.confidence})")
        self.signals_processed.append(event)
        
        # For testing, we'll just track signals without actual trading
        if event.signal == "BUY" and event.confidence > 0.7:
            logger.info(f"Would create position for {event.symbol} based on strong BUY signal")
            
            # Create mock position
            mock_position = {
                "symbol": event.symbol,
                "signal": event.signal,
                "confidence": event.confidence,
                "price": event.price,
                "timestamp": event.timestamp
            }
            self.positions_created.append(mock_position)
    
    async def handle_price_update(self, event: PriceEvent):
        """Handle price updates."""
        logger.debug(f"Price update: {event.symbol} = {event.price}")
        # Update positions with new prices


class TestE2ETradingWorkflow:
    """End-to-end trading workflow tests."""

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_complete_system_integration(self):
        """Test complete system integration without real trading."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 20,  # Different client ID
            connection_timeout=10.0
        )
        
        # Initialize system components
        tws_connection = TWSConnection(config)
        event_bus = EventBus()
        position_tracker = PositionTracker(event_bus)
        order_manager = OrderManager(event_bus)
        
        # Initialize mock workflow
        workflow = MockTradingWorkflow(tws_connection, event_bus, position_tracker, order_manager)
        
        try:
            # Connect to TWS
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Initialize components
            await workflow.initialize()
            await position_tracker.initialize()
            await order_manager.initialize()
            
            logger.info("✅ All system components initialized")
            
            # Test event flow
            logger.info("Testing event-driven workflow...")
            
            # Simulate prediction signal
            prediction_event = PredictionSignalEvent(
                symbol="AAPL",
                signal="BUY",
                confidence=0.85,
                price=150.0,
                prediction_data={"model": "test", "features": {}}
            )
            
            await event_bus.emit(prediction_event)
            await asyncio.sleep(1)  # Allow event processing
            
            # Verify signal was processed
            assert len(workflow.signals_processed) == 1, "Prediction signal should be processed"
            assert workflow.signals_processed[0].symbol == "AAPL"
            assert len(workflow.positions_created) == 1, "Position should be created for strong signal"
            
            # Simulate price update
            price_event = PriceEvent(
                symbol="AAPL",
                price=152.0,
                volume=1000,
                timestamp=asyncio.get_event_loop().time()
            )
            
            await event_bus.emit(price_event)
            await asyncio.sleep(1)  # Allow event processing
            
            logger.info("✅ Event-driven workflow test completed")
            
            # Test basic TWS functionality
            logger.info("Testing TWS API functionality...")
            
            # Request current time
            tws_connection.request_current_time()
            await asyncio.sleep(2)
            
            # Request managed accounts
            tws_connection.request_managed_accounts()
            await asyncio.sleep(2)
            
            logger.info("✅ TWS API functionality test completed")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in the complete workflow."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 21,  # Different client ID
            connection_timeout=10.0
        )
        
        # Initialize components
        tws_connection = TWSConnection(config)
        event_bus = EventBus()
        
        try:
            # Connect to TWS
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Test error handling by sending invalid events
            invalid_event = PredictionSignalEvent(
                symbol="",  # Invalid empty symbol
                signal="INVALID",  # Invalid signal
                confidence=-1.0,  # Invalid confidence
                price=0.0,  # Invalid price
                prediction_data={}
            )
            
            # This should not crash the system
            await event_bus.emit(invalid_event)
            await asyncio.sleep(1)
            
            logger.info("✅ Error handling test completed")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_reconnection_workflow(self):
        """Test system behavior during connection interruptions."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 22,  # Different client ID
            connection_timeout=5.0
        )
        
        tws_connection = TWSConnection(config)
        
        try:
            # Initial connection
            connected = await tws_connection.connect()
            assert connected, "Failed to initial connect to TWS"
            
            # Verify connection
            assert tws_connection.is_connected(), "Should be connected"
            
            # Simulate disconnection
            logger.info("Simulating disconnection...")
            tws_connection.disconnect()
            await asyncio.sleep(2)
            
            # Verify disconnection
            assert not tws_connection.is_connected(), "Should be disconnected"
            
            # Test reconnection
            logger.info("Testing reconnection...")
            reconnected = await tws_connection.connect()
            assert reconnected, "Should be able to reconnect"
            assert tws_connection.is_connected(), "Should be connected after reconnection"
            
            logger.info("✅ Reconnection test completed")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_multiple_client_connections(self):
        """Test multiple client connections to TWS."""
        credentials = get_tws_credentials()
        
        # Create multiple configurations with different client IDs
        configs = [
            TWSConfig(
                host=credentials["host"],
                port=credentials["port"],
                client_id=credentials["client_id"] + 30 + i,
                connection_timeout=10.0
            )
            for i in range(3)
        ]
        
        connections = [TWSConnection(config) for config in configs]
        
        try:
            # Connect all clients
            connect_results = []
            for i, connection in enumerate(connections):
                logger.info(f"Connecting client {i + 1}...")
                connected = await connection.connect()
                connect_results.append(connected)
                await asyncio.sleep(1)  # Small delay between connections
            
            # Verify connections
            successful_connections = sum(connect_results)
            logger.info(f"Successfully connected {successful_connections} out of {len(connections)} clients")
            
            # Should be able to connect at least one client
            assert successful_connections >= 1, "Should connect at least one client"
            
            # Test basic functionality for connected clients
            for i, connection in enumerate(connections):
                if connection.is_connected():
                    logger.info(f"Testing client {i + 1} functionality...")
                    connection.request_current_time()
                    await asyncio.sleep(1)
            
            logger.info("✅ Multiple client connection test completed")
            
        finally:
            # Disconnect all clients
            for i, connection in enumerate(connections):
                if connection.is_connected():
                    logger.info(f"Disconnecting client {i + 1}...")
                    connection.disconnect()
                    await asyncio.sleep(0.5)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_system_performance_basic(self):
        """Test basic system performance metrics."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 25,  # Different client ID
            connection_timeout=10.0
        )
        
        tws_connection = TWSConnection(config)
        event_bus = EventBus()
        
        try:
            # Connect to TWS
            start_time = asyncio.get_event_loop().time()
            connected = await tws_connection.connect()
            connection_time = asyncio.get_event_loop().time() - start_time
            
            assert connected, "Failed to connect to TWS"
            logger.info(f"Connection time: {connection_time:.3f} seconds")
            
            # Test event bus performance
            event_count = 100
            start_time = asyncio.get_event_loop().time()
            
            for i in range(event_count):
                price_event = PriceEvent(
                    symbol="TEST",
                    price=100.0 + i,
                    volume=1000,
                    timestamp=asyncio.get_event_loop().time()
                )
                await event_bus.emit(price_event)
            
            event_time = asyncio.get_event_loop().time() - start_time
            events_per_second = event_count / event_time
            
            logger.info(f"Event processing: {events_per_second:.0f} events/second")
            
            # Basic performance assertions
            assert connection_time < 30.0, "Connection should complete within 30 seconds"
            assert events_per_second > 10, "Should process at least 10 events per second"
            
            logger.info("✅ Basic performance test completed")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1) 