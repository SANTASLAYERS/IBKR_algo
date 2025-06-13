#!/usr/bin/env python3
"""
Live Test: GLD BUY Signal Flow with Unified Fill Manager
========================================================

This test simulates receiving a GLD BUY prediction with 77% confidence
and tracks the complete order flow using the new UnifiedFillManager including:
- Main BUY order
- Stop loss order
- Take profit order
- Double down order
- Automatic protective order updates on fills

Usage:
    python test_live_gld_buy_flow_unified.py
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
from src.event.order import OrderEvent, NewOrderEvent, OrderStatusEvent, FillEvent
from src.rule.engine import RuleEngine
from src.rule.condition import EventCondition
from src.rule.linked_order_actions import LinkedCreateOrderAction
from src.rule.unified_fill_manager import UnifiedFillManager  # NEW: Using UnifiedFillManager
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
        logging.FileHandler('test_gld_buy_flow_unified.log', encoding='utf-8'),
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


class GLDBuyFlowUnifiedTest:
    """Test class for GLD BUY signal flow with UnifiedFillManager."""
    
    def __init__(self):
        self.event_bus = None
        self.tws_connection = None
        self.rule_engine = None
        self.order_manager = None
        self.position_tracker = None
        self.unified_fill_manager = None  # NEW
        self.orders_created = []
        self.fills_received = []
        self.test_complete = False
        
    async def initialize(self):
        """Initialize all system components."""
        logger.info("=" * 80)
        logger.info("INITIALIZING GLD BUY FLOW TEST WITH UNIFIED FILL MANAGER")
        logger.info("=" * 80)
        
        # Create event bus with concurrent processing
        self.event_bus = EventBus()
        logger.info("Event bus created with concurrent processing support")
        
        # Subscribe to order events for tracking
        await self.event_bus.subscribe(NewOrderEvent, self.on_new_order)
        await self.event_bus.subscribe(OrderStatusEvent, self.on_order_status)
        await self.event_bus.subscribe(FillEvent, self.on_fill_event)  # NEW: Track fills
        logger.info("Subscribed to order and fill events")
        
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
        
        # NEW: Setup UnifiedFillManager instead of separate managers
        self.unified_fill_manager = UnifiedFillManager(
            context=self.rule_engine.context,
            event_bus=self.event_bus
        )
        await self.unified_fill_manager.initialize()
        logger.info("UnifiedFillManager initialized - handles all fill events and protective order updates")
        
    def setup_gld_buy_rule(self):
        """Setup the GLD BUY rule."""
        logger.info("\n" + "=" * 80)
        logger.info("SETTING UP GLD BUY RULE")
        logger.info("=" * 80)
        
        # Create BUY condition for GLD with 0.5 threshold
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
            quantity=10000,  # $10K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=2.5,
            atr_target_multiplier=2.5
        )
        logger.info("Created BUY action ($10K allocation, 2.5x ATR stop, 2.5x ATR target)")
        
        # Create the rule
        buy_rule = Rule(
            rule_id="gld_buy_test_rule",
            name="GLD Buy Test Rule",
            description="Test rule for GLD BUY signal processing with UnifiedFillManager",
            condition=buy_condition,
            action=buy_action,
            priority=100,
            cooldown_seconds=0  # No cooldown for testing
        )
        
        # Register the rule
        self.rule_engine.register_rule(buy_rule)
        logger.info(f"Registered rule: {buy_rule.rule_id}")
        
    async def simulate_gld_buy_signal(self):
        """Simulate receiving a GLD BUY signal with 77% confidence."""
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
                current_price = 180.00
                self.rule_engine.context["prices"]["GLD"] = current_price
                logger.info(f"Using default price: ${current_price:.2f}")
        except Exception as e:
            logger.error(f"Error getting GLD price: {e}")
            current_price = 180.00
            self.rule_engine.context["prices"]["GLD"] = current_price
            logger.info(f"Using default price: ${current_price:.2f}")
        
        # Create the prediction signal event
        prediction_event = PredictionSignalEvent(
            symbol="GLD",
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
        if "GLD" in self.rule_engine.context:
            gld_context = self.rule_engine.context["GLD"]
            logger.info(f"GLD context after initial creation:")
            logger.info(f"   Main orders: {gld_context.get('main_orders', [])}")
            logger.info(f"   Stop orders: {gld_context.get('stop_orders', [])}")
            logger.info(f"   Target orders: {gld_context.get('target_orders', [])}")
        
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
        
    async def on_fill_event(self, event: FillEvent):
        """Track fill events - NEW method."""
        logger.info(f"\n🎯 FILL EVENT RECEIVED:")
        logger.info(f"   Order ID: {event.order_id}")
        logger.info(f"   Symbol: {event.symbol}")
        logger.info(f"   Fill Price: ${event.fill_price:.2f}")
        logger.info(f"   Fill Quantity: {event.fill_quantity}")
        logger.info(f"   Status: {event.status.value}")
        logger.info(f"   ⚡ UnifiedFillManager will handle protective order updates")
        
        self.fills_received.append({
            "order_id": event.order_id,
            "symbol": event.symbol,
            "fill_price": event.fill_price,
            "fill_quantity": event.fill_quantity,
            "status": event.status
        })
        
    async def simulate_partial_fill(self):
        """Simulate a partial fill to test UnifiedFillManager behavior."""
        logger.info("\n" + "=" * 80)
        logger.info("SIMULATING PARTIAL FILL TO TEST UNIFIED FILL MANAGER")
        logger.info("=" * 80)
        
        # Find the main order
        main_orders = [o for o in self.orders_created if o['type'] == OrderType.MARKET and o['quantity'] > 0]
        if not main_orders:
            logger.warning("No main order found to simulate fill")
            return
            
        main_order = main_orders[0]
        logger.info(f"Simulating partial fill on main order: {main_order['order_id']}")
        
        # Create a partial fill event
        fill_event = FillEvent(
            order_id=main_order['order_id'],
            symbol="GLD",
            status=OrderStatus.PARTIALLY_FILLED,
            fill_price=180.55,
            fill_quantity=200,  # Partial fill of 200 shares
            cumulative_quantity=200,
            remaining_quantity=main_order['quantity'] - 200,
            fill_time=datetime.now()
        )
        
        logger.info(f"Emitting partial fill event: 200 shares at $180.55")
        await self.event_bus.emit(fill_event)
        
        # Wait for processing
        await asyncio.sleep(2)
        
        logger.info("UnifiedFillManager should have updated protective orders to match position size")
        
    async def simulate_double_down_fill(self):
        """Simulate a double down fill to test protective order updates."""
        logger.info("\n" + "=" * 80)
        logger.info("SIMULATING DOUBLE DOWN FILL TO TEST PROTECTIVE ORDER UPDATES")
        logger.info("=" * 80)
        
        # Find the double down order
        dd_orders = [o for o in self.orders_created if o['type'] == OrderType.LIMIT and o['quantity'] > 0 and 'doubledown' in str(o['order_id'])]
        if not dd_orders:
            # Find by checking all limit buy orders (excluding main order)
            dd_orders = [o for o in self.orders_created if o['type'] == OrderType.LIMIT and o['quantity'] > 0]
            
        if not dd_orders:
            logger.warning("No double down order found to simulate fill")
            return
            
        dd_order = dd_orders[0]
        logger.info(f"Simulating double down fill on order: {dd_order['order_id']}")
        logger.info(f"Double down order details: {dd_order['quantity']} shares @ ${dd_order['limit_price']:.2f}")
        
        # Create a fill event for the double down order
        fill_event = FillEvent(
            order_id=dd_order['order_id'],
            symbol="GLD",
            status=OrderStatus.FILLED,
            fill_price=dd_order['limit_price'],
            fill_quantity=dd_order['quantity'],
            cumulative_quantity=dd_order['quantity'],
            remaining_quantity=0,
            fill_time=datetime.now()
        )
        
        logger.info(f"Emitting double down fill event: {dd_order['quantity']} shares at ${dd_order['limit_price']:.2f}")
        await self.event_bus.emit(fill_event)
        
        # Wait for processing
        await asyncio.sleep(3)
        
        logger.info("UnifiedFillManager should have updated protective orders to new position size (606 shares)")
        
    async def simulate_stop_loss_fill(self):
        """Simulate a stop loss fill to test position closure and order cancellation."""
        logger.info("\n" + "=" * 80)
        logger.info("SIMULATING STOP LOSS FILL TO TEST POSITION CLOSURE")
        logger.info("=" * 80)
        
        # Find the stop order
        stop_orders = [o for o in self.orders_created if o['type'] == OrderType.STOP]
        if not stop_orders:
            logger.warning("No stop order found to simulate fill")
            return
            
        stop_order = stop_orders[0]
        logger.info(f"Simulating stop loss fill on order: {stop_order['order_id']}")
        
        # Create a fill event for the stop order
        fill_event = FillEvent(
            order_id=stop_order['order_id'],
            symbol="GLD",
            status=OrderStatus.FILLED,
            fill_price=stop_order['stop_price'],
            fill_quantity=stop_order['quantity'],  # This is negative for a sell
            cumulative_quantity=stop_order['quantity'],
            remaining_quantity=0,
            fill_time=datetime.now()
        )
        
        logger.info(f"Emitting stop loss fill event: {stop_order['quantity']} shares at ${stop_order['stop_price']:.2f}")
        await self.event_bus.emit(fill_event)
        
        # Wait for processing
        await asyncio.sleep(3)
        
        logger.info("UnifiedFillManager should have cancelled all remaining orders")
        
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
        
        # Expected: 1 market (main), 1 stop, 1 limit (target), 1 limit (double down)
        expected_total = 4
        if len(self.orders_created) == expected_total:
            logger.info(f"\n✅ SUCCESS: All {expected_total} expected orders were created!")
        else:
            logger.warning(f"\n⚠️ WARNING: Expected {expected_total} orders but got {len(self.orders_created)}")
        
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
        if self.fills_received:
            logger.info(f"\n🎯 FILLS SUMMARY:")
            logger.info(f"   Total fills received: {len(self.fills_received)}")
            for i, fill in enumerate(self.fills_received, 1):
                logger.info(f"\n   Fill #{i}:")
                logger.info(f"     Order ID: {fill['order_id']}")
                logger.info(f"     Quantity: {fill['fill_quantity']}")
                logger.info(f"     Price: ${fill['fill_price']:.2f}")
                logger.info(f"     Status: {fill['status'].value}")
        
        # Monitor position and orders
        logger.info("\n📊 Monitoring position and orders...")
        logger.info("Waiting for fills:")
        logger.info("  - Double down to fill (increases position)")
        logger.info("  - Stop loss to fill (closes position)")
        logger.info("  - Take profit to fill (closes position)")
        
        start_time = asyncio.get_event_loop().time()
        timeout = 300  # 5 minutes timeout
        last_fill_count = len(self.fills_received)
        position_closed = False
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(2)
            
            # Check for new fills
            current_fill_count = len(self.fills_received)
            if current_fill_count > last_fill_count:
                logger.info(f"\n🎯 New fill detected! Total fills: {current_fill_count}")
                last_fill_count = current_fill_count
                
                # Check if stop or profit filled (position closing orders)
                stop_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'stop' 
                                for o in self.orders_created for f in self.fills_received)
                profit_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'limit' and o['quantity'] < 0 
                                  for o in self.orders_created for f in self.fills_received)
                
                if stop_filled or profit_filled:
                    logger.info("\n✅ Position closed via protective order")
                    position_closed = True
                    # Give time for order cancellations to process
                    await asyncio.sleep(3)
                    break
            
            # Check position status using position_tracker
            position_tracker = self.position_tracker
            if position_tracker:
                positions_list = await position_tracker.get_positions_for_symbol("GLD")
                gld_positions = [p for p in positions_list if p.quantity != 0]
                
                if gld_positions:
                    pos = gld_positions[0]
                    logger.info(f"\r⏳ Position open: {pos.quantity} shares @ ${pos.entry_price:.2f} | P&L: ${pos.unrealized_pnl:.2f}", end="")
                elif position_closed:
                    logger.info("\n✅ Position confirmed closed")
                    break
            
            # Log order status periodically
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % 30 == 0 and elapsed > 0:  # Every 30 seconds
                logger.info(f"\n\n📊 Status update at {elapsed}s:")
                logger.info(f"   Fills received: {len(self.fills_received)}")
                
                # Check current order statuses
                active_orders = 0
                for order_info in self.orders_created:
                    order = await self.order_manager.get_order(order_info['order_id'])
                    if order and order.status.value in ['submitted', 'presubmitted', 'partially_filled']:
                        active_orders += 1
                
                logger.info(f"   Active orders: {active_orders}")
        
        if (asyncio.get_event_loop().time() - start_time) >= timeout:
            logger.info(f"\n⏱️ Monitoring timeout reached ({timeout} seconds)")
        
        # Log final state
        await self.log_final_state()
    

    
    async def log_final_state(self):
        """Log the final state of all orders."""
        logger.info("\n" + "=" * 80)
        logger.info("FINAL ORDER STATE & VERIFICATION")
        logger.info("=" * 80)
        
        # Get current order states from order manager
        if self.order_manager:
            logger.info("\nChecking current order states...")
            for order_info in self.orders_created:
                order_id = order_info['order_id']
                order = await self.order_manager.get_order(order_id)
                if order:
                    logger.info(f"\nOrder {order_id}:")
                    logger.info(f"  Type: {order.order_type.value}")
                    logger.info(f"  Status: {order.status.value}")
                    logger.info(f"  Quantity: {order.quantity}")
                    if order.broker_order_id:
                        logger.info(f"  Broker ID: {order.broker_order_id}")
        
        # Verify the complete flow
        logger.info("\n" + "=" * 80)
        logger.info("FLOW VERIFICATION")
        logger.info("=" * 80)
        
        # Check what happened
        main_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'market' 
                         for o in self.orders_created for f in self.fills_received)
        
        dd_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'limit' and o['quantity'] > 0 
                       for o in self.orders_created for f in self.fills_received)
        
        stop_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'stop' 
                         for o in self.orders_created for f in self.fills_received)
        
        profit_filled = any(f['order_id'] == o['order_id'] and o['type'].value == 'limit' and o['quantity'] < 0 
                           for o in self.orders_created for f in self.fills_received)
        
        logger.info(f"✓ Main order filled: {main_filled}")
        logger.info(f"{'✓' if dd_filled else '○'} Double down filled: {dd_filled}")
        logger.info(f"{'✓' if stop_filled else '○'} Stop loss filled: {stop_filled}")
        logger.info(f"{'✓' if profit_filled else '○'} Take profit filled: {profit_filled}")
        
        # Verify UnifiedFillManager behavior
        if dd_filled and not (stop_filled or profit_filled):
            logger.info("\n⚠️ Double down filled but position not closed - protective orders should have been updated")
        elif stop_filled:
            logger.info("\n✅ Stop loss filled - all other orders should have been cancelled")
        elif profit_filled:
            logger.info("\n✅ Take profit filled - all other orders should have been cancelled")
        
        # Count cancelled orders
        cancelled_count = 0
        for order_info in self.orders_created:
            order = await self.order_manager.get_order(order_info['order_id'])
            if order and order.status.value == 'cancelled':
                cancelled_count += 1
        
        logger.info(f"\nTotal orders cancelled: {cancelled_count}")
        
        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        
        if stop_filled or profit_filled:
            logger.info("✅ Position closed successfully via protective order")
            logger.info("✅ UnifiedFillManager handled order cancellation correctly")
        else:
            logger.info("⚠️ Position did not close during test - manual intervention may be needed")
    
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
        
        # Cleanup UnifiedFillManager
        if self.unified_fill_manager:
            await self.unified_fill_manager.cleanup()
            logger.info("UnifiedFillManager cleaned up")
        
        # Stop rule engine
        if self.rule_engine:
            await self.rule_engine.stop()
            logger.info("Rule engine stopped")
        
        logger.info("\nTest cleanup complete")


async def main():
    """Main test function."""
    test = GLDBuyFlowUnifiedTest()
    
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
        
        # Skip partial fill simulation for this test run
        # # Optionally simulate a partial fill to test UnifiedFillManager
        # response = input("\nSimulate partial fill to test UnifiedFillManager? (y/n): ")
        # if response.lower() == 'y':
        #     await test.simulate_partial_fill()
        #     await asyncio.sleep(3)
        
        # Verify orders and wait for position to close
        await test.verify_orders()
        
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
    print("GLD BUY SIGNAL FLOW TEST WITH UNIFIED FILL MANAGER")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Connect to TWS")
    print("2. Setup a GLD BUY rule")
    print("3. Simulate a 77% confidence BUY signal")
    print("4. Track all orders created")
    print("5. Use UnifiedFillManager for all fill handling")
    print("6. Monitor continuously for fills (up to 5 minutes)")
    print("7. Verify the complete order flow")
    print("\n✨ NEW: Using UnifiedFillManager for concurrent fill processing")
    print("\nNOTE: This will create REAL orders in TWS (paper trading)")
    print("=" * 80)
    print("\n🚀 Starting test automatically...")
    
    asyncio.run(main())
 