#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main Trading Application - Alpaca Version

This is the main entry point for the automated trading system,
now exclusively using Alpaca Markets.
"""

import asyncio
import signal
import sys
import time
from typing import Optional

from src.config.broker_config import BrokerConfig
from src.alpaca_connection import AlpacaConnection
from src.event_bus import EventBus
from src.order_manager import OrderManager
from src.rule_engine import RuleEngine
from src.api_client import APIClient
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.position.alpaca_sync import AlpacaPositionSync
from src.logger import get_logger

logger = get_logger(__name__)


class TradingApp:
    """Main trading application class."""
    
    def __init__(self):
        """Initialize the trading application."""
        self.config: Optional[BrokerConfig] = None
        self.connection: Optional[AlpacaConnection] = None
        self.event_bus: Optional[EventBus] = None
        self.order_manager: Optional[OrderManager] = None
        self.rule_engine: Optional[RuleEngine] = None
        self.api_client: Optional[APIClient] = None
        self.position_tracker: Optional[PositionTracker] = None
        self.position_manager: Optional[PositionManager] = None
        self.position_sync: Optional[AlpacaPositionSync] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self) -> bool:
        """
        Initialize all components of the trading system.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("=" * 50)
            logger.info("Initializing Alpaca Trading System")
            logger.info("=" * 50)
            
            # Load configuration
            logger.info("Loading configuration...")
            self.config = BrokerConfig.from_env()
            
            # Validate configuration
            if not self.config.validate():
                logger.error("Configuration validation failed")
                return False
            
            logger.info(f"✅ Configuration loaded - Trading Mode: {self.config.alpaca.trading_mode}")
            
            # Initialize event bus
            logger.info("Initializing event bus...")
            self.event_bus = EventBus()
            logger.info("✅ Event bus initialized")
            
            # Create Alpaca connection with event bus
            logger.info("Creating Alpaca connection...")
            self.connection = AlpacaConnection(self.config.alpaca, self.event_bus)
            
            # Set connection callbacks
            self.connection.set_callbacks(
                on_connected=self._on_connected,
                on_disconnected=self._on_disconnected,
                on_error=self._on_error
            )
            
            # Connect to Alpaca
            logger.info("Connecting to Alpaca...")
            connected = await self.connection.connect()
            
            if not connected:
                logger.error("Failed to connect to Alpaca")
                return False
            
            logger.info("✅ Connected to Alpaca")
            
            # Initialize position tracking
            logger.info("Initializing position tracking...")
            self.position_tracker = PositionTracker(self.event_bus)
            await self.position_tracker.initialize()
            self.position_manager = PositionManager()
            logger.info("✅ Position tracking initialized")
            
            # Initialize position synchronization
            logger.info("Initializing position synchronization...")
            self.position_sync = AlpacaPositionSync(
                connection=self.connection,
                position_tracker=self.position_tracker,
                position_manager=self.position_manager,
                event_bus=self.event_bus
            )
            
            # Perform initial position sync
            logger.info("Performing initial position sync...")
            sync_result = await self.position_sync.sync_positions()
            if sync_result['status'] == 'success':
                logger.info(f"✅ Position sync completed - {sync_result['alpaca_positions']} positions synced")
            else:
                logger.warning(f"Position sync failed: {sync_result.get('message', 'Unknown error')}")
            
            # Start periodic position sync
            await self.position_sync.start_periodic_sync(interval=30)
            logger.info("✅ Started periodic position sync (30s interval)")
            
            # Initialize order manager
            logger.info("Initializing order manager...")
            self.order_manager = OrderManager(
                connection=self.connection,
                event_bus=self.event_bus
            )
            logger.info("✅ Order manager initialized")
            
            # Initialize API client
            logger.info("Initializing API client...")
            self.api_client = APIClient(event_bus=self.event_bus)
            logger.info("✅ API client initialized")
            
            # Initialize rule engine
            logger.info("Initializing rule engine...")
            self.rule_engine = RuleEngine(
                event_bus=self.event_bus,
                order_manager=self.order_manager,
                api_client=self.api_client
            )
            logger.info("✅ Rule engine initialized")
            
            # Load trading rules
            logger.info("Loading trading rules...")
            rules_loaded = self.rule_engine.load_rules()
            logger.info(f"✅ Loaded {rules_loaded} trading rules")
            
            logger.info("=" * 50)
            logger.info("✅ Trading system initialized successfully")
            logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}", exc_info=True)
            return False
    
    def _on_connected(self):
        """Handle connection established event."""
        logger.info("🔗 Connection established callback triggered")
        if self.event_bus:
            self.event_bus.emit('connection.established', {
                'broker': 'alpaca',
                'timestamp': time.time()
            })
    
    def _on_disconnected(self):
        """Handle connection lost event."""
        logger.warning("🔌 Connection lost callback triggered")
        if self.event_bus:
            self.event_bus.emit('connection.lost', {
                'broker': 'alpaca',
                'timestamp': time.time()
            })
    
    def _on_error(self, req_id: int, error_code: int, error_string: str):
        """Handle connection error event."""
        logger.error(f"❌ Connection error: {error_code} - {error_string}")
        if self.event_bus:
            self.event_bus.emit('connection.error', {
                'broker': 'alpaca',
                'error_code': error_code,
                'error_string': error_string,
                'timestamp': time.time()
            })
    
    async def run(self):
        """Run the main trading loop."""
        if not await self.initialize():
            logger.error("Failed to initialize trading system")
            return
        
        self._running = True
        logger.info("🚀 Trading system is running...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            # Keep the application running
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the trading system gracefully."""
        if not self._running:
            return
        
        logger.info("Shutting down trading system...")
        self._running = False
        
        try:
            # Stop position sync
            if self.position_sync:
                logger.info("Stopping position sync...")
                await self.position_sync.stop_periodic_sync()
            
            # Stop rule engine
            if self.rule_engine:
                logger.info("Stopping rule engine...")
                self.rule_engine.stop()
            
            # Disconnect from broker
            if self.connection and self.connection.is_connected():
                logger.info("Disconnecting from Alpaca...")
                self.connection.disconnect()
            
            # Stop event bus
            if self.event_bus:
                logger.info("Stopping event bus...")
                # Add any event bus cleanup if needed
            
            logger.info("✅ Trading system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        
        # Set shutdown event
        self._shutdown_event.set()
    
    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}")
        asyncio.create_task(self.shutdown())


async def main():
    """Main entry point."""
    app = TradingApp()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, app.handle_signal)
    signal.signal(signal.SIGTERM, app.handle_signal)
    
    # Run the application
    await app.run()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 