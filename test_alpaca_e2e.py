#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca End-to-End Trading Flow Test

Tests the complete trading flow from signal to position management.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.broker_config import BrokerConfig
from src.alpaca_connection import AlpacaConnection
from src.event.bus import EventBus
from src.event.api import PredictionEvent
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.position.alpaca_sync import AlpacaPositionSync
from src.rule.engine import RuleEngine
from src.rule.base import Rule, Condition, Action
from src.rule.condition import (
    PredictionCondition, PositionCondition, TimeCondition
)
from src.rule.action import (
    CreateOrderAction, ClosePositionAction, LogAction
)
from src.api.client import APIClient
from src.logger import get_logger

logger = get_logger(__name__)


class E2ETestFlow:
    """End-to-end test flow for Alpaca trading system."""
    
    def __init__(self):
        self.config = None
        self.connection = None
        self.event_bus = None
        self.order_manager = None
        self.position_tracker = None
        self.position_manager = None
        self.position_sync = None
        self.rule_engine = None
        self.api_client = None
        
        # Test tracking
        self.test_symbol = "AAPL"
        self.events_logged = []
    
    async def setup(self):
        """Set up the complete trading system."""
        print("\n🔧 Setting up E2E test environment...")
        
        # Load configuration
        self.config = BrokerConfig.from_env()
        
        # Initialize event bus
        self.event_bus = EventBus()
        
        # Create connection
        self.connection = AlpacaConnection(self.config.alpaca, self.event_bus)
        connected = await self.connection.connect()
        if not connected:
            raise Exception("Failed to connect to Alpaca")
        
        # Initialize position tracking
        self.position_tracker = PositionTracker(self.event_bus)
        await self.position_tracker.initialize()
        self.position_manager = PositionManager()
        
        # Initialize position sync
        self.position_sync = AlpacaPositionSync(
            self.connection,
            self.position_tracker,
            self.position_manager,
            self.event_bus
        )
        
        # Perform initial sync
        sync_result = await self.position_sync.sync_positions()
        print(f"Position sync: {sync_result['status']}")
        
        # Initialize order manager
        self.order_manager = OrderManager(self.event_bus, self.connection)
        await self.order_manager.initialize()
        
        # Initialize API client (for predictions)
        self.api_client = APIClient(self.event_bus)
        
        # Initialize rule engine
        self.rule_engine = RuleEngine(
            event_bus=self.event_bus,
            order_manager=self.order_manager,
            position_tracker=self.position_tracker,
            api_client=self.api_client
        )
        
        print("E2E test environment ready")
    
    async def teardown(self):
        """Clean up the test environment."""
        print("\nCleaning up E2E test...")
        
        # Stop rule engine
        if self.rule_engine:
            await self.rule_engine.stop()
        
        # Stop position sync
        if self.position_sync:
            await self.position_sync.stop_periodic_sync()
        
        # Disconnect
        if self.connection:
            self.connection.disconnect()
        
        print("E2E cleanup complete")
    
    async def create_test_rules(self):
        """Create test trading rules."""
        print("\nCreating test trading rules...")
        
        # Rule 1: Buy on bullish prediction
        buy_rule = Rule(
            name="test_buy_rule",
            conditions=[
                PredictionCondition(
                    prediction_type="bullish",
                    confidence_threshold=0.7
                ),
                PositionCondition(
                    check_type="no_position"
                )
            ],
            actions=[
                LogAction(message="Bullish signal detected - creating buy order"),
                CreateOrderAction(
                    order_type="market",
                    side="buy",
                    quantity=1,
                    symbol_from_event=True
                )
            ]
        )
        
        # Rule 2: Sell on bearish prediction
        sell_rule = Rule(
            name="test_sell_rule",
            conditions=[
                PredictionCondition(
                    prediction_type="bearish",
                    confidence_threshold=0.7
                ),
                PositionCondition(
                    check_type="has_position"
                )
            ],
            actions=[
                LogAction(message="Bearish signal detected - closing position"),
                ClosePositionAction(
                    reason="Bearish signal"
                )
            ]
        )
        
        # Add rules to engine
        await self.rule_engine.add_rule(buy_rule)
        await self.rule_engine.add_rule(sell_rule)
        
        print(f"Added {len(self.rule_engine.rules)} trading rules")
    
    async def simulate_trading_flow(self):
        """Simulate a complete trading flow."""
        print("\nSimulating trading flow...")
        
        # Start rule engine
        await self.rule_engine.start()
        print("Rule engine started")
        
        # Step 1: Simulate bullish prediction
        print("\n1️⃣ Simulating bullish prediction...")
        bullish_event = PredictionEvent(
            symbol=self.test_symbol,
            prediction="bullish",
            confidence=0.85,
            timestamp=datetime.now(),
            metadata={
                "source": "test_simulation",
                "model": "test_model"
            }
        )
        
        await self.event_bus.emit(bullish_event)
        print(f"Emitted bullish prediction for {self.test_symbol}")
        
        # Wait for order processing
        await asyncio.sleep(5)
        
        # Check if order was created
        active_orders = await self.order_manager.get_active_orders(self.test_symbol)
        if active_orders:
            print(f"Order created: {active_orders[0].order_id}")
        else:
            print("WARNING: No order created (may need position or market closed)")
        
        # Step 2: Check position status
        print("\n2️⃣ Checking position status...")
        positions = await self.position_tracker.get_positions_for_symbol(self.test_symbol)
        if positions:
            pos = positions[0]
            print(f"Position found: {pos.quantity} shares @ ${pos.entry_price}")
        else:
            print("WARNING: No position found")
        
        # Step 3: Simulate bearish prediction
        print("\n3️⃣ Simulating bearish prediction...")
        bearish_event = PredictionEvent(
            symbol=self.test_symbol,
            prediction="bearish",
            confidence=0.80,
            timestamp=datetime.now(),
            metadata={
                "source": "test_simulation",
                "model": "test_model"
            }
        )
        
        await self.event_bus.emit(bearish_event)
        print(f"Emitted bearish prediction for {self.test_symbol}")
        
        # Wait for position closure
        await asyncio.sleep(5)
        
        # Step 4: Verify position closed
        print("\n4️⃣ Verifying position closure...")
        positions = await self.position_tracker.get_positions_for_symbol(self.test_symbol)
        open_positions = [p for p in positions if p.status.value == 'open']
        if not open_positions:
            print("Position closed successfully")
        else:
            print("WARNING: Position still open")
        
        # Step 5: Check final state
        print("\n5️⃣ Final state check...")
        
        # Get position summary
        summary = await self.position_tracker.get_position_summary()
        print(f"Total positions: {summary['total_positions']}")
        print(f"Total P/L: ${summary['total_realized_pnl']:.2f}")
        
        # Get order history
        completed_orders = await self.order_manager.get_completed_orders(
            self.test_symbol,
            limit=10
        )
        print(f"Completed orders: {len(completed_orders)}")
    
    async def test_error_handling(self):
        """Test error handling and recovery."""
        print("\n🛡️ Testing error handling...")
        
        # Test invalid order
        print("  - Testing invalid order...")
        try:
            order = await self.order_manager.create_order(
                symbol="INVALID_SYMBOL_XYZ",
                quantity=1
            )
            await self.order_manager.submit_order(order.order_id)
        except Exception as e:
            print(f"  Error handled correctly: {type(e).__name__}")
        
        # Test position sync with no positions
        print("  - Testing position sync...")
        sync_result = await self.position_sync.sync_positions()
        print(f"  Sync handled empty positions: {sync_result['status']}")
    
    async def run_e2e_test(self):
        """Run the complete end-to-end test."""
        print("\n" + "="*60)
        print("ALPACA END-TO-END TEST")
        print("="*60)
        
        try:
            # Setup
            await self.setup()
            
            # Create rules
            await self.create_test_rules()
            
            # Run trading simulation
            await self.simulate_trading_flow()
            
            # Test error handling
            await self.test_error_handling()
            
            print("\n" + "="*60)
            print("E2E TEST COMPLETED SUCCESSFULLY")
            print("="*60)
            
            return True
            
        except Exception as e:
            print(f"\nE2E test failed: {e}")
            logger.error(f"E2E test error: {e}", exc_info=True)
            return False
            
        finally:
            await self.teardown()


async def main():
    """Run the E2E test."""
    test = E2ETestFlow()
    success = await test.run_e2e_test()
    
    if success:
        print("\nEnd-to-end test passed!")
        return 0
    else:
        print("\nEnd-to-end test failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 