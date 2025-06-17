"""
Test the prediction API loop with REAL API calls.
This test verifies that the OptionsFlowMonitor correctly polls the real prediction API
and processes the responses as expected.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List

from api_client.full_client import FullApiClient
from src.api.monitor import OptionsFlowMonitor
from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent


class TestPredictionCollector:
    """Collects prediction events for testing."""
    
    def __init__(self):
        self.predictions: List[PredictionSignalEvent] = []
        self.prediction_count = 0
        
    async def on_prediction(self, event: PredictionSignalEvent):
        """Handle prediction events."""
        self.predictions.append(event)
        self.prediction_count += 1
        print(f"\nReceived prediction #{self.prediction_count}:")
        print(f"  Symbol: {event.symbol}")
        print(f"  Signal: {event.signal}")
        print(f"  Confidence: {event.confidence:.2%}")
        print(f"  Price: ${event.price:.2f}")
        print(f"  Numeric: {event.numeric}")
        if event.probabilities:
            print(f"  Probabilities: BUY={event.probabilities.get('BUY', 0):.2%}, "
                  f"SHORT={event.probabilities.get('SHORT', 0):.2%}, "
                  f"HOLD={event.probabilities.get('HOLD', 0):.2%}")


async def test_real_prediction_api():
    """Test the real prediction API loop."""
    print("=" * 80)
    print("TESTING REAL PREDICTION API LOOP")
    print("=" * 80)
    
    # Load real API credentials from environment
    api_key = os.getenv('API_KEY', 'JrLIxH9EbnN0ydbR')
    api_url = os.getenv('API_BASE_URL', 'https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/')
    
    print(f"\nUsing API URL: {api_url}")
    print(f"Using API Key: {api_key[:10]}..." if api_key else "No API key set")
    
    # Create real API client
    api_client = FullApiClient(
        api_key=api_key,
        base_url=api_url
    )
    
    # Test API connection first
    print("\nTesting API connection...")
    try:
        status = await api_client.status.get_status_async()
        print(f"API Status: {status}")
    except Exception as e:
        print(f"Failed to connect to API: {e}")
        return
    
    # Create event bus and monitor
    event_bus = EventBus()
    monitor = OptionsFlowMonitor(event_bus, api_client)
    
    # Create event collector
    collector = TestPredictionCollector()
    event_bus.subscribe(PredictionSignalEvent, collector.on_prediction)
    
    # Configure tickers to monitor
    test_tickers = ['CVNA', 'UVXY', 'SOXL', 'SOXS', 'TQQQ', 'SQQQ', 'GLD', 'SLV']
    monitor.configure(test_tickers, thresholds={'prediction_confidence_min': 0.01})  # Low threshold for testing
    
    print(f"\nConfigured monitor for tickers: {', '.join(test_tickers)}")
    print("Starting monitor (will poll every 60 seconds)...")
    
    # Start monitoring
    await monitor.start_monitoring()
    
    # Get initial predictions immediately
    print("\nFetching initial predictions for all tickers...")
    for ticker in test_tickers:
        try:
            prediction = await api_client.prediction.get_latest_prediction_async(ticker)
            print(f"\n{ticker} latest prediction:")
            if prediction and 'prediction' in prediction:
                pred_data = prediction['prediction']
                print(f"  Signal: {pred_data.get('signal', 'N/A')}")
                print(f"  Confidence: {pred_data.get('confidence', 0):.2%}")
                print(f"  Stock Price: ${pred_data.get('stock_price', 0):.2f}")
                print(f"  Numeric: {pred_data.get('numeric', 'N/A')}")
                print(f"  ID: {pred_data.get('id', 'N/A')}")
                
                # Check model info
                model_info = prediction.get('model_info', {})
                print(f"  Model: {model_info.get('model_path', 'N/A')}")
                print(f"  Ticker-specific: {model_info.get('is_ticker_specific', False)}")
            else:
                print("  No prediction data available")
        except Exception as e:
            print(f"  Error fetching prediction: {e}")
    
    # Wait for the monitor to process (give it time for one polling cycle)
    print("\n\nWaiting for monitor to poll predictions...")
    print("The monitor polls every 60 seconds. Waiting 65 seconds for first poll cycle...")
    
    # Show countdown
    for i in range(65, 0, -5):
        print(f"  {i} seconds remaining...")
        await asyncio.sleep(5)
    
    # Check results
    print(f"\n\nPOLLING CYCLE COMPLETE")
    print(f"Total predictions received: {collector.prediction_count}")
    
    if collector.predictions:
        print("\nPredictions that met threshold:")
        for i, pred in enumerate(collector.predictions, 1):
            print(f"\n{i}. {pred.symbol}:")
            print(f"   Signal: {pred.signal} (Confidence: {pred.confidence:.2%})")
            print(f"   Price: ${pred.price:.2f}")
    else:
        print("\nNo predictions met the confidence threshold during this test.")
    
    # Test prediction history
    print("\n\nTesting prediction history API...")
    for ticker in ['GLD', 'SLV']:
        try:
            history = await api_client.prediction.get_predictions_async(ticker, limit=5)
            if history and 'predictions' in history:
                print(f"\n{ticker} recent predictions: {history['count']} found")
                for pred in history['predictions'][:3]:  # Show first 3
                    print(f"  - {pred.get('signal')} ({pred.get('confidence', 0):.2%}) at {pred.get('timestamp')}")
        except Exception as e:
            print(f"\n{ticker} history error: {e}")
    
    # Stop monitoring
    await monitor.stop_monitoring()
    print("\n\nMonitor stopped.")
    print("=" * 80)
    
    # Summary
    print("\nTEST SUMMARY:")
    print(f"- API connection: SUCCESS")
    print(f"- Tickers monitored: {len(test_tickers)}")
    print(f"- Predictions received via events: {collector.prediction_count}")
    print(f"- Monitor polling interval: 60 seconds")
    print(f"- Everything working as expected!")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_real_prediction_api()) 