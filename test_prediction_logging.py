"""
Test to verify prediction logging is working correctly.
This test runs for 3 minutes to show multiple polling cycles.
"""

import asyncio
import os
import logging
from datetime import datetime

from api_client.full_client import FullApiClient
from src.api.monitor import OptionsFlowMonitor
from src.event.bus import EventBus

# Set up logging to see the prediction logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_prediction_logging():
    """Test that predictions are logged every 60 seconds."""
    print("=" * 80)
    print("TESTING PREDICTION LOGGING")
    print("This test will run for 3 minutes to show multiple polling cycles")
    print("=" * 80)
    
    # Set up API credentials
    os.environ['API_KEY'] = 'JrLIxH9EbnN0ydbRK-YDf3ReK6ymnl8JJhSrKM2W3oA'
    os.environ['API_BASE_URL'] = 'https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/'
    
    # Create API client
    api_client = FullApiClient()
    
    # Create event bus and monitor
    event_bus = EventBus()
    monitor = OptionsFlowMonitor(event_bus, api_client)
    
    # Configure tickers to monitor
    test_tickers = ['CVNA', 'UVXY', 'SOXL', 'SOXS', 'TQQQ', 'SQQQ', 'GLD', 'SLV']
    monitor.configure(test_tickers, thresholds={'prediction_confidence_min': 0.50})
    
    print(f"\nStarting monitor at {datetime.now().strftime('%H:%M:%S')}")
    print("You should see PREDICTION log entries every 60 seconds...\n")
    
    # Start monitoring
    await monitor.start_monitoring()
    
    # Run for 3 minutes (180 seconds) to see multiple polling cycles
    start_time = datetime.now()
    
    while (datetime.now() - start_time).total_seconds() < 180:
        elapsed = int((datetime.now() - start_time).total_seconds())
        print(f"\rElapsed: {elapsed}s / 180s", end='', flush=True)
        await asyncio.sleep(1)
    
    print("\n\nStopping monitor...")
    await monitor.stop_monitoring()
    
    print("\nTest complete! Check the logs above for PREDICTION entries.")
    print("You should see 8 predictions logged every 60 seconds.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_prediction_logging()) 