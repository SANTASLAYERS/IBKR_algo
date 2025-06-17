"""
Full API client with all endpoints attached as attributes.
"""

from .client import ApiClient
from .endpoints import (
    StatusEndpoint,
    TickersEndpoint,
    TradesEndpoint,
    MinuteDataEndpoint,
    DivergenceEndpoint,
    PredictionEndpoint,
    DataRangeEndpoint
)


class FullApiClient(ApiClient):
    """
    Full API client with all endpoints attached as attributes.
    
    This provides a convenient interface where endpoints can be accessed as:
    - client.status.get_status()
    - client.prediction.get_latest_prediction('SLV')
    - etc.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the full API client with all endpoints."""
        super().__init__(*args, **kwargs)
        
        # Attach all endpoints as attributes
        self.status = StatusEndpoint(self)
        self.tickers = TickersEndpoint(self)
        self.trades = TradesEndpoint(self)
        self.minute_data = MinuteDataEndpoint(self)
        self.divergence = DivergenceEndpoint(self)
        self.prediction = PredictionEndpoint(self)
        self.data_range = DataRangeEndpoint(self) 