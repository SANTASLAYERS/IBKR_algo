"""
API-related events for the event system.

This module defines events related to API signals, particularly those from the
options flow monitor API and prediction signals.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.event.base import BaseEvent


@dataclass
class OptionsFlowEvent(BaseEvent):
    """Base class for all options flow-related events."""
    
    source: str = "api"
    
    # Symbol the event is for
    symbol: str = ""
    
    # API reference (endpoint or data source)
    api_reference: Optional[str] = None
    
    # The time from the API data
    data_time: Optional[datetime] = None
    
    # Additional options flow data
    flow_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionSignalEvent(OptionsFlowEvent):
    """Event for prediction signals from the API."""
    
    # Signal direction ("BUY", "SELL", "NEUTRAL")
    signal: str = ""
    
    # Numeric signal value
    numeric: Optional[float] = None
    
    # Signal confidence (0.0 to 1.0)
    confidence: float = 0.0
    
    # Asset price at time of prediction
    price: float = 0.0
    
    # Class probabilities if available
    probabilities: Optional[List[float]] = None
    
    # Feature values that led to prediction
    feature_values: Dict[str, float] = field(default_factory=dict)
    
    # Model information
    model_info: Dict[str, Any] = field(default_factory=dict)
    
    # Prediction timestamp
    prediction_time: datetime = field(default_factory=datetime.now)


@dataclass
class FlowThresholdEvent(OptionsFlowEvent):
    """
    Event for when options flow metrics cross predefined thresholds.
    
    This is a placeholder for future implementation of divergence and trade data integration.
    """
    
    # Threshold type that was crossed
    threshold_type: str = ""
    
    # Threshold value
    threshold_value: float = 0.0
    
    # Actual value that crossed the threshold
    actual_value: float = 0.0
    
    # Direction of crossing (above/below)
    crossing_direction: str = ""
    
    # Previous value before crossing
    previous_value: Optional[float] = None