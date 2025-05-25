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
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedScaleInAction, LinkedCloseAllAction
from src.rule.base import Rule
from src.order import OrderType
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.api.monitor import OptionsFlowMonitor
from api_client import ApiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


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
        
    async def initialize(self):
        """Initialize all system components."""
        logger.info("🚀 Initializing Trading Application...")
        
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
        
        # Initialize components
        await self.order_manager.initialize()
        await self.position_tracker.initialize()
        
        # Setup rule engine context
        self.rule_engine.update_context({
            "order_manager": self.order_manager,
            "position_tracker": self.position_tracker,
            "account": {"equity": 100000},  # Update with real account value
            "prices": {}
        })
        
        # Setup API monitoring
        try:
            api_client = ApiClient.from_env()
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
        strategies = [
            {
                "ticker": "AAPL",
                "confidence_threshold": 0.80,
                "quantity": 100,
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.08,
                "cooldown_minutes": 5
            },
            {
                "ticker": "MSFT", 
                "confidence_threshold": 0.85,
                "quantity": 50,
                "stop_loss_pct": 0.025,
                "take_profit_pct": 0.10,
                "cooldown_minutes": 10
            },
            {
                "ticker": "TSLA",
                "confidence_threshold": 0.90,  # Higher threshold for more volatile stock
                "quantity": 25,
                "stop_loss_pct": 0.04,
                "take_profit_pct": 0.12,
                "cooldown_minutes": 15
            },
            {
                "ticker": "NVDA",
                "confidence_threshold": 0.85,
                "quantity": 30,
                "stop_loss_pct": 0.035,
                "take_profit_pct": 0.09,
                "cooldown_minutes": 8
            }
        ]
        
        # Create rules for each strategy
        for strategy in strategies:
            self._create_strategy_rules(strategy)
        
        # Add end-of-day position closure rule
        self._create_eod_closure_rule()
        
        logger.info(f"✅ Created strategies for {len(strategies)} tickers")
    
    def _create_strategy_rules(self, strategy: Dict):
        """Create buy and sell rules for a specific ticker strategy."""
        ticker = strategy["ticker"]
        
        # BUY Rule
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
            quantity=strategy["quantity"],
            order_type=OrderType.MARKET,
            auto_create_stops=True,  # Automatically create stop & target orders
            stop_loss_pct=strategy["stop_loss_pct"],
            take_profit_pct=strategy["take_profit_pct"]
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
        
        # SCALE-IN Rule (for existing positions)
        scalein_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": ticker,
                "signal": "BUY",
                "confidence": lambda c: c >= (strategy["confidence_threshold"] + 0.05)  # Higher threshold for scale-in
            }
        )
        
        # Use the formal LinkedScaleInAction (replaces custom ScaleInAction)
        scalein_action = LinkedScaleInAction(
            symbol=ticker,
            scale_quantity=strategy["quantity"] // 2,  # Scale in with half the original quantity
            trigger_profit_pct=0.02  # Only scale-in if position is 2%+ profitable
        )
        
        scalein_rule = Rule(
            rule_id=f"{ticker.lower()}_scalein_rule",
            name=f"{ticker} Scale-In on Very High Confidence",
            description=f"Scale into existing {ticker} position when confidence >= {strategy['confidence_threshold'] + 0.05}",
            condition=scalein_condition,
            action=scalein_action,
            priority=90,  # Lower priority than initial entry
            cooldown_seconds=strategy["cooldown_minutes"] * 60 * 2  # Longer cooldown for scale-ins
        )
        
        # SELL Rule  
        sell_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": ticker,
                "signal": "SELL",
                "confidence": lambda c: c >= strategy["confidence_threshold"]
            }
        )
        
        sell_action = LinkedCloseAllAction(
            symbol=ticker,
            reason="Sell signal from prediction API"
        )
        
        sell_rule = Rule(
            rule_id=f"{ticker.lower()}_sell_rule", 
            name=f"{ticker} Sell on High Confidence",
            description=f"Sell {ticker} when confidence >= {strategy['confidence_threshold']}",
            condition=sell_condition,
            action=sell_action,
            priority=100,
            cooldown_seconds=strategy["cooldown_minutes"] * 60
        )
        
        # Register all rules
        self.rule_engine.register_rule(buy_rule)
        self.rule_engine.register_rule(scalein_rule)  # Add scale-in rule
        self.rule_engine.register_rule(sell_rule)
        
        logger.info(f"📊 Created strategy for {ticker} (confidence >= {strategy['confidence_threshold']}, scale-in >= {strategy['confidence_threshold'] + 0.05})")
    
    def _create_eod_closure_rule(self):
        """Create end-of-day position closure rule."""
        # End-of-Day Close Rule (close ALL positions and orders)
        for strategy in self.strategies:
            ticker = strategy["ticker"]
            eod_condition = TimeCondition(
                time_check=lambda: datetime.now().time() >= time(15, 30)  # 3:30 PM ET
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
                priority=200  # High priority
            )
            
            self.rule_engine.register_rule(eod_rule)
        
        logger.info("📅 Created end-of-day closure rule")
    
    async def start_trading(self):
        """Start the trading system."""
        logger.info("🔥 Starting trading system...")
        
        # Configure API monitoring for our tickers
        tickers = ["AAPL", "MSFT", "TSLA", "NVDA"]
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
            while self.running:
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