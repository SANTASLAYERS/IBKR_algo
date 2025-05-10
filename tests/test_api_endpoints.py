"""
Tests for the API endpoint classes.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch

from api_client.client import ApiClient
from api_client.endpoints import (
    BaseEndpoint,
    StatusEndpoint,
    TickersEndpoint,
    TradesEndpoint,
    MinuteDataEndpoint,
    DivergenceEndpoint,
    PredictionEndpoint,
    DataRangeEndpoint
)


@pytest.fixture
def mock_client():
    """Create a mock API client for testing."""
    client = Mock(spec=ApiClient)
    # Setup default response for sync and async get methods
    client.get.return_value = {'status': 'success', 'data': {}}
    client.get_async.return_value = {'status': 'success', 'data': {}}
    return client


class TestBaseEndpoint:
    """Test the BaseEndpoint class."""
    
    def test_init(self, mock_client):
        """Test BaseEndpoint initialization."""
        endpoint = BaseEndpoint(mock_client)
        assert endpoint.client is mock_client


class TestStatusEndpoint:
    """Test the StatusEndpoint class."""
    
    def test_get_status(self, mock_client):
        """Test getting system status."""
        # Setup mock response
        status_data = {
            'system': {'status': 'running'},
            'market': {'is_market_hours': True}
        }
        mock_client.get.return_value = {'status': 'success', 'data': status_data}
        
        # Test endpoint
        endpoint = StatusEndpoint(mock_client)
        result = endpoint.get_status()
        
        # Verify request
        mock_client.get.assert_called_once_with('status')
        assert result == status_data
        
    @pytest.mark.asyncio
    async def test_get_status_async(self, mock_client):
        """Test getting system status asynchronously."""
        # Setup mock response
        status_data = {
            'system': {'status': 'running'},
            'market': {'is_market_hours': True}
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': status_data}
        
        # Test endpoint
        endpoint = StatusEndpoint(mock_client)
        result = await endpoint.get_status_async()
        
        # Verify request
        mock_client.get_async.assert_called_once_with('status')
        assert result == status_data


class TestTickersEndpoint:
    """Test the TickersEndpoint class."""
    
    def test_get_tickers(self, mock_client):
        """Test getting supported tickers."""
        # Setup mock response
        tickers_data = {
            'tickers': ['SLV', 'GLD', 'CVNA'],
            'count': 3
        }
        mock_client.get.return_value = {'status': 'success', 'data': tickers_data}
        
        # Test endpoint
        endpoint = TickersEndpoint(mock_client)
        result = endpoint.get_tickers()
        
        # Verify request
        mock_client.get.assert_called_once_with('tickers')
        assert result == ['SLV', 'GLD', 'CVNA']
        
    @pytest.mark.asyncio
    async def test_get_tickers_async(self, mock_client):
        """Test getting supported tickers asynchronously."""
        # Setup mock response
        tickers_data = {
            'tickers': ['SLV', 'GLD', 'CVNA'],
            'count': 3
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': tickers_data}
        
        # Test endpoint
        endpoint = TickersEndpoint(mock_client)
        result = await endpoint.get_tickers_async()
        
        # Verify request
        mock_client.get_async.assert_called_once_with('tickers')
        assert result == ['SLV', 'GLD', 'CVNA']


class TestTradesEndpoint:
    """Test the TradesEndpoint class."""
    
    def test_get_trades_with_recent(self, mock_client):
        """Test getting recent trades."""
        # Setup mock response
        trades_data = {
            'ticker': 'SLV',
            'trades': [{'id': 1}, {'id': 2}],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': trades_data}
        
        # Test endpoint
        endpoint = TradesEndpoint(mock_client)
        result = endpoint.get_trades('SLV', recent=True, limit=2)
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'trades',
            params={'ticker': 'SLV', 'recent': True, 'limit': 2}
        )
        assert result == trades_data
        
    def test_get_trades_with_date_range(self, mock_client):
        """Test getting trades with date range parameters."""
        # Setup mock response
        trades_data = {
            'ticker': 'GLD',
            'trades': [{'id': 1}, {'id': 2}, {'id': 3}],
            'count': 3
        }
        mock_client.get.return_value = {'status': 'success', 'data': trades_data}
        
        # Test with string dates
        endpoint = TradesEndpoint(mock_client)
        result = endpoint.get_trades(
            'GLD',
            start_date='2023-05-01',
            start_time='09:30',
            end_date='2023-05-02',
            end_time='16:00',
            limit=10
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'trades',
            params={
                'ticker': 'GLD',
                'start_date': '2023-05-01',
                'start_time': '09:30',
                'end_date': '2023-05-02',
                'end_time': '16:00',
                'limit': 10
            }
        )
        assert result == trades_data
        
    def test_get_trades_with_datetime_objects(self, mock_client):
        """Test getting trades with datetime objects for date parameters."""
        # Setup mock response
        trades_data = {
            'ticker': 'CVNA',
            'trades': [{'id': 4}, {'id': 5}],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': trades_data}
        
        # Test with datetime objects
        start_date = datetime(2023, 5, 1)
        end_date = date(2023, 5, 2)
        
        endpoint = TradesEndpoint(mock_client)
        result = endpoint.get_trades(
            'CVNA',
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'trades',
            params={
                'ticker': 'CVNA',
                'start_date': '2023-05-01',
                'end_date': '2023-05-02'
            }
        )
        assert result == trades_data
        
    @pytest.mark.asyncio
    async def test_get_trades_async(self, mock_client):
        """Test getting trades asynchronously."""
        # Setup mock response
        trades_data = {
            'ticker': 'SLV',
            'trades': [{'id': 1}, {'id': 2}],
            'count': 2
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': trades_data}
        
        # Test endpoint
        endpoint = TradesEndpoint(mock_client)
        result = await endpoint.get_trades_async('SLV', recent=True, limit=2)
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'trades',
            params={'ticker': 'SLV', 'recent': True, 'limit': 2}
        )
        assert result == trades_data


class TestMinuteDataEndpoint:
    """Test the MinuteDataEndpoint class."""
    
    def test_get_minute_data_recent(self, mock_client):
        """Test getting recent minute data."""
        # Setup mock response
        minute_data = {
            'ticker': 'GLD',
            'minute_data': [
                {'timestamp': 1, 'open': 100.0, 'close': 101.0},
                {'timestamp': 2, 'open': 101.0, 'close': 102.0}
            ],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': minute_data}
        
        # Test endpoint
        endpoint = MinuteDataEndpoint(mock_client)
        result = endpoint.get_minute_data('GLD', recent=True, limit=2)
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'minute-data',
            params={'ticker': 'GLD', 'recent': True, 'limit': 2}
        )
        assert result == minute_data
        
    def test_get_minute_data_with_date_range(self, mock_client):
        """Test getting minute data with date range parameters."""
        # Setup mock response
        minute_data = {
            'ticker': 'SLV',
            'minute_data': [
                {'timestamp': 3, 'open': 22.0, 'close': 22.5},
                {'timestamp': 4, 'open': 22.5, 'close': 22.7}
            ],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': minute_data}
        
        # Test with datetime objects
        start_date = date(2023, 5, 1)
        end_date = datetime(2023, 5, 2, 16, 0)
        
        endpoint = MinuteDataEndpoint(mock_client)
        result = endpoint.get_minute_data(
            'SLV',
            start_date=start_date,
            start_time='09:30',
            end_date=end_date,
            end_time='16:00'
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'minute-data',
            params={
                'ticker': 'SLV',
                'start_date': '2023-05-01',
                'start_time': '09:30',
                'end_date': '2023-05-02',
                'end_time': '16:00'
            }
        )
        assert result == minute_data
        
    @pytest.mark.asyncio
    async def test_get_minute_data_async(self, mock_client):
        """Test getting minute data asynchronously."""
        # Setup mock response
        minute_data = {
            'ticker': 'GLD',
            'minute_data': [
                {'timestamp': 1, 'open': 100.0, 'close': 101.0},
                {'timestamp': 2, 'open': 101.0, 'close': 102.0}
            ],
            'count': 2
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': minute_data}
        
        # Test endpoint
        endpoint = MinuteDataEndpoint(mock_client)
        result = await endpoint.get_minute_data_async('GLD', recent=True, limit=2)
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'minute-data',
            params={'ticker': 'GLD', 'recent': True, 'limit': 2}
        )
        assert result == minute_data


class TestDivergenceEndpoint:
    """Test the DivergenceEndpoint class."""
    
    def test_get_divergence_with_days(self, mock_client):
        """Test getting divergence data with days parameter."""
        # Setup mock response
        divergence_data = {
            'ticker': 'CVNA',
            'divergence_data': [
                {'timestamp': 1, 'd_diff_short': 0.04, 'd_diff_long': 0.10},
                {'timestamp': 2, 'd_diff_short': 0.05, 'd_diff_long': 0.12}
            ],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': divergence_data}
        
        # Test endpoint
        endpoint = DivergenceEndpoint(mock_client)
        result = endpoint.get_divergence('CVNA', days=1, limit=2)
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'divergence',
            params={'ticker': 'CVNA', 'days': 1, 'limit': 2}
        )
        assert result == divergence_data
        
    def test_get_divergence_with_date_range(self, mock_client):
        """Test getting divergence data with date range parameters."""
        # Setup mock response
        divergence_data = {
            'ticker': 'SLV',
            'divergence_data': [
                {'timestamp': 3, 'd_diff_short': 0.02, 'd_diff_long': 0.08},
                {'timestamp': 4, 'd_diff_short': 0.03, 'd_diff_long': 0.09}
            ],
            'count': 2
        }
        mock_client.get.return_value = {'status': 'success', 'data': divergence_data}
        
        # Test with date strings
        endpoint = DivergenceEndpoint(mock_client)
        result = endpoint.get_divergence(
            'SLV',
            start_date='2023-05-01',
            end_date='2023-05-02'
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'divergence',
            params={
                'ticker': 'SLV',
                'start_date': '2023-05-01',
                'end_date': '2023-05-02'
            }
        )
        assert result == divergence_data
        
    @pytest.mark.asyncio
    async def test_get_divergence_async(self, mock_client):
        """Test getting divergence data asynchronously."""
        # Setup mock response
        divergence_data = {
            'ticker': 'CVNA',
            'divergence_data': [
                {'timestamp': 1, 'd_diff_short': 0.04, 'd_diff_long': 0.10},
                {'timestamp': 2, 'd_diff_short': 0.05, 'd_diff_long': 0.12}
            ],
            'count': 2
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': divergence_data}
        
        # Test endpoint
        endpoint = DivergenceEndpoint(mock_client)
        result = await endpoint.get_divergence_async('CVNA', days=1, limit=2)
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'divergence',
            params={'ticker': 'CVNA', 'days': 1, 'limit': 2}
        )
        assert result == divergence_data


class TestPredictionEndpoint:
    """Test the PredictionEndpoint class."""
    
    def test_get_latest_prediction(self, mock_client):
        """Test getting latest prediction."""
        # Setup mock response
        prediction_data = {
            'ticker': 'SLV',
            'prediction': {
                'signal': 'BUY',
                'confidence': 0.85,
                'stock_price': 22.75
            },
            'model_info': {
                'model_path': 'models/slv_predictor.joblib',
                'is_ticker_specific': True
            }
        }
        mock_client.get.return_value = {'status': 'success', 'data': prediction_data}
        
        # Test endpoint
        endpoint = PredictionEndpoint(mock_client)
        result = endpoint.get_latest_prediction('SLV')
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'prediction/latest',
            params={'ticker': 'SLV', 'use_default_only': False}
        )
        assert result == prediction_data
        
    def test_get_latest_prediction_with_default_model(self, mock_client):
        """Test getting latest prediction with default model parameter."""
        # Setup mock response
        prediction_data = {
            'ticker': 'SLV',
            'prediction': {
                'signal': 'BUY',
                'confidence': 0.82,
                'stock_price': 22.75
            },
            'model_info': {
                'model_path': 'models/default_predictor.joblib',
                'is_ticker_specific': False
            }
        }
        mock_client.get.return_value = {'status': 'success', 'data': prediction_data}
        
        # Test endpoint
        endpoint = PredictionEndpoint(mock_client)
        result = endpoint.get_latest_prediction('SLV', use_default_only=True)
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'prediction/latest',
            params={'ticker': 'SLV', 'use_default_only': True}
        )
        assert result == prediction_data
        
    def test_get_predictions(self, mock_client):
        """Test getting prediction history."""
        # Setup mock response
        predictions_data = {
            'ticker': 'GLD',
            'predictions': [
                {'signal': 'BUY', 'confidence': 0.85},
                {'signal': 'HOLD', 'confidence': 0.60}
            ],
            'count': 2,
            'model_info': {
                'model_path': 'models/gld_predictor.joblib',
                'is_ticker_specific': True
            }
        }
        mock_client.get.return_value = {'status': 'success', 'data': predictions_data}
        
        # Test endpoint
        endpoint = PredictionEndpoint(mock_client)
        result = endpoint.get_predictions('GLD', limit=2)
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'predictions',
            params={'ticker': 'GLD', 'limit': 2, 'use_default_only': False}
        )
        assert result == predictions_data
        
    def test_get_predictions_with_date_range(self, mock_client):
        """Test getting prediction history with date range."""
        # Setup mock response
        predictions_data = {
            'ticker': 'GLD',
            'predictions': [
                {'signal': 'BUY', 'confidence': 0.85},
                {'signal': 'HOLD', 'confidence': 0.60}
            ],
            'count': 2,
            'model_info': {
                'model_path': 'models/gld_predictor.joblib',
                'is_ticker_specific': True
            }
        }
        mock_client.get.return_value = {'status': 'success', 'data': predictions_data}
        
        # Test with datetime objects
        start_date = date(2023, 5, 1)
        end_date = date(2023, 5, 2)
        
        endpoint = PredictionEndpoint(mock_client)
        result = endpoint.get_predictions(
            'GLD',
            start_date=start_date,
            end_date=end_date,
            use_default_only=True
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'predictions',
            params={
                'ticker': 'GLD',
                'start_date': '2023-05-01',
                'end_date': '2023-05-02',
                'use_default_only': True
            }
        )
        assert result == predictions_data
        
    @pytest.mark.asyncio
    async def test_get_latest_prediction_async(self, mock_client):
        """Test getting latest prediction asynchronously."""
        # Setup mock response
        prediction_data = {
            'ticker': 'SLV',
            'prediction': {
                'signal': 'BUY',
                'confidence': 0.85,
                'stock_price': 22.75
            },
            'model_info': {
                'model_path': 'models/slv_predictor.joblib',
                'is_ticker_specific': True
            }
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': prediction_data}
        
        # Test endpoint
        endpoint = PredictionEndpoint(mock_client)
        result = await endpoint.get_latest_prediction_async('SLV')
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'prediction/latest',
            params={'ticker': 'SLV', 'use_default_only': False}
        )
        assert result == prediction_data
        
    @pytest.mark.asyncio
    async def test_get_predictions_async(self, mock_client):
        """Test getting prediction history asynchronously."""
        # Setup mock response
        predictions_data = {
            'ticker': 'GLD',
            'predictions': [
                {'signal': 'BUY', 'confidence': 0.85},
                {'signal': 'HOLD', 'confidence': 0.60}
            ],
            'count': 2,
            'model_info': {
                'model_path': 'models/gld_predictor.joblib',
                'is_ticker_specific': True
            }
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': predictions_data}
        
        # Test endpoint
        endpoint = PredictionEndpoint(mock_client)
        result = await endpoint.get_predictions_async('GLD', limit=2)
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'predictions',
            params={'ticker': 'GLD', 'limit': 2, 'use_default_only': False}
        )
        assert result == predictions_data


class TestDataRangeEndpoint:
    """Test the DataRangeEndpoint class."""
    
    def test_get_data_range_required_params(self, mock_client):
        """Test getting data range with only required parameters."""
        # Setup mock response
        data_range = {
            'ticker': 'CVNA',
            'parameters': {
                'start_date': '2023-05-18T09:00:00',
                'end_date': '2023-05-19T16:15:00',
                'date_range': '2023-05-18 to 2023-05-19'
            },
            'data_info': {
                'original_trades': 1250,
                'filtered_trades': 1250,
                'minute_data_points': 780,
                'divergence_points': 780
            },
            'divergence_data': []
        }
        mock_client.get.return_value = {'status': 'success', 'data': data_range}
        
        # Test endpoint
        endpoint = DataRangeEndpoint(mock_client)
        result = endpoint.get_data_range(
            'CVNA',
            start_date='2023-05-18',
            end_date='2023-05-19'
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'data-range',
            params={
                'ticker': 'CVNA',
                'start_date': '2023-05-18',
                'end_date': '2023-05-19'
            }
        )
        assert result == data_range
        
    def test_get_data_range_all_params(self, mock_client):
        """Test getting data range with all parameters."""
        # Setup mock response
        data_range = {
            'ticker': 'CVNA',
            'parameters': {
                'start_date': '2023-05-18T09:00:00',
                'end_date': '2023-05-19T16:15:00',
                'lookback_hours': 6,
                'lambda_short': 0.5,
                'lambda_long': 0.8,
                'date_range': '2023-05-18 to 2023-05-19',
                'filters': {
                    'min_value': 500,
                    'max_value': 5000,
                    'min_size': 5,
                    'max_size': 50,
                    'min_delta': 0.3,
                    'max_delta': 0.7
                }
            },
            'data_info': {
                'original_trades': 1250,
                'filtered_trades': 150,
                'minute_data_points': 780,
                'divergence_points': 780
            },
            'divergence_data': []
        }
        mock_client.get.return_value = {'status': 'success', 'data': data_range}
        
        # Test with datetime objects
        start_date = datetime(2023, 5, 18)
        end_date = datetime(2023, 5, 19)
        
        endpoint = DataRangeEndpoint(mock_client)
        result = endpoint.get_data_range(
            'CVNA',
            start_date=start_date,
            end_date=end_date,
            lookback_hours=6,
            lambda_short=0.5,
            lambda_long=0.8,
            min_value=500,
            max_value=5000,
            min_size=5,
            max_size=50,
            min_delta=0.3,
            max_delta=0.7
        )
        
        # Verify request
        mock_client.get.assert_called_once_with(
            'data-range',
            params={
                'ticker': 'CVNA',
                'start_date': '2023-05-18',
                'end_date': '2023-05-19',
                'lookback_hours': 6,
                'lambda_short': 0.5,
                'lambda_long': 0.8,
                'min_value': 500,
                'max_value': 5000,
                'min_size': 5,
                'max_size': 50,
                'min_delta': 0.3,
                'max_delta': 0.7
            }
        )
        assert result == data_range
        
    @pytest.mark.asyncio
    async def test_get_data_range_async(self, mock_client):
        """Test getting data range asynchronously."""
        # Setup mock response
        data_range = {
            'ticker': 'CVNA',
            'parameters': {
                'start_date': '2023-05-18T09:00:00',
                'end_date': '2023-05-19T16:15:00',
                'date_range': '2023-05-18 to 2023-05-19'
            },
            'data_info': {
                'original_trades': 1250,
                'filtered_trades': 1250,
                'minute_data_points': 780,
                'divergence_points': 780
            },
            'divergence_data': []
        }
        mock_client.get_async.return_value = {'status': 'success', 'data': data_range}
        
        # Test endpoint
        endpoint = DataRangeEndpoint(mock_client)
        result = await endpoint.get_data_range_async(
            'CVNA',
            start_date='2023-05-18',
            end_date='2023-05-19'
        )
        
        # Verify request
        mock_client.get_async.assert_called_once_with(
            'data-range',
            params={
                'ticker': 'CVNA',
                'start_date': '2023-05-18',
                'end_date': '2023-05-19'
            }
        )
        assert result == data_range