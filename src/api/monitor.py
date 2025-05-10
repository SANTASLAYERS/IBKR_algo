"""
API monitoring and event generation for the options flow monitor API.

This module provides functionality to monitor the options flow monitor API
and generate events based on prediction signals.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

from src.event.bus import EventBus
from src.event.api import PredictionSignalEvent, FlowThresholdEvent

# Set up logger
logger = logging.getLogger(__name__)


class OptionsFlowMonitor:
    """
    Monitors options flow API data and generates events.
    
    This class polls the options flow monitor API for prediction signals and
    generates events when new predictions are received that meet confidence thresholds.
    """
    
    def __init__(self, event_bus: EventBus, api_client: Any):
        """
        Initialize the options flow monitor.
        
        Args:
            event_bus: The event bus to publish events to
            api_client: The API client for the options flow monitor API
        """
        self.event_bus = event_bus
        self.api_client = api_client
        
        # Configuration
        self.thresholds = {
            'prediction_confidence_min': 0.75
        }
        
        # State
        self.configured_tickers: Set[str] = set()
        self.running = False
        self.last_poll_time: Dict[str, datetime] = {}
        self.last_prediction_ids: Dict[str, str] = {}
        
        # Tasks
        self._polling_task = None
        
        logger.debug("OptionsFlowMonitor initialized")
    
    def configure(self, tickers: List[str], thresholds: Optional[Dict[str, float]] = None) -> None:
        """
        Configure the options flow monitor.
        
        Args:
            tickers: List of tickers to monitor
            thresholds: Optional threshold overrides
        """
        self.configured_tickers = set(tickers)
        
        if thresholds:
            self.thresholds.update(thresholds)
            
        logger.info(f"OptionsFlowMonitor configured with tickers: {', '.join(tickers)}")
    
    async def start_monitoring(self) -> None:
        """Start the monitoring process."""
        if self.running:
            logger.warning("OptionsFlowMonitor already running")
            return
        
        if not self.configured_tickers:
            logger.warning("No tickers configured for OptionsFlowMonitor")
            return
        
        self.running = True
        
        # Schedule periodic prediction polling
        self._polling_task = asyncio.create_task(self._poll_predictions())
        
        logger.info("OptionsFlowMonitor started")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring process."""
        if not self.running:
            logger.warning("OptionsFlowMonitor not running")
            return
        
        self.running = False
        
        # Cancel the polling task
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            
        logger.info("OptionsFlowMonitor stopped")
    
    async def _poll_predictions(self) -> None:
        """Poll for new predictions from the API."""
        while self.running:
            try:
                # For each configured ticker
                for ticker in self.configured_tickers:
                    try:
                        logger.debug(f"Polling predictions for {ticker}")
                        
                        # Get latest prediction
                        prediction = await self.api_client.prediction.get_latest_prediction_async(ticker)
                        
                        # Process the prediction
                        await self._process_prediction(ticker, prediction)
                        
                    except Exception as e:
                        logger.error(f"Error polling predictions for {ticker}: {e}")
            
            except Exception as e:
                logger.error(f"Error in prediction polling loop: {e}")
            
            # Sleep before next poll
            await asyncio.sleep(60)  # Poll every minute
    
    async def _process_prediction(self, ticker: str, prediction: Dict[str, Any]) -> None:
        """
        Process a prediction from the API.
        
        Args:
            ticker: The ticker the prediction is for
            prediction: The prediction data from the API
        """
        # Extract prediction data
        prediction_data = prediction.get('prediction', {})
        if not prediction_data:
            logger.warning(f"No prediction data found for {ticker}")
            return
        
        # Check if we've seen this prediction before
        prediction_id = prediction_data.get('id', '')
        if prediction_id and prediction_id == self.last_prediction_ids.get(ticker):
            logger.debug(f"Skipping already processed prediction for {ticker}")
            return
        
        # Update tracking
        self.last_prediction_ids[ticker] = prediction_id
        self.last_poll_time[ticker] = datetime.now()
        
        # Extract fields
        signal = prediction_data.get('signal', '')
        confidence = prediction_data.get('confidence', 0.0)
        numeric = prediction_data.get('numeric')
        stock_price = prediction_data.get('stock_price', 0.0)
        probabilities = prediction_data.get('probabilities')
        feature_values = prediction_data.get('feature_values', {})
        
        # Check confidence threshold
        if confidence >= self.thresholds['prediction_confidence_min']:
            logger.info(f"High confidence prediction for {ticker}: {signal} ({confidence:.2f})")
            
            # Create prediction signal event
            event = PredictionSignalEvent(
                symbol=ticker,
                signal=signal,
                numeric=numeric,
                confidence=confidence,
                price=stock_price,
                probabilities=probabilities,
                feature_values=feature_values,
                model_info=prediction.get('model_info', {}),
                flow_data={'prediction_id': prediction_id}
            )
            
            # Emit the event
            await self.event_bus.emit(event)
            
            logger.debug(f"Emitted PredictionSignalEvent for {ticker}")
    
    async def _poll_trades(self) -> None:
        """
        Poll for unusual options trades.
        
        This is a placeholder for future implementation.
        """
        pass
    
    async def _poll_divergence(self) -> None:
        """
        Poll for delta divergence changes.
        
        This is a placeholder for future implementation.
        """
        pass