#!/usr/bin/env python3
"""
Live Test: Unified Fill Manager with GLD
========================================

This test demonstrates the UnifiedFillManager handling:
- Main order fills
- Protective order updates on fills
- Double down fills
- Partial fills on protective orders

Usage:
    python test_unified_fill_manager_gld_live.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Import all necessary components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent
from src.event.order import OrderEvent, NewOrderEvent, OrderStatusEvent, FillEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import LinkedCreateOrderAction
from src.rule.unified_fill_manager import UnifiedFillManager
from src.rule.base import Rule
from src.order import OrderType, OrderStatus
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
        logging.FileHandler('test_unified_fill_manager_gld.log', encoding='utf-8'),
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


class UnifiedFillManagerTest:
    """Test class for UnifiedFillManager with GLD."""
    
    def __init__(self):
        self.event_bus = None
        self.tws_connection = None
        self.rule_engine = None
        self.order_manager = None
        self.position_tracker = None
        self.unified_fill_manager = None
        self.orders_created = []
        self.fills_received = []
        self.test_complete = False
        
    async def initialize(self):
        """Initialize all system components."""
        logger.info("=" * 80)
        logger.info("INITIALIZING UNIFIED FILL MANAGER TEST")
        logger.info("=" * 80)
        
        # Create event bus
        self.event_bus = EventBus()
        logger.info("Event bus created")
        
        # Subscribe to order events for tracking
        await self.event_bus.subscribe(NewOrderEvent, self.on_new_order)
        await self.event_bus.subscribe(OrderStatusEvent, self.on_order_status)
        await self.event_bus.subscribe(FillEvent, self.on_order_filled)
        logger.info("Subscribed to order events")
        
        # Setup TWS connection with unique client ID
        config = TWSConfig.from_env()
        # Use a different client ID to avoid conflicts
        config.client_id = 999  # Unique ID for this test
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
        
        # Setup UnifiedFillManager
        self.unified_fill_manager = UnifiedFillManager(
            context=self.rule_engine.context,
            event_bus=self.event_bus
        )
        await self.unified_fill_manager.initialize()
        logger.info("UnifiedFillManager initialized")
        
    def setup_gld_buy_rule(self):
        """Setup the GLD BUY rule."""
        logger.info("\n" + "=" * 80)
        logger.info("SETTING UP GLD BUY RULE")
        logger.info("=" * 80)
        
        # Create BUY condition for GLD
        buy_condition = EventCondition(
            event_type=PredictionSignalEvent,
            field_conditions={
                "symbol": "GLD",
                "signal": "BUY",
                "confidence": lambda c: c >= 0.50  # 50% threshold
            }
        )
        logger.info("Created BUY condition (threshold: 50%)")
        
        # Create BUY action with automatic stops using ATR
        buy_action = LinkedCreateOrderAction(
            symbol="GLD",
            quantity=300,  # 300 shares as requested
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=1.5,      # 1.5x ATR for stop loss
            atr_target_multiplier=1.5     # 1.5x ATR for take profit
        )
        logger.info("Created BUY action (300 shares, 1.5x ATR stop, 1.5x ATR target)")
        
        # Create the rule
        buy_rule = Rule(
            rule_id="gld_buy_test_rule",
            name="GLD Buy Test Rule",
            description="Test rule for GLD BUY signal processing",
            condition=buy_condition,
            action=buy_action,
            priority=100,
            cooldown_seconds=0  # No cooldown for testing
        )
        
        # Register the rule
        self.rule_engine.register_rule(buy_rule)
        logger.info(f"Registered rule: {buy_rule.rule_id}")
        
    async def simulate_gld_buy_signal(self):
        """Simulate receiving a GLD BUY signal."""
        logger.info("\n" + "=" * 80)
        logger.info("SIMULATING GLD BUY SIGNAL")
        logger.info("=" * 80)
        
        # Get current GLD price
        try:
            current_price = await self.price_service.get_price("GLD")
            if current_price:
                logger.info(f"Current GLD price: ${current_price:.2f}")
                # Update context with price
                self.rule_engine.context["prices"]["GLD"] = current_price
            else:
                logger.warning("Could not get current GLD price")
                # Use a default price for testing
                current_price = 245.00
                self.rule_engine.context["prices"]["GLD"] = current_price
                logger.info(f"Using default price: ${current_price:.2f}")
        except Exception as e:
            logger.error(f"Error getting GLD price: {e}")
            current_price = 245.00
            self.rule_engine.context["prices"]["GLD"] = current_price
            logger.info(f"Using default price: ${current_price:.2f}")
        
        # Create the prediction signal event
        prediction_event = PredictionSignalEvent(
            symbol="GLD",
            signal="BUY",
            confidence=0.75,  # 75% confidence
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
        
        # Wait for processing
        logger.info("Waiting for initial order creation...")
        await asyncio.sleep(3)
        
        # Log current context state
        if "GLD" in self.rule_engine.context:
            gld_context = self.rule_engine.context["GLD"]
            logger.info(f"GLD context after initial creation:")
            logger.info(f"   Main orders: {gld_context.get('main_orders', [])}")
            logger.info(f"   Stop orders: {gld_context.get('stop_orders', [])}")
            logger.info(f"   Target orders: {gld_context.get('target_orders', [])}")
        
    async def on_new_order(self, event: NewOrderEvent):
        """Track new orders created."""
        logger.info(f"\n🆕 NEW ORDER CREATED:")
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
        logger.info(f"\n📊 ORDER STATUS UPDATE:")
        logger.info(f"   Order ID: {event.order_id}")
        logger.info(f"   Status: {event.status.value}")
        logger.info(f"   Previous: {event.previous_status.value if event.previous_status else 'None'}")
        
    async def on_order_filled(self, event: FillEvent):
        """Track order fills - this is where UnifiedFillManager acts."""
        logger.info(f"\n✅ ORDER FILLED:")
        logger.info(f"   Order ID: {event.order_id}")
        logger.info(f"   Symbol: {event.symbol}")
        logger.info(f"   Filled Qty: {event.fill_quantity}")
        logger.info(f"   Fill Price: ${event.fill_price:.2f}")
        logger.info(f"   Is Partial: {event.is_partial}")
        
        self.fills_received.append({
            "order_id": event.order_id,
            "symbol": event.symbol,
            "filled_quantity": event.fill_quantity,
            "average_price": event.fill_price,
            "is_partial": event.is_partial
        })
        
        # Log protective order status after fill
        await asyncio.sleep(1)  # Give UnifiedFillManager time to process
        if "GLD" in self.rule_engine.context:
            gld_context = self.rule_engine.context["GLD"]
            logger.info(f"\n📋 GLD Context After Fill:")
            logger.info(f"   Position: {gld_context.get('position', 0)}")
            logger.info(f"   Stop orders: {gld_context.get('stop_orders', [])}")
            logger.info(f"   Target orders: {gld_context.get('target_orders', [])}")
            
            # Check protective order quantities
            if gld_context.get('stop_orders'):
                for order_id in gld_context['stop_orders']:
                    order = self.order_manager.get_order(order_id)
                    if order:
                        logger.info(f"   Stop order {order_id}: qty={order.quantity}")
                        
            if gld_context.get('target_orders'):
                for order_id in gld_context['target_orders']:
                    order = self.order_manager.get_order(order_id)
                    if order:
                        logger.info(f"   Target order {order_id}: qty={order.quantity}")
        
    async def verify_orders(self):
        """Verify all expected orders were created."""
        logger.info("\n" + "=" * 80)
        logger.info("VERIFYING ORDERS CREATED")
        logger.info("=" * 80)
        
        # Check context for GLD
        if "GLD" in self.rule_engine.context:
            gld_context = self.rule_engine.context["GLD"]
            logger.info(f"\nGLD Context:")
            logger.info(f"   Side: {gld_context.get('side', 'N/A')}")
            logger.info(f"   Status: {gld_context.get('status', 'N/A')}")
            logger.info(f"   Position: {gld_context.get('position', 0)}")
            logger.info(f"   Main Orders: {len(gld_context.get('main_orders', []))}")
            logger.info(f"   Stop Orders: {len(gld_context.get('stop_orders', []))}")
            logger.info(f"   Target Orders: {len(gld_context.get('target_orders', []))}")
            logger.info(f"   Double Down Orders: {len(gld_context.get('doubledown_orders', []))}")
        else:
            logger.warning("No GLD context found!")
        
        # Summary of orders created
        logger.info(f"\nORDERS SUMMARY:")
        logger.info(f"   Total orders created: {len(self.orders_created)}")
        
        market_orders = [o for o in self.orders_created if o['type'] == OrderType.MARKET]
        stop_orders = [o for o in self.orders_created if o['type'] == OrderType.STOP]
        limit_orders = [o for o in self.orders_created if o['type'] == OrderType.LIMIT]
        
        logger.info(f"   Market orders: {len(market_orders)}")
        logger.info(f"   Stop orders: {len(stop_orders)}")
        logger.info(f"   Limit orders: {len(limit_orders)}")
        
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
                
        # Summary of fills
        logger.info(f"\nFILLS SUMMARY:")
        logger.info(f"   Total fills received: {len(self.fills_received)}")
        for i, fill in enumerate(self.fills_received, 1):
            logger.info(f"\n   Fill #{i}:")
            logger.info(f"     Order ID: {fill['order_id']}")
            logger.info(f"     Quantity: {fill['filled_quantity']}")
            logger.info(f"     Avg Price: ${fill['average_price']:.2f}")
            logger.info(f"     Partial: {fill['is_partial']}")
    
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
        
        # UnifiedFillManager doesn't need explicit cleanup
        logger.info("UnifiedFillManager cleanup not needed (event-based)")
        
        logger.info("\nTest cleanup complete")


async def main():
    """Main test function."""
    test = UnifiedFillManagerTest()
    
    try:
        # Initialize system
        await test.initialize()
        
        # Setup GLD buy rule
        test.setup_gld_buy_rule()
        
        # Simulate GLD buy signal
        await test.simulate_gld_buy_signal()
        
        # Wait for orders to be created
        logger.info("\nWaiting for order processing...")
        await asyncio.sleep(5)
        
        # Verify orders
        await test.verify_orders()
        
        # Keep running for a bit to see any updates
        logger.info("\n📍 MONITORING FOR FILLS AND UPDATES...")
        logger.info("You can now manually fill orders in TWS to test UnifiedFillManager")
        logger.info("Press Ctrl+C when done testing")
        
        # Monitor for fills
        while True:
            await asyncio.sleep(10)
            logger.info("Still monitoring... (Press Ctrl+C to stop)")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
    finally:
        # Always cleanup
        await test.cleanup()
        
        # Disconnect TWS at the very end
        if test.tws_connection and test.tws_connection.is_connected():
            test.tws_connection.disconnect()
            logger.info("Disconnected from TWS")
        
        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("UNIFIED FILL MANAGER TEST WITH GLD")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Connect to TWS")
    print("2. Setup a GLD BUY rule (300 shares)")
    print("3. Create main order with protective orders")
    print("4. Monitor fills and verify UnifiedFillManager updates")
    print("\nYou can manually fill orders in TWS to test:")
    print("- Main order fill → protective orders update to position size")
    print("- Double down fill → protective orders update to new total")
    print("- Partial protective fill → other protective order updates")
    print("\nNOTE: This will create REAL orders in TWS (paper trading)")
    print("=" * 80)
    
    response = input("\nProceed with test? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.") 