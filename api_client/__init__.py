"""
Multi-Ticker Options Flow Monitor API client package.

This package provides a client for interacting with the Multi-Ticker Options
Flow Monitor API, which provides options flow data, trade analytics, and
ML-based trading signal predictions.
"""

from .client import ApiClient, ApiException
from .endpoints import (
    StatusEndpoint,
    TickersEndpoint,
    TradesEndpoint,
    MinuteDataEndpoint,
    DivergenceEndpoint,
    PredictionEndpoint,
    DataRangeEndpoint
)
from .utils import load_env, safe_get_env

__all__ = [
    'ApiClient',
    'ApiException',
    'StatusEndpoint',
    'TickersEndpoint',
    'TradesEndpoint',
    'MinuteDataEndpoint',
    'DivergenceEndpoint',
    'PredictionEndpoint',
    'DataRangeEndpoint',
    'load_env',
    'safe_get_env'
]