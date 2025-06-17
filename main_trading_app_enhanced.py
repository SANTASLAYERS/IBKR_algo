#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enhanced Alpaca Trading Application

This version includes advanced features from the TWS trading system:
- ATR-based stop loss and take profit
- Dynamic position sizing based on dollar allocation
- Customized strategy parameters per ticker
- End-of-day position closure
- Double down order functionality
- Enhanced monitoring and status reporting
"""

import asyncio
import signal
import sys
import time
from typing import Optional, Dict
from datetime import datetime, time as dt_time

from src.config.broker_config import BrokerConfig
from src.alpaca_connection import AlpacaConnection
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.rule.engine import RuleEngine
from api_client import FullApiClient as APIClient
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.position.alpaca_sync import AlpacaPositionSync
from src.position.sizer import PositionSizer
from src.price.service import PriceService
from src.indicators.manager import IndicatorManager
from src.rule.unified_fill_manager import UnifiedFillManager
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    CooldownResetManager,
    LinkedFlattenCloseAction
)
from src.api import OptionsFlowMonitor
from src.rule.base import Rule
from src.rule.condition import EventCondition, TimeCondition
from src.event.api import PredictionSignalEvent
from src.order import OrderType
from src.logger import get_logger

logger = get_logger(__name__)


class EnhancedTradingApp:
    """Enhanced trading application with advanced features."""
    
    def __init__(self):
        """Initialize the enhanced trading application."""
        self.config: Optional[BrokerConfig] = None
        self.connection: Optional[AlpacaConnection] = None
        self.event_bus: Optional[EventBus] = None
        self.order_manager: Optional[OrderManager] = None
        self.rule_engine: Optional[RuleEngine] = None
        self.api_client: Optional[APIClient] = None
        self.position_tracker: Optional[PositionTracker] = None
        self.position_manager: Optional[PositionManager] = None
        self.position_sync: Optional[AlpacaPositionSync] = None
        self.position_sizer: Optional[PositionSizer] = None
        self.price_service: Optional[PriceService] = None
        self.indicator_manager: Optional[IndicatorManager] = None
        self.unified_fill_manager: Optional[UnifiedFillManager] = None
        self.cooldown_reset_manager: Optional[CooldownResetManager] = None
        self.options_flow_monitor: Optional[OptionsFlowMonitor] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Enhanced strategy configurations per ticker
        self.strategies = {
            "CVNA": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "UVXY": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "SOXL": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "SOXS": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "TQQQ": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "SQQQ": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            },
            "GLD": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 10.0,  # Higher for less volatile GLD
                "atr_target_multiplier": 5.0, 
                "cooldown_minutes": 3
            },
            "SLV": {
                "confidence_threshold": 0.50, 
                "allocation": 30000, 
                "atr_stop_multiplier": 6.0, 
                "atr_target_multiplier": 4.0, 
                "cooldown_minutes": 3
            }
        }
    
    async def initialize(self) -> bool:
        """Initialize all components of the enhanced trading system."""
        try:
            logger.info("=" * 50)
            logger.info("Initializing Enhanced Alpaca Trading System")
            logger.info("=" * 50)
            
            # Load configuration
            logger.info("Loading configuration...")
            self.config = BrokerConfig.from_env()
            
            if not self.config.validate():
                logger.error("Configuration validation failed")
                return False
            
            logger.info(f"Configuration loaded - Trading Mode: {self.config.alpaca.trading_mode}")
            
            # Initialize event bus
            logger.info("Initializing event bus...")
            self.event_bus = EventBus()
            
            # Create Alpaca connection
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
            
            logger.info("Connected to Alpaca")
            
            # Initialize core components
            self.position_tracker = PositionTracker(self.event_bus)
            await self.position_tracker.initialize()
            self.position_manager = PositionManager()
            
            # Initialize position synchronization
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
                logger.info(f"Position sync completed - {sync_result['alpaca_positions']} positions synced")
            
            # Start periodic position sync
            await self.position_sync.start_periodic_sync(interval=30)
            
            # Initialize order manager
            self.order_manager = OrderManager(
                event_bus=self.event_bus,
                broker_connection=self.connection
            )
            
            # Initialize price service for real-time prices
            self.price_service = PriceService(self.connection)
            
            # Initialize position sizer for dynamic position sizing
            self.position_sizer = PositionSizer(min_shares=1, max_shares=10000)
            
            # Initialize indicator manager for ATR calculations
            self.indicator_manager = IndicatorManager(
                minute_data_manager=self.connection.minute_bar_manager
            )
            
            # Initialize API client
            logger.info("Initializing API client...")
            self.api_client = APIClient()
            logger.info("API client initialized")
            
            # Initialize rule engine with enhanced context
            logger.info("Initializing rule engine...")
            self.rule_engine = RuleEngine(event_bus=self.event_bus)
            
            # Set rule engine context with all components
            self.rule_engine.update_context({
                'order_manager': self.order_manager,
                'api_client': self.api_client,
                'position_tracker': self.position_tracker,
                'position_manager': self.position_manager,
                'connection': self.connection,
                'price_service': self.price_service,
                'position_sizer': self.position_sizer,
                'indicator_manager': self.indicator_manager,
                'account': {'equity': 1000000},  # Update with real account value
                'prices': {}
            })
            
            # Initialize UnifiedFillManager
            logger.info("Initializing UnifiedFillManager...")
            context = {
                'order_manager': self.order_manager,
                'position_manager': self.position_manager,
                'position_tracker': self.position_tracker,
                'connection': self.connection
            }
            self.unified_fill_manager = UnifiedFillManager(
                context=context,
                event_bus=self.event_bus
            )
            await self.unified_fill_manager.initialize()
            
            # Initialize cooldown reset manager for stop loss handling
            self.cooldown_reset_manager = CooldownResetManager(
                rule_engine=self.rule_engine,
                event_bus=self.event_bus
            )
            await self.cooldown_reset_manager.initialize()
            
            # Start the rule engine
            await self.rule_engine.start()
            
            # Initialize OptionsFlowMonitor
            logger.info("Initializing OptionsFlowMonitor...")
            self.options_flow_monitor = OptionsFlowMonitor(
                event_bus=self.event_bus,
                api_client=self.api_client
            )
            
            # Configure with custom thresholds
            tickers_to_monitor = list(self.strategies.keys())
            self.options_flow_monitor.configure(
                tickers=tickers_to_monitor,
                thresholds={'prediction_confidence_min': 0.50}  # Lower threshold like TWS
            )
            
            # Start monitoring
            await self.options_flow_monitor.start_monitoring()
            logger.info(f"OptionsFlowMonitor started for {len(tickers_to_monitor)} tickers")
            
            # Register enhanced trading rules
            self._setup_trading_rules()
            
            # Add end-of-day closure rules
            self._setup_eod_rules()
            
            logger.info("=" * 50)
            logger.info("Enhanced trading system initialized successfully")
            logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}", exc_info=True)
            return False
    
    def _setup_trading_rules(self):
        """Setup enhanced trading rules with ATR-based stops."""
        logger.info("Setting up enhanced trading strategies...")
        rules_registered = 0
        
        for ticker, strategy in self.strategies.items():
            # BUY Rule (Long Entry)
            buy_condition = EventCondition(
                event_type=PredictionSignalEvent,
                field_conditions={
                    "symbol": ticker,
                    "signal": "BUY",
                    "confidence": lambda c: c >= strategy["confidence_threshold"]
                }
            )
            
            buy_action = LinkedCreateOrderAction(
                symbol=ticker,
                quantity=strategy["allocation"],  # Dollar allocation
                side="BUY",
                order_type=OrderType.MARKET,
                auto_create_stops=True,
                atr_stop_multiplier=strategy["atr_stop_multiplier"],
                atr_target_multiplier=strategy["atr_target_multiplier"]
            )
            
            buy_rule = Rule(
                rule_id=f"{ticker.lower()}_buy_rule",
                name=f"{ticker} Buy on High Confidence",
                description=f"Buy {ticker} when confidence >= {strategy['confidence_threshold']}",
                condition=buy_condition,
                action=buy_action,
                priority=100,
                cooldown_seconds=strategy["cooldown_minutes"] * 60
            )
            
            self.rule_engine.register_rule(buy_rule)
            rules_registered += 1
            
            # SELL Rule (Short Entry)
            sell_condition = EventCondition(
                event_type=PredictionSignalEvent,
                field_conditions={
                    "symbol": ticker,
                    "signal": "SHORT",
                    "confidence": lambda c: c >= strategy["confidence_threshold"]
                }
            )
            
            sell_action = LinkedCreateOrderAction(
                symbol=ticker,
                quantity=strategy["allocation"],  # Dollar allocation
                side="SELL",
                order_type=OrderType.MARKET,
                auto_create_stops=True,
                atr_stop_multiplier=strategy["atr_stop_multiplier"],
                atr_target_multiplier=strategy["atr_target_multiplier"]
            )
            
            sell_rule = Rule(
                rule_id=f"{ticker.lower()}_sell_rule",
                name=f"{ticker} Sell (Short) on High Confidence",
                description=f"Short {ticker} when confidence >= {strategy['confidence_threshold']}",
                condition=sell_condition,
                action=sell_action,
                priority=100,
                cooldown_seconds=strategy["cooldown_minutes"] * 60
            )
            
            self.rule_engine.register_rule(sell_rule)
            rules_registered += 1
            
            logger.info(
                f"Created strategy for {ticker} "
                f"(confidence >= {strategy['confidence_threshold']}, "
                f"allocation: ${strategy['allocation']:,}, "
                f"ATR stop: {strategy['atr_stop_multiplier']}x, "
                f"ATR target: {strategy['atr_target_multiplier']}x)"
            )
        
        logger.info(f"Registered {rules_registered} enhanced trading rules")
    
    def _setup_eod_rules(self):
        """Setup end-of-day position closure rules."""
        logger.info("Setting up end-of-day closure rules...")
        
        for ticker in self.strategies.keys():
            eod_condition = TimeCondition(
                start_time=dt_time(15, 59),  # 3:59 PM ET
                end_time=dt_time(16, 0)      # 4:00 PM ET
            )
            
            eod_action = LinkedFlattenCloseAction(symbol=ticker)
            
            eod_rule = Rule(
                rule_id=f"eod_closure_{ticker.lower()}",
                name=f"End of Day Closure - {ticker}",
                description=f"Close all {ticker} positions and orders before market close",
                condition=eod_condition,
                action=eod_action,
                priority=200,  # High priority
                max_executions_per_day=1
            )
            
            self.rule_engine.register_rule(eod_rule)
        
        logger.info("Created end-of-day closure rules (3:59 PM)")
    
    def _on_connected(self):
        """Handle connection established event."""
        logger.info("Connection established callback triggered")
        if self.event_bus:
            self.event_bus.emit('connection.established', {
                'broker': 'alpaca',
                'timestamp': time.time()
            })
    
    def _on_disconnected(self):
        """Handle connection lost event."""
        logger.warning("Connection lost callback triggered")
        if self.event_bus:
            self.event_bus.emit('connection.lost', {
                'broker': 'alpaca',
                'timestamp': time.time()
            })
    
    def _on_error(self, req_id: int, error_code: int, error_string: str):
        """Handle connection error event."""
        logger.error(f"Connection error: {error_code} - {error_string}")
        if self.event_bus:
            self.event_bus.emit('connection.error', {
                'broker': 'alpaca',
                'error_code': error_code,
                'error_string': error_string,
                'timestamp': time.time()
            })
    
    async def _log_system_status(self):
        """Log current system status with position summary."""
        try:
            if self.position_tracker:
                summary = await self.position_tracker.get_position_summary()
                logger.info("=" * 50)
                logger.info("SYSTEM STATUS UPDATE")
                logger.info(f"Current positions: {summary['total_positions']}")
                logger.info(f"Total value: ${summary['total_value']:,.2f}")
                logger.info(f"Unrealized P&L: ${summary['total_unrealized_pnl']:,.2f}")
                
                # Log individual positions
                if summary['total_positions'] > 0:
                    logger.info("Active positions:")
                    positions = await self.position_tracker.get_all_positions()
                    for pos in positions:
                        if pos.status.value == "open":
                            logger.info(
                                f"  {pos.symbol}: {pos.quantity} shares @ "
                                f"${pos.entry_price:.2f} (P&L: ${pos.unrealized_pnl:.2f})"
                            )
                
                logger.info("=" * 50)
        except Exception as e:
            logger.error(f"Error logging system status: {e}")
    
    async def run_monitoring_loop(self):
        """Run the enhanced monitoring loop with status updates."""
        try:
            while self._running:
                # Log status every 10 minutes
                await asyncio.sleep(600)  # 10 minutes
                
                if self._running:
                    await self._log_system_status()
                    
                    # Check account status
                    if self.connection and self.connection.is_connected():
                        account = self.connection.get_account()
                        if account:
                            logger.info(f"Account buying power: ${float(account.buying_power):,.2f}")
                            logger.info(f"Account equity: ${float(account.equity):,.2f}")
                    
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
    
    async def run(self):
        """Run the main trading loop."""
        if not await self.initialize():
            logger.error("Failed to initialize trading system")
            return
        
        self._running = True
        logger.info("Enhanced trading system is running...")
        logger.info("Features enabled:")
        logger.info("  - ATR-based stop loss and take profit")
        logger.info("  - Dynamic position sizing ($30k allocation per trade)")
        logger.info("  - Customized parameters per ticker")
        logger.info("  - End-of-day automatic position closure")
        logger.info("  - 10-minute status monitoring")
        logger.info("Press Ctrl+C to stop")
        
        # Start monitoring loop
        monitoring_task = asyncio.create_task(self.run_monitoring_loop())
        
        try:
            # Log initial status
            await self._log_system_status()
            
            # Keep the application running
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            # Cancel monitoring task
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
            
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the trading system gracefully."""
        if not self._running:
            return
        
        logger.info("Shutting down enhanced trading system...")
        self._running = False
        
        try:
            # Stop position sync
            if self.position_sync:
                logger.info("Stopping position sync...")
                await self.position_sync.stop_periodic_sync()
            
            # Clean up UnifiedFillManager
            if self.unified_fill_manager:
                logger.info("Cleaning up UnifiedFillManager...")
                await self.unified_fill_manager.cleanup()
            
            # Stop OptionsFlowMonitor
            if self.options_flow_monitor:
                logger.info("Stopping OptionsFlowMonitor...")
                await self.options_flow_monitor.stop_monitoring()
            
            # Stop rule engine
            if self.rule_engine:
                logger.info("Stopping rule engine...")
                await self.rule_engine.stop()
            
            # Disconnect from broker
            if self.connection and self.connection.is_connected():
                logger.info("Disconnecting from Alpaca...")
                self.connection.disconnect()
            
            logger.info("Enhanced trading system shutdown complete")
            
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
    app = EnhancedTradingApp()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, app.handle_signal)
    signal.signal(signal.SIGTERM, app.handle_signal)
    
    # Run the application
    await app.run()


if __name__ == "__main__":
    print("Enhanced Alpaca Trading System")
    print("=" * 40)
    print("Features:")
    print("- ATR-based stop loss and take profit")
    print("- Dynamic position sizing")
    print("- Customized parameters per ticker")
    print("- End-of-day position closure")
    print("- Enhanced monitoring")
    print("=" * 40)
    print("Starting application...")
    
    # Run the async main function
    asyncio.run(main()) 