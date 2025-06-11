#!/usr/bin/env python3
"""
Main Trading Application
========================

This is the main entry point for the automated trading system.
It sets up multiple strategies for different tickers and runs the complete system.

Usage:
    python main_trading_app.py

Environment Variables Required:
    TWS_HOST, TWS_PORT, TWS_CLIENT_ID, TWS_ACCOUNT
    API_BASE_URL, API_KEY
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, List
from datetime import datetime, time

# Import all necessary components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition, TimeCondition
from src.rule.action import CreateOrderAction, ClosePositionAction
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedScaleInAction, LinkedCloseAllAction, LinkedOrderConclusionManager, CooldownResetManager, LinkedDoubleDownAction, LinkedDoubleDownFillManager
from src.rule.unified_fill_manager import UnifiedFillManager
from src.rule.base import Rule
from src.order import OrderType
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.sizer import PositionSizer
from src.position.position_manager import PositionManager
from src.price.service import PriceService
from src.api.monitor import OptionsFlowMonitor
from api_client import ApiClient, PredictionEndpoint
from src.indicators.manager import IndicatorManager
from src.config.feature_flags import FeatureFlags

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log', encoding='utf-8'),  # Add UTF-8 encoding
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Reduce noise from IB API logging
logging.getLogger('ibapi').setLevel(logging.WARNING)
logging.getLogger('ibapi.client').setLevel(logging.WARNING)
logging.getLogger('ibapi.wrapper').setLevel(logging.WARNING)
logging.getLogger('ibapi.decoder').setLevel(logging.WARNING)
logging.getLogger('ibapi.reader').setLevel(logging.WARNING)
logging.getLogger('ibapi.connection').setLevel(logging.WARNING)
logging.getLogger('ibapi.utils').setLevel(logging.WARNING)

# Reduce noise from httpx logging
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


class TradingApplication:
    """Main trading application that manages multiple strategies."""
    
    def __init__(self):
        self.running = False
        self.event_bus = None
        self.tws_connection = None
        self.rule_engine = None
        self.order_manager = None
        self.position_tracker = None
        self.api_monitor = None
        self.conclusion_manager = None
        self.cooldown_reset_manager = None
        self.doubledown_fill_manager = None
        self.unified_fill_manager = None
        self.indicator_manager = None
        self.price_service = None
        self.position_sizer = None
        self.strategies = {}
        
    async def initialize(self):
        """Initialize all system components."""
        logger.info("🚀 Initializing Trading Application...")
        
        # Log feature flags
        FeatureFlags.log_flags(logger)
        
        # Create event bus
        self.event_bus = EventBus()
        
        # Setup TWS connection
        config = TWSConfig.from_env()
        self.tws_connection = TWSConnection(config)
        
        # Connect to TWS
        logger.info("Connecting to TWS...")
        connected = await self.tws_connection.connect()
        if not connected:
            raise Exception("Failed to connect to TWS")
        logger.info("✅ Connected to TWS")
        
        # Initialize components
        self.order_manager = OrderManager(self.event_bus, self.tws_connection)
        self.position_tracker = PositionTracker(self.event_bus)
        self.rule_engine = RuleEngine(self.event_bus)
        
        # Initialize PositionManager (singleton)
        position_manager = PositionManager()
        logger.info("✅ PositionManager initialized (dual-write enabled)")
        
        # Initialize indicator manager for ATR calculations
        self.indicator_manager = IndicatorManager(
            minute_data_manager=self.tws_connection.minute_bar_manager  # Assuming TWS has minute bar manager
        )
        
        # Initialize price service for real-time prices
        self.price_service = PriceService(self.tws_connection)
        
        # Initialize position sizer for dynamic position sizing
        self.position_sizer = PositionSizer(min_shares=1, max_shares=10000)
        
        # Initialize components
        await self.order_manager.initialize()
        await self.position_tracker.initialize()
        
        # Setup rule engine context
        self.rule_engine.update_context({
            "order_manager": self.order_manager,
            "position_tracker": self.position_tracker,
            "indicator_manager": self.indicator_manager,  # Add indicator manager to context
            "price_service": self.price_service,          # Add price service to context
            "position_sizer": self.position_sizer,        # Add position sizer to context
            "account": {"equity": 1000000},  # Update with real account value
            "prices": {}
        })
        
        # 🎯 NEW: Setup unified fill manager for all fill events
        self.unified_fill_manager = UnifiedFillManager(
            context=self.rule_engine.context,
            event_bus=self.event_bus
        )
        await self.unified_fill_manager.initialize()
        logger.info("✅ UnifiedFillManager initialized - handles all fill events and protective order updates")
        
        # Initialize cooldown reset manager for stop loss handling
        self.cooldown_reset_manager = CooldownResetManager(
            rule_engine=self.rule_engine,
            event_bus=self.event_bus
        )
        await self.cooldown_reset_manager.initialize()
        
        # DEPRECATED: These managers are kept for backward compatibility but functionality
        # is now handled by UnifiedFillManager
        if FeatureFlags.get("ENABLE_LEGACY_FILL_MANAGERS", False):
            # Only initialize if explicitly enabled
            self.conclusion_manager = LinkedOrderConclusionManager(
                context=self.rule_engine.context,
                event_bus=self.event_bus
            )
            await self.conclusion_manager.initialize()
            
            self.doubledown_fill_manager = LinkedDoubleDownFillManager(
                context=self.rule_engine.context,
                event_bus=self.event_bus
            )
            await self.doubledown_fill_manager.initialize()
        
        # Setup API monitoring
        try:
            # ApiClient will automatically use environment variables if no parameters provided
            api_client = ApiClient()
            # Attach the prediction endpoint that OptionsFlowMonitor expects
            api_client.prediction = PredictionEndpoint(api_client)
            self.api_monitor = OptionsFlowMonitor(self.event_bus, api_client)
            logger.info("✅ API client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize API client: {e}")
            raise
        
        logger.info("✅ All components initialized")
    
    def setup_strategies(self):
        """Setup trading strategies for different tickers."""
        logger.info("📋 Setting up trading strategies...")
        
        # Strategy configurations for different tickers
        self.strategies = {
            "CVNA": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "UVXY": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "SOXL": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "SOXS": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "TQQQ": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "SQQQ": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "GLD": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3},
            "SLV": {"confidence_threshold": 0.50, "allocation": 30000, "atr_stop_multiplier": 6.5, "atr_target_multiplier": 3.0, "cooldown_minutes": 3}
        }
        
        # Create rules for each strategy
        for ticker, strategy in self.strategies.items():
            self._create_strategy_rules(ticker, strategy)
        
        # Add end-of-day position closure rule
        self._create_eod_closure_rule()
        
        logger.info(f"✅ Created strategies for {len(self.strategies)} tickers")
    
    def _create_strategy_rules(self, ticker: str, strategy: Dict):
        """Create buy and sell rules for a specific ticker strategy."""
        
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
            quantity=strategy["allocation"],
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,  # Automatically create stop & target orders
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
        
        # SELL Rule (Short Entry)
        sell_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": ticker,
                "signal": "SELL",
                "confidence": lambda c: c >= strategy["confidence_threshold"]
            }
        )
        
        sell_action = LinkedCreateOrderAction(
            symbol=ticker,
            quantity=strategy["allocation"],
            side="SELL",                      # Short position
            order_type=OrderType.MARKET,
            auto_create_stops=True,  # Automatically create stop & target orders
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
        
        # Register rules
        self.rule_engine.register_rule(buy_rule)
        self.rule_engine.register_rule(sell_rule)
        
        logger.info(f"📊 Created strategy for {ticker} (confidence >= {strategy['confidence_threshold']}, auto double down @ 50% to stop)")
    
    def _create_eod_closure_rule(self):
        """Create end-of-day position closure rule."""
        # End-of-Day Close Rule (close ALL positions and orders)
        tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]  # Updated ticker list
        
        for ticker in tickers:
            eod_condition = TimeCondition(
                start_time=time(15, 59),  # 3:59 PM ET - Changed from 3:30 PM
                end_time=time(16, 0)      # 4:00 PM ET - Only run between 3:59 and 4:00
            )
            
            # Use LinkedCloseAllAction to close position AND cancel all linked orders
            eod_action = LinkedCloseAllAction(
                symbol=ticker,
                reason="End of day close"
            )
            
            eod_rule = Rule(
                rule_id=f"end_of_day_closure_{ticker}",
                name=f"End of Day Closure - {ticker}",
                description=f"Close all {ticker} positions and orders before market close",
                condition=eod_condition,
                action=eod_action,
                priority=200,  # High priority
                max_executions_per_day=1  # Only run once per day
            )
            
            self.rule_engine.register_rule(eod_rule)
        
        logger.info("📅 Created end-of-day closure rule (3:59 PM)")
    
    async def start_trading(self):
        """Start the trading system."""
        logger.info("🔥 Starting trading system...")
        
        # Configure API monitoring for our tickers
        tickers = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV"]
        self.api_monitor.configure(tickers)
        
        # Start components
        await self.rule_engine.start()
        await self.api_monitor.start_monitoring()
        
        self.running = True
        logger.info("🚀 TRADING SYSTEM ACTIVE!")
        logger.info("📊 Monitoring tickers: " + ", ".join(tickers))
        logger.info("📋 Rules registered: " + str(len(self.rule_engine.get_all_rules())))
        logger.info("⚡ Waiting for prediction signals...")
        
        # Log current system status
        await self._log_system_status()
    
    async def stop_trading(self):
        """Stop the trading system gracefully."""
        logger.info("⏹️ Stopping trading system...")
        
        self.running = False
        
        # Stop components
        if self.api_monitor:
            await self.api_monitor.stop_monitoring()
        
        if self.rule_engine:
            await self.rule_engine.stop()
        
        # Clean up UnifiedFillManager
        if self.unified_fill_manager:
            await self.unified_fill_manager.cleanup()
        
        # Disconnect TWS
        if self.tws_connection and self.tws_connection.is_connected():
            self.tws_connection.disconnect()
        
        logger.info("✅ Trading system stopped")
    
    async def _log_system_status(self):
        """Log current system status."""
        # Get positions summary
        if self.position_tracker:
            summary = await self.position_tracker.get_position_summary()
            logger.info(f"💰 Current positions: {summary['total_positions']}")
            logger.info(f"💰 Total value: ${summary['total_value']:,.2f}")
            logger.info(f"💰 Unrealized P&L: ${summary['total_unrealized_pnl']:,.2f}")
    
    async def run_monitoring_loop(self):
        """Run the main monitoring loop."""
        try:
            last_reconciliation = datetime.now()
            reconciliation_interval = 3600  # 1 hour
            
            while self.running:
                # Check if we should run reconciliation
                if FeatureFlags.RECONCILIATION_ENABLED:
                    time_since_last = (datetime.now() - last_reconciliation).total_seconds()
                    if time_since_last >= reconciliation_interval:
                        # Run reconciliation
                        try:
                            from src.utils.reconcile_position_tracking import run_reconciliation
                            logger.info("🔍 Running position tracking reconciliation...")
                            summary = run_reconciliation()
                            if summary['status'] != 'IN_SYNC':
                                logger.warning(f"⚠️ Position tracking discrepancies found: {summary['discrepancies']['count']}")
                            last_reconciliation = datetime.now()
                        except Exception as e:
                            logger.error(f"Error running reconciliation: {e}")
                
                # Log status every 10 minutes
                await asyncio.sleep(600)
                if self.running:
                    await self._log_system_status()
                    
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")


async def main():
    """Main entry point."""
    app = TradingApplication()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("🛑 Received shutdown signal")
        asyncio.create_task(app.stop_trading())
    
    # Register signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        try:
            signal.signal(sig, lambda s, f: signal_handler())
        except:
            pass  # Signal handling might not work on all platforms
    
    try:
        # Initialize system
        await app.initialize()
        
        # Setup strategies
        app.setup_strategies()
        
        # Start trading
        await app.start_trading()
        
        # Run monitoring loop
        await app.run_monitoring_loop()
        
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise
    finally:
        await app.stop_trading()


if __name__ == "__main__":
    print("🔥 TWS Automated Trading System")
    print("🚀 Starting application...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
    except Exception as e:
        print(f"\n❌ Application failed: {e}")
        sys.exit(1) 