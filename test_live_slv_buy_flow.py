#!/usr/bin/env python3
"""
Live Test: SLV BUY Signal Flow
==============================

This test simulates receiving a SLV BUY prediction with 77% confidence
and tracks the complete order flow including:
- Main BUY order
- Stop loss order
- Take profit order
- Double down order

Usage:
    python test_live_slv_buy_flow.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, Any

# Import all necessary components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.event.order import OrderEvent, NewOrderEvent, OrderStatusEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderConclusionManager,
    LinkedDoubleDownFillManager
)
from src.rule.base import Rule
from src.order import OrderType
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.sizer import PositionSizer
from src.price.service import PriceService
from src.indicators.manager import IndicatorManager

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_slv_buy_flow.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Reduce verbosity of specific loggers
logging.getLogger('ibapi').setLevel(logging.WARNING)
logging.getLogger('ibapi.client').setLevel(logging.WARNING)
logging.getLogger('ibapi.wrapper').setLevel(logging.WARNING)
logging.getLogger('ibapi.decoder').setLevel(logging.WARNING)
logging.getLogger('ibapi.reader').setLevel(logging.WARNING)
logging.getLogger('ibapi.connection').setLevel(logging.WARNING)
logging.getLogger('ibapi.utils').setLevel(logging.WARNING)
logging.getLogger('src.price.service').setLevel(logging.INFO)


class SLVBuyFlowTest:
    """Test class for SLV BUY signal flow."""
    
    def __init__(self):
        self.event_bus = None
        self.tws_connection = None
        self.rule_engine = None
        self.order_manager = None
        self.position_tracker = None
        self.orders_created = []
        self.test_complete = False
        
    async def initialize(self):
        """Initialize all system components."""
        logger.info("=" * 80)
        logger.info("INITIALIZING SLV BUY FLOW TEST")
        logger.info("=" * 80)
        
        # Create event bus
        self.event_bus = EventBus()
        logger.info("Event bus created")
        
        # Subscribe to order events for tracking
        await self.event_bus.subscribe(NewOrderEvent, self.on_new_order)
        await self.event_bus.subscribe(OrderStatusEvent, self.on_order_status)
        logger.info("Subscribed to order events")
        
        # Setup TWS connection
        config = TWSConfig.from_env()
        logger.info(f"TWS Config: host={config.host}, port={config.port}, client_id={config.client_id}")
        
        self.tws_connection = TWSConnection(config)
        
        # Connect to TWS
        logger.info("Connecting to TWS...")
        connected = await self.tws_connection.connect()
        if not connected:
            raise Exception("Failed to connect to TWS")
        logger.info("Connected to TWS successfully")
        
        # Initialize components
        self.order_manager = OrderManager(self.event_bus, self.tws_connection)
        self.position_tracker = PositionTracker(self.event_bus)
        self.rule_engine = RuleEngine(self.event_bus)
        
        # Initialize indicator manager with TWS connection
        self.indicator_manager = IndicatorManager(self.tws_connection.minute_bar_manager)
        
        # Initialize price service
        self.price_service = PriceService(self.tws_connection)
        
        # Initialize position sizer
        self.position_sizer = PositionSizer(min_shares=1, max_shares=10000)
        
        # Initialize components
        await self.order_manager.initialize()
        await self.position_tracker.initialize()
        
        logger.info("Order manager and position tracker initialized")
        
        # Setup rule engine context
        self.rule_engine.update_context({
            "order_manager": self.order_manager,
            "position_tracker": self.position_tracker,
            "indicator_manager": self.indicator_manager,
            "price_service": self.price_service,
            "position_sizer": self.position_sizer,
            "account": {"equity": 100000},
            "prices": {}
        })
        
        logger.info("Rule engine context configured")
        
        # Setup conclusion manager
        self.conclusion_manager = LinkedOrderConclusionManager(
            context=self.rule_engine.context,
            event_bus=self.event_bus
        )
        await self.conclusion_manager.initialize()
        logger.info("Order conclusion manager initialized")
        
        # Setup double down fill manager
        self.doubledown_fill_manager = LinkedDoubleDownFillManager(
            context=self.rule_engine.context,
            event_bus=self.event_bus
        )
        await self.doubledown_fill_manager.initialize()
        logger.info("Double down fill manager initialized")
        
    def setup_slv_buy_rule(self):
        """Setup the SLV BUY rule."""
        logger.info("\n" + "=" * 80)
        logger.info("SETTING UP SLV BUY RULE")
        logger.info("=" * 80)
        
        # Create BUY condition for SLV with 0.5 threshold
        buy_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": "SLV",
                "signal": "BUY",
                "confidence": lambda c: c >= 0.50  # 50% threshold
            }
        )
        logger.info("Created BUY condition (threshold: 50%)")
        
        # Create BUY action with automatic stops
        buy_action = LinkedCreateOrderAction(
            symbol="SLV",
            quantity=10000,  # $10K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            stop_loss_pct=0.03,      # 3% stop loss
            take_profit_pct=0.06     # 6% take profit
        )
        logger.info("Created BUY action ($10K allocation, 3% stop, 6% target)")
        
        # Create the rule
        buy_rule = Rule(
            rule_id="slv_buy_test_rule",
            name="SLV Buy Test Rule",
            description="Test rule for SLV BUY signal processing",
            condition=buy_condition,
            action=buy_action,
            priority=100,
            cooldown_seconds=0  # No cooldown for testing
        )
        
        # Register the rule
        self.rule_engine.register_rule(buy_rule)
        logger.info(f"Registered rule: {buy_rule.rule_id}")
        
    async def simulate_slv_buy_signal(self):
        """Simulate receiving a SLV BUY signal with 77% confidence."""
        logger.info("\n" + "=" * 80)
        logger.info("SIMULATING SLV BUY SIGNAL")
        logger.info("=" * 80)
        
        # Get current SLV price
        try:
            current_price = await self.price_service.get_price("SLV")
            if current_price:
                logger.info(f"Current SLV price: ${current_price:.2f}")
                # Update context with price
                self.rule_engine.context["prices"]["SLV"] = current_price
            else:
                logger.warning("Could not get current SLV price")
                # Use a default price for testing
                current_price = 22.50
                self.rule_engine.context["prices"]["SLV"] = current_price
                logger.info(f"Using default price: ${current_price:.2f}")
        except Exception as e:
            logger.error(f"Error getting SLV price: {e}")
            current_price = 22.50
            self.rule_engine.context["prices"]["SLV"] = current_price
            logger.info(f"Using default price: ${current_price:.2f}")
        
        # Create the prediction signal event
        prediction_event = PredictionSignalEvent(
            symbol="SLV",
            signal="BUY",
            confidence=0.77,  # 77% confidence
            price=current_price,
            timestamp=datetime.now(),
            source="test_simulation"
        )
        
        logger.info(f"Created prediction event:")
        logger.info(f"   Symbol: {prediction_event.symbol}")
        logger.info(f"   Signal: {prediction_event.signal}")
        logger.info(f"   Confidence: {prediction_event.confidence:.1%}")
        logger.info(f"   Price: ${prediction_event.price:.2f}")
        
        # Start the rule engine
        await self.rule_engine.start()
        logger.info("Rule engine started")
        
        # Emit the prediction event
        logger.info("\nEMITTING PREDICTION EVENT...")
        await self.event_bus.emit(prediction_event)
        logger.info("Prediction event emitted")
        
        # Wait for processing - give more time for all orders to be created
        logger.info("Waiting for initial order creation...")
        await asyncio.sleep(3)
        
        # Log current context state
        if "SLV" in self.rule_engine.context:
            slv_context = self.rule_engine.context["SLV"]
            logger.info(f"SLV context after initial creation:")
            logger.info(f"   Main orders: {slv_context.get('main_orders', [])}")
            logger.info(f"   Stop orders: {slv_context.get('stop_orders', [])}")
            logger.info(f"   Target orders: {slv_context.get('target_orders', [])}")
        
    async def on_new_order(self, event: NewOrderEvent):
        """Track new orders created."""
        logger.info(f"\nNEW ORDER CREATED:")
        logger.info(f"   Order ID: {event.order_id}")
        logger.info(f"   Symbol: {event.symbol}")
        logger.info(f"   Type: {event.order_type}")
        logger.info(f"   Quantity: {event.quantity}")
        if event.limit_price:
            logger.info(f"   Limit Price: ${event.limit_price:.2f}")
        if event.stop_price:
            logger.info(f"   Stop Price: ${event.stop_price:.2f}")
        
        self.orders_created.append({
            "order_id": event.order_id,
            "symbol": event.symbol,
            "type": event.order_type,
            "quantity": event.quantity,
            "limit_price": event.limit_price,
            "stop_price": event.stop_price
        })
        
    async def on_order_status(self, event: OrderStatusEvent):
        """Track order status updates."""
        logger.info(f"\nORDER STATUS UPDATE:")
        logger.info(f"   Order ID: {event.order_id}")
        logger.info(f"   Status: {event.status.value}")
        logger.info(f"   Previous: {event.previous_status.value if event.previous_status else 'None'}")
        
    async def verify_orders(self):
        """Verify all expected orders were created."""
        logger.info("\n" + "=" * 80)
        logger.info("VERIFYING ORDERS CREATED")
        logger.info("=" * 80)
        
        # Check context for SLV
        if "SLV" in self.rule_engine.context:
            slv_context = self.rule_engine.context["SLV"]
            logger.info(f"\nSLV Context:")
            logger.info(f"   Side: {slv_context.get('side', 'N/A')}")
            logger.info(f"   Status: {slv_context.get('status', 'N/A')}")
            logger.info(f"   Main Orders: {len(slv_context.get('main_orders', []))}")
            logger.info(f"   Stop Orders: {len(slv_context.get('stop_orders', []))}")
            logger.info(f"   Target Orders: {len(slv_context.get('target_orders', []))}")
            logger.info(f"   Double Down Orders: {len(slv_context.get('doubledown_orders', []))}")
        else:
            logger.warning("No SLV context found!")
        
        # Summary of orders created
        logger.info(f"\nORDERS SUMMARY:")
        logger.info(f"   Total orders created: {len(self.orders_created)}")
        
        market_orders = [o for o in self.orders_created if o['type'] == OrderType.MARKET]
        stop_orders = [o for o in self.orders_created if o['type'] == OrderType.STOP]
        limit_orders = [o for o in self.orders_created if o['type'] == OrderType.LIMIT]
        
        logger.info(f"   Market orders: {len(market_orders)}")
        logger.info(f"   Stop orders: {len(stop_orders)}")
        logger.info(f"   Limit orders: {len(limit_orders)}")
        
        # Expected: 1 market (main), 1 stop, 1 limit (target), 1 limit (double down)
        expected_total = 4
        if len(self.orders_created) == expected_total:
            logger.info(f"\nSUCCESS: All {expected_total} expected orders were created!")
        else:
            logger.warning(f"\nWARNING: Expected {expected_total} orders but got {len(self.orders_created)}")
        
        # List all orders
        logger.info("\nDETAILED ORDER LIST:")
        for i, order in enumerate(self.orders_created, 1):
            logger.info(f"\n   Order #{i}:")
            logger.info(f"     ID: {order['order_id']}")
            logger.info(f"     Type: {order['type'].value}")
            logger.info(f"     Quantity: {order['quantity']}")
            if order['limit_price']:
                logger.info(f"     Limit: ${order['limit_price']:.2f}")
            if order['stop_price']:
                logger.info(f"     Stop: ${order['stop_price']:.2f}")
    
    async def cleanup(self):
        """Clean up test resources."""
        logger.info("\n" + "=" * 80)
        logger.info("CLEANING UP TEST")
        logger.info("=" * 80)
        
        # Cancel all created orders
        if self.orders_created and self.order_manager:
            logger.info(f"Cancelling {len(self.orders_created)} test orders...")
            for order in self.orders_created:
                try:
                    await self.order_manager.cancel_order(
                        order['order_id'], 
                        "Test cleanup"
                    )
                    logger.info(f"   Cancelled order {order['order_id']}")
                except Exception as e:
                    logger.error(f"   Error cancelling order {order['order_id']}: {e}")
        
        # Stop rule engine
        if self.rule_engine:
            await self.rule_engine.stop()
            logger.info("Rule engine stopped")
        
        # Disconnect TWS
        if self.tws_connection and self.tws_connection.is_connected():
            self.tws_connection.disconnect()
            logger.info("Disconnected from TWS")
        
        logger.info("\nTest cleanup complete")


async def main():
    """Main test function."""
    test = SLVBuyFlowTest()
    
    try:
        # Initialize system
        await test.initialize()
        
        # Setup SLV buy rule
        test.setup_slv_buy_rule()
        
        # Simulate SLV buy signal
        await test.simulate_slv_buy_signal()
        
        # Wait for orders to be created
        logger.info("\nWaiting for order processing...")
        await asyncio.sleep(5)
        
        # Verify orders
        await test.verify_orders()
        
        # Keep running for a bit to see any updates
        logger.info("\nMonitoring for 10 seconds...")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
    finally:
        # Always cleanup
        await test.cleanup()
        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SLV BUY SIGNAL FLOW TEST")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Connect to TWS")
    print("2. Setup a SLV BUY rule")
    print("3. Simulate a 77% confidence BUY signal")
    print("4. Track all orders created")
    print("5. Verify the complete order flow")
    print("\nNOTE: This will create REAL orders in TWS (paper trading)")
    print("=" * 80)
    
    response = input("\nProceed with test? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 