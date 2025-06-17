#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Alpaca Event System Adaptations

This script tests the event system adaptations for Alpaca, including
order status updates and fill event generation.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alpaca_config import AlpacaConfig
from src.alpaca_connection import AlpacaConnection
from src.event.bus import EventBus
from src.event.order import OrderStatusEvent, FillEvent, CancelEvent, RejectEvent
from src.logger import get_logger

logger = get_logger(__name__)


class EventMonitor:
    """Monitor and display events."""
    
    def __init__(self):
        self.events_received = []
    
    async def on_order_status(self, event: OrderStatusEvent):
        """Handle order status events."""
        self.events_received.append(event)
        print(f"\n📊 Order Status Event:")
        print(f"  Order ID: {event.order_id}")
        print(f"  Symbol: {event.symbol}")
        print(f"  Status: {event.previous_status.value if event.previous_status else 'None'} -> {event.status.value}")
        print(f"  Time: {event.status_time}")
        print(f"  Reason: {event.reason}")
    
    async def on_fill(self, event: FillEvent):
        """Handle fill events."""
        self.events_received.append(event)
        print(f"\n💰 Fill Event:")
        print(f"  Order ID: {event.order_id}")
        print(f"  Symbol: {event.symbol}")
        print(f"  Fill Price: ${event.fill_price:.2f}")
        print(f"  Fill Quantity: {event.fill_quantity}")
        print(f"  Cumulative: {event.cumulative_quantity}")
        print(f"  Remaining: {event.remaining_quantity}")
        print(f"  Partial: {event.is_partial}")
    
    async def on_cancel(self, event: CancelEvent):
        """Handle cancel events."""
        self.events_received.append(event)
        print(f"\n❌ Cancel Event:")
        print(f"  Order ID: {event.order_id}")
        print(f"  Symbol: {event.symbol}")
        print(f"  Time: {event.cancel_time}")
        print(f"  Reason: {event.reason}")
    
    async def on_reject(self, event: RejectEvent):
        """Handle reject events."""
        self.events_received.append(event)
        print(f"\n🚫 Reject Event:")
        print(f"  Order ID: {event.order_id}")
        print(f"  Symbol: {event.symbol}")
        print(f"  Time: {event.reject_time}")
        print(f"  Reason: {event.reason}")
        print(f"  Error: {event.error_message}")


async def test_event_system():
    """Test Alpaca event system adaptations."""
    print("\n=== Testing Alpaca Event System ===\n")
    
    # Initialize components
    config = AlpacaConfig.from_env()
    event_bus = EventBus()
    
    # Create event monitor
    monitor = EventMonitor()
    
    # Subscribe to events
    print("1. Setting up event subscriptions...")
    await event_bus.subscribe(OrderStatusEvent, monitor.on_order_status)
    await event_bus.subscribe(FillEvent, monitor.on_fill)
    await event_bus.subscribe(CancelEvent, monitor.on_cancel)
    await event_bus.subscribe(RejectEvent, monitor.on_reject)
    print("✅ Event subscriptions configured")
    
    # Create connection with event bus
    print("\n2. Creating Alpaca connection with event bus...")
    connection = AlpacaConnection(config, event_bus)
    
    # Connect to Alpaca
    print("\n3. Connecting to Alpaca...")
    connected = await connection.connect()
    if not connected:
        print("❌ Failed to connect to Alpaca")
        return
    
    print("✅ Connected to Alpaca with event adapter\n")
    
    # Test order placement to generate events
    print("4. Testing order placement and event generation...")
    
    # Get a test order ID
    order_id = connection.get_next_order_id()
    print(f"Generated order ID: {order_id}")
    
    # Place a small test order
    print("\n5. Placing a test order (1 share of AAPL)...")
    connection.placeOrder(
        orderId=order_id,
        symbol="AAPL",
        quantity=1,
        order_type="MKT",
        side="BUY"
    )
    
    # Wait for events
    print("\n6. Waiting for order events (10 seconds)...")
    await asyncio.sleep(10)
    
    # Check if we received events
    print(f"\n7. Events Summary:")
    print(f"Total events received: {len(monitor.events_received)}")
    
    event_types = {}
    for event in monitor.events_received:
        event_type = type(event).__name__
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    for event_type, count in event_types.items():
        print(f"  - {event_type}: {count}")
    
    # Cancel the order if it's still open
    print("\n8. Attempting to cancel order...")
    connection.cancelOrder(order_id)
    
    # Wait for cancel event
    await asyncio.sleep(5)
    
    # Final event count
    print(f"\n9. Final Results:")
    print(f"Total events after cancel: {len(monitor.events_received)}")
    
    # Test event adapter directly with mock data
    print("\n10. Testing event adapter with mock data...")
    
    # Create mock trade update
    class MockOrder:
        def __init__(self):
            self.client_order_id = "TEST_123"
            self.id = "alpaca_123"
            self.symbol = "TEST"
            self.status = "filled"
            self.filled_qty = "10"
            self.qty = "10"
            self.filled_avg_price = "100.50"
            self.side = "buy"
            self.order_type = "market"
            self.time_in_force = "day"
    
    class MockTradeUpdate:
        def __init__(self, event_type):
            self.event = event_type
            self.order = MockOrder()
            self.price = "100.50"
            self.timestamp = datetime.now()
    
    # Test fill event
    print("\nTesting mock fill event...")
    mock_fill = MockTradeUpdate("fill")
    await connection.event_adapter.handle_trade_update(mock_fill)
    
    # Test partial fill
    print("\nTesting mock partial fill event...")
    mock_fill.order.filled_qty = "5"
    mock_fill.event = "partial_fill"
    await connection.event_adapter.handle_trade_update(mock_fill)
    
    # Test rejection
    print("\nTesting mock rejection event...")
    mock_reject = MockTradeUpdate("rejected")
    mock_reject.order.status = "rejected"
    await connection.event_adapter.handle_trade_update(mock_reject)
    
    await asyncio.sleep(1)
    
    print(f"\n✅ Event adapter test completed")
    print(f"Total events (including mocks): {len(monitor.events_received)}")
    
    # Disconnect
    print("\n11. Disconnecting...")
    connection.disconnect()
    print("✅ Test completed")


if __name__ == "__main__":
    asyncio.run(test_event_system()) 