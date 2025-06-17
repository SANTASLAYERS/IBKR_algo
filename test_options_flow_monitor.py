"""
Test to verify OptionsFlowMonitor is working correctly.
"""

import asyncio
import os
import logging
from datetime import datetime

from api_client.full_client import FullApiClient
from src.api.monitor import OptionsFlowMonitor
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent

# Set up logging to see all logs
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see everything
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Silence httpx logs to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)


async def test_monitor():
    """Test the OptionsFlowMonitor in isolation."""
    print("=" * 80)
    print("TESTING OPTIONS FLOW MONITOR")
    print("=" * 80)
    
    # Set up API credentials
    os.environ['API_KEY'] = 'JrLIxH9EbnN0ydbRK-YDf3ReK6ymnl8JJhSrKM2W3oA'
    os.environ['API_BASE_URL'] = 'https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/'
    
    try:
        # Create API client
        print("\n1. Creating API client...")
        api_client = FullApiClient()
        print("   ✓ API client created")
        
        # Test API connection
        print("\n2. Testing API connection...")
        status = await api_client.status.get_status_async()
        print(f"   ✓ API connected: {status['system']['status']}")
        
        # Create event bus
        print("\n3. Creating event bus...")
        event_bus = EventBus()
        print("   ✓ Event bus created")
        
        # Create monitor
        print("\n4. Creating OptionsFlowMonitor...")
        monitor = OptionsFlowMonitor(event_bus, api_client)
        print("   ✓ Monitor created")
        
        # Configure monitor
        print("\n5. Configuring monitor...")
        tickers = ['GLD', 'SLV', 'SOXL']  # Just 3 for testing
        monitor.configure(tickers, thresholds={'prediction_confidence_min': 0.50})
        print(f"   ✓ Configured for tickers: {', '.join(tickers)}")
        
        # Subscribe to events
        event_count = 0
        async def on_prediction(event: PredictionSignalEvent):
            nonlocal event_count
            event_count += 1
            print(f"\n   EVENT #{event_count}: {event.symbol} {event.signal} @ ${event.price:.2f} ({event.confidence:.1%})")
        
        print("\n6. Subscribing to prediction events...")
        await event_bus.subscribe(PredictionSignalEvent, on_prediction)
        print("   ✓ Subscribed to events")
        
        # Start monitoring
        print("\n7. Starting monitor...")
        await monitor.start_monitoring()
        print("   ✓ Monitor started")
        
        # Check if polling task was created
        print(f"\n8. Polling task created: {monitor._polling_task is not None}")
        print(f"   Task running: {not monitor._polling_task.done() if monitor._polling_task else False}")
        
        # Wait a bit to see predictions
        print("\n9. Waiting 70 seconds for first poll cycle...")
        print("   You should see PREDICTION logs within 5 seconds...")
        
        for i in range(70, 0, -10):
            print(f"   {i} seconds remaining...")
            await asyncio.sleep(10)
        
        print(f"\n10. Results:")
        print(f"    - Monitor running: {monitor.running}")
        print(f"    - Events received: {event_count}")
        print(f"    - Last poll times: {monitor.last_poll_time}")
        
        # Stop monitor
        print("\n11. Stopping monitor...")
        await monitor.stop_monitoring()
        print("    ✓ Monitor stopped")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_monitor()) 