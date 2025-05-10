"""
Endpoint-specific methods for the Multi-Ticker Options Flow Monitor API.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional, Union, List, TypeVar, Generic

from .client import ApiClient

# Type variable for the base client
T = TypeVar('T', bound=ApiClient)


class BaseEndpoint(Generic[T]):
    """Base class for API endpoints."""
    
    def __init__(self, client: T):
        """
        Initialize endpoint with API client.
        
        Args:
            client: API client instance
        """
        self.client = client


class StatusEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for system status information.
    
    Example:
        ```python
        api = ApiClient(...)
        status = StatusEndpoint(api)
        system_status = status.get_status()
        ```
    """
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get system status information.

        Returns:
            System status information
        """
        # Use just 'status' instead of '/api/v1/status' since the base URL already includes the API path
        response = self.client.get('status')
        return response.get('data', {})
        
    async def get_status_async(self) -> Dict[str, Any]:
        """
        Get system status information asynchronously.

        Returns:
            System status information
        """
        # Use just 'status' instead of '/api/v1/status' since the base URL already includes the API path
        response = await self.client.get_async('status')
        return response.get('data', {})


class TickersEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for supported tickers.
    
    Example:
        ```python
        api = ApiClient(...)
        tickers = TickersEndpoint(api)
        supported_tickers = tickers.get_tickers()
        ```
    """
    
    def get_tickers(self) -> List[str]:
        """
        Get list of supported tickers.

        Returns:
            List of ticker symbols
        """
        # Use just 'tickers' instead of '/api/v1/tickers' since the base URL already includes the API path
        response = self.client.get('tickers')
        return response.get('data', {}).get('tickers', [])
        
    async def get_tickers_async(self) -> List[str]:
        """
        Get list of supported tickers asynchronously.

        Returns:
            List of ticker symbols
        """
        # Use just 'tickers' instead of '/api/v1/tickers' since the base URL already includes the API path
        response = await self.client.get_async('tickers')
        return response.get('data', {}).get('tickers', [])


class TradesEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for options trades data.
    
    Example:
        ```python
        api = ApiClient(...)
        trades = TradesEndpoint(api)
        recent_trades = trades.get_trades('SLV', recent=True, limit=10)
        ```
    """
    
    def get_trades(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
        recent: bool = False
    ) -> Dict[str, Any]:
        """
        Get options trades for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            limit: Maximum number of records to return
            recent: If true, returns most recent trades
            
        Returns:
            Dictionary with ticker, trades list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if limit:
            params['limit'] = limit
            
        if recent:
            params['recent'] = True
            
        response = self.client.get('trades', params=params)
        return response.get('data', {})
        
    async def get_trades_async(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
        recent: bool = False
    ) -> Dict[str, Any]:
        """
        Get options trades for a specific ticker asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            limit: Maximum number of records to return
            recent: If true, returns most recent trades
            
        Returns:
            Dictionary with ticker, trades list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if limit:
            params['limit'] = limit
            
        if recent:
            params['recent'] = True
            
        response = await self.client.get_async('trades', params=params)
        return response.get('data', {})


class MinuteDataEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for minute-by-minute OHLCV data.
    
    Example:
        ```python
        api = ApiClient(...)
        minute_data = MinuteDataEndpoint(api)
        recent_data = minute_data.get_minute_data('GLD', recent=True, limit=10)
        ```
    """
    
    def get_minute_data(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
        recent: bool = False
    ) -> Dict[str, Any]:
        """
        Get minute-by-minute OHLCV data for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            limit: Maximum number of records to return
            recent: If true, returns most recent data
            
        Returns:
            Dictionary with ticker, minute_data list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if limit:
            params['limit'] = limit
            
        if recent:
            params['recent'] = True
            
        response = self.client.get('minute-data', params=params)
        return response.get('data', {})
        
    async def get_minute_data_async(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
        recent: bool = False
    ) -> Dict[str, Any]:
        """
        Get minute-by-minute OHLCV data for a specific ticker asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            limit: Maximum number of records to return
            recent: If true, returns most recent data
            
        Returns:
            Dictionary with ticker, minute_data list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if limit:
            params['limit'] = limit
            
        if recent:
            params['recent'] = True
            
        response = await self.client.get_async('minute-data', params=params)
        return response.get('data', {})


class DivergenceEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for delta divergence data.
    
    Example:
        ```python
        api = ApiClient(...)
        divergence = DivergenceEndpoint(api)
        data = divergence.get_divergence('CVNA', days=1, limit=10)
        ```
    """
    
    def get_divergence(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get delta divergence data for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            days: Number of days of data to return
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with ticker, divergence_data list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if days:
            params['days'] = days
            
        if limit:
            params['limit'] = limit
            
        response = self.client.get('divergence', params=params)
        return response.get('data', {})
        
    async def get_divergence_async(
        self,
        ticker: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        start_time: Optional[str] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        end_time: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get delta divergence data for a specific ticker asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            start_time: Start time (HH:MM)
            end_date: End date (YYYY-MM-DD)
            end_time: End time (HH:MM)
            days: Number of days of data to return
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with ticker, divergence_data list, and count
        """
        params = {'ticker': ticker}
        
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.strftime('%Y-%m-%d')
            else:
                params['start_date'] = start_date
                
        if start_time:
            params['start_time'] = start_time
            
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.strftime('%Y-%m-%d')
            else:
                params['end_date'] = end_date
                
        if end_time:
            params['end_time'] = end_time
            
        if days:
            params['days'] = days
            
        if limit:
            params['limit'] = limit
            
        response = await self.client.get_async('divergence', params=params)
        return response.get('data', {})


class PredictionEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for machine learning predictions.
    
    Example:
        ```python
        api = ApiClient(...)
        prediction = PredictionEndpoint(api)
        latest = prediction.get_latest_prediction('SLV')
        ```
    """
    
    def get_latest_prediction(
        self, 
        ticker: str, 
        use_default_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get the latest ML prediction for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            use_default_only: If true, uses the default model instead of ticker-specific model
            
        Returns:
            Dictionary with ticker, prediction data, and model_info
        """
        params = {
            'ticker': ticker,
            'use_default_only': use_default_only
        }
        
        response = self.client.get('prediction/latest', params=params)
        return response.get('data', {})
        
    async def get_latest_prediction_async(
        self, 
        ticker: str, 
        use_default_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get the latest ML prediction for a specific ticker asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            use_default_only: If true, uses the default model instead of ticker-specific model
            
        Returns:
            Dictionary with ticker, prediction data, and model_info
        """
        params = {
            'ticker': ticker,
            'use_default_only': use_default_only
        }
        
        response = await self.client.get_async('prediction/latest', params=params)
        return response.get('data', {})
    
    def get_predictions(
        self,
        ticker: str,
        limit: Optional[int] = None,
        start_date: Optional[Union[str, date, datetime]] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        use_default_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get ML prediction history for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of predictions to return
            start_date: Start date
            end_date: End date
            use_default_only: If true, uses the default model
            
        Returns:
            Dictionary with ticker, predictions list, count, and model_info
        """
        params = {
            'ticker': ticker,
            'use_default_only': use_default_only
        }
        
        if limit:
            params['limit'] = limit
            
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.isoformat().split('T')[0]
            else:
                params['start_date'] = start_date
                
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.isoformat().split('T')[0]
            else:
                params['end_date'] = end_date
                
        response = self.client.get('predictions', params=params)
        return response.get('data', {})
        
    async def get_predictions_async(
        self,
        ticker: str,
        limit: Optional[int] = None,
        start_date: Optional[Union[str, date, datetime]] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        use_default_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get ML prediction history for a specific ticker asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of predictions to return
            start_date: Start date
            end_date: End date
            use_default_only: If true, uses the default model
            
        Returns:
            Dictionary with ticker, predictions list, count, and model_info
        """
        params = {
            'ticker': ticker,
            'use_default_only': use_default_only
        }
        
        if limit:
            params['limit'] = limit
            
        if start_date:
            if isinstance(start_date, (date, datetime)):
                params['start_date'] = start_date.isoformat().split('T')[0]
            else:
                params['start_date'] = start_date
                
        if end_date:
            if isinstance(end_date, (date, datetime)):
                params['end_date'] = end_date.isoformat().split('T')[0]
            else:
                params['end_date'] = end_date
                
        response = await self.client.get_async('predictions', params=params)
        return response.get('data', {})


class DataRangeEndpoint(BaseEndpoint[ApiClient]):
    """
    Endpoint for custom date range data with filter options.
    
    Example:
        ```python
        api = ApiClient(...)
        data_range = DataRangeEndpoint(api)
        data = data_range.get_data_range('CVNA', '2023-05-18', '2023-05-19')
        ```
    """
    
    def get_data_range(
        self,
        ticker: str,
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        lookback_hours: Optional[int] = None,
        lambda_short: Optional[float] = None,
        lambda_long: Optional[float] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        min_delta: Optional[float] = None,
        max_delta: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get custom date range data with filter options.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date
            lookback_hours: Number of hours to look back for trades
            lambda_short: Short-term decay factor
            lambda_long: Long-term decay factor
            min_value: Minimum trade value filter
            max_value: Maximum trade value filter
            min_size: Minimum trade size filter
            max_size: Maximum trade size filter
            min_delta: Minimum delta value filter
            max_delta: Maximum delta value filter
            
        Returns:
            Dictionary with filtered data and metadata
        """
        params = {'ticker': ticker}
        
        # Handle date parameters
        if isinstance(start_date, (date, datetime)):
            params['start_date'] = start_date.strftime('%Y-%m-%d')
        else:
            params['start_date'] = start_date
            
        if isinstance(end_date, (date, datetime)):
            params['end_date'] = end_date.strftime('%Y-%m-%d')
        else:
            params['end_date'] = end_date
            
        # Add optional parameters
        if lookback_hours is not None:
            params['lookback_hours'] = lookback_hours
            
        if lambda_short is not None:
            params['lambda_short'] = lambda_short
            
        if lambda_long is not None:
            params['lambda_long'] = lambda_long
            
        if min_value is not None:
            params['min_value'] = min_value
            
        if max_value is not None:
            params['max_value'] = max_value
            
        if min_size is not None:
            params['min_size'] = min_size
            
        if max_size is not None:
            params['max_size'] = max_size
            
        if min_delta is not None:
            params['min_delta'] = min_delta
            
        if max_delta is not None:
            params['max_delta'] = max_delta
            
        response = self.client.get('data-range', params=params)
        return response.get('data', {})
        
    async def get_data_range_async(
        self,
        ticker: str,
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        lookback_hours: Optional[int] = None,
        lambda_short: Optional[float] = None,
        lambda_long: Optional[float] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        min_delta: Optional[float] = None,
        max_delta: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get custom date range data with filter options asynchronously.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date
            lookback_hours: Number of hours to look back for trades
            lambda_short: Short-term decay factor
            lambda_long: Long-term decay factor
            min_value: Minimum trade value filter
            max_value: Maximum trade value filter
            min_size: Minimum trade size filter
            max_size: Maximum trade size filter
            min_delta: Minimum delta value filter
            max_delta: Maximum delta value filter
            
        Returns:
            Dictionary with filtered data and metadata
        """
        params = {'ticker': ticker}
        
        # Handle date parameters
        if isinstance(start_date, (date, datetime)):
            params['start_date'] = start_date.strftime('%Y-%m-%d')
        else:
            params['start_date'] = start_date
            
        if isinstance(end_date, (date, datetime)):
            params['end_date'] = end_date.strftime('%Y-%m-%d')
        else:
            params['end_date'] = end_date
            
        # Add optional parameters
        if lookback_hours is not None:
            params['lookback_hours'] = lookback_hours
            
        if lambda_short is not None:
            params['lambda_short'] = lambda_short
            
        if lambda_long is not None:
            params['lambda_long'] = lambda_long
            
        if min_value is not None:
            params['min_value'] = min_value
            
        if max_value is not None:
            params['max_value'] = max_value
            
        if min_size is not None:
            params['min_size'] = min_size
            
        if max_size is not None:
            params['max_size'] = max_size
            
        if min_delta is not None:
            params['min_delta'] = min_delta
            
        if max_delta is not None:
            params['max_delta'] = max_delta
            
        response = await self.client.get_async('data-range', params=params)
        return response.get('data', {})