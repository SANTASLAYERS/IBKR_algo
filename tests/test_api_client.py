"""
Tests for the API client module.
"""

import os
import json
import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

from api_client.client import ApiClient, ApiException


class TestApiClient:
    """Test suite for the ApiClient class."""
    
    @pytest.fixture
    def api_client(self):
        """Create a test API client."""
        # Use test values for base URL and API key
        os.environ['API_BASE_URL'] = 'https://test-api.example.com/api/v1'
        os.environ['API_KEY'] = 'test-api-key'
        client = ApiClient()
        yield client
        # Clean up
        client.close()
        del os.environ['API_BASE_URL']
        del os.environ['API_KEY']
        
    @pytest.fixture
    def direct_api_client(self):
        """Create a test API client with direct parameters."""
        client = ApiClient(
            base_url='https://direct-api.example.com/api/v1',
            api_key='direct-test-key',
            timeout=10,
            verify_ssl=False
        )
        yield client
        # Clean up
        client.close()
        
    def test_init_with_env_vars(self, api_client):
        """Test initializing client with environment variables."""
        assert api_client.base_url == 'https://test-api.example.com/api/v1/'
        assert api_client.api_key == 'test-api-key'
        assert api_client.timeout == 30  # Default value
        assert api_client.verify_ssl is True  # Default value
        
    def test_init_with_direct_params(self, direct_api_client):
        """Test initializing client with direct parameters."""
        assert direct_api_client.base_url == 'https://direct-api.example.com/api/v1/'
        assert direct_api_client.api_key == 'direct-test-key'
        assert direct_api_client.timeout == 10
        assert direct_api_client.verify_ssl is False
        
    def test_init_missing_base_url(self):
        """Test initialization without base URL should raise ValueError."""
        with pytest.raises(ValueError, match="Base URL is required"):
            ApiClient(api_key='test-key')
            
    def test_init_missing_api_key(self):
        """Test initialization without API key should raise ValueError."""
        with pytest.raises(ValueError, match="API key is required"):
            ApiClient(base_url='https://api.example.com')
            
    def test_get_default_headers(self, api_client):
        """Test default headers include API key and content type."""
        headers = api_client._get_default_headers()
        assert headers['X-API-Key'] == 'test-api-key'
        assert headers['Accept'] == 'application/json'
        assert headers['Content-Type'] == 'application/json'
        
    def test_build_url(self, api_client):
        """Test URL building from base URL and endpoint."""
        # Without leading slash
        url = api_client._build_url('status')
        assert url == 'https://test-api.example.com/api/v1/status'
        
        # With leading slash
        url = api_client._build_url('/status')
        assert url == 'https://test-api.example.com/api/v1/status'
    
    def test_enter_exit(self, api_client):
        """Test context manager protocol."""
        with api_client as client:
            assert client is api_client
    
    def test_request_network_error(self, api_client):
        """Test handling network errors."""
        with patch.object(api_client._client, 'request', side_effect=httpx.ConnectError('Connection failed')):
            with pytest.raises(ApiException) as exc_info:
                api_client.request('GET', 'test-endpoint')
                
        assert 'Request failed: Connection failed' in str(exc_info.value)
        
    def test_request_timeout(self, api_client):
        """Test handling request timeouts."""
        with patch.object(api_client._client, 'request', side_effect=httpx.TimeoutException('Request timed out')):
            with pytest.raises(ApiException) as exc_info:
                api_client.request('GET', 'test-endpoint')
                
        assert 'Request failed: Request timed out' in str(exc_info.value)
    
    def test_close(self, api_client):
        """Test client cleanup."""
        # Create async client as a mock
        async_client_mock = MagicMock()
        async_client_mock.aclose = AsyncMock()
        api_client._async_client = async_client_mock
        
        # Also mock the client close method
        api_client._client.close = MagicMock()
        
        api_client.close()
        
        # Verify sync client was closed
        api_client._client.close.assert_called_once()
        
    def test_handle_response(self, api_client):
        """Test response handling for different scenarios."""
        # Test success case
        success_response = httpx.Response(200, json={"status": "success", "data": {"test": True}})
        with patch.object(success_response, 'raise_for_status'):
            result = api_client._handle_response(success_response)
            assert result == {"status": "success", "data": {"test": True}}
        
        # Test API error in 200 response
        api_error_response = httpx.Response(200, json={"status": "error", "error": "API Error"})
        with patch.object(api_error_response, 'raise_for_status'):
            with pytest.raises(ApiException) as exc_info:
                api_client._handle_response(api_error_response)
            assert "API Error" in str(exc_info.value)
            assert exc_info.value.status_code == 200
        
        # Test HTTP error (401 unauthorized)
        http_error_response = httpx.Response(401, json={"status": "error", "error": "Unauthorized"})
        # Mock raise_for_status to raise HTTPStatusError
        with patch.object(http_error_response, 'raise_for_status', side_effect=httpx.HTTPStatusError("401", request=None, response=http_error_response)):
            with pytest.raises(ApiException) as exc_info:
                api_client._handle_response(http_error_response)
            assert "Authentication failed" in str(exc_info.value)
            assert exc_info.value.status_code == 401
        
        # Test rate limit error
        rate_limit_response = httpx.Response(429, json={"status": "error", "error": "Too Many Requests"})
        with patch.object(rate_limit_response, 'raise_for_status', side_effect=httpx.HTTPStatusError("429", request=None, response=rate_limit_response)):
            with pytest.raises(ApiException) as exc_info:
                api_client._handle_response(rate_limit_response)
            assert "Rate limit exceeded" in str(exc_info.value)
            assert exc_info.value.status_code == 429
        
        # Test invalid JSON response
        invalid_json_response = httpx.Response(200, content=b"Not valid JSON")
        with patch.object(invalid_json_response, 'raise_for_status'):
            with pytest.raises(ApiException) as exc_info:
                api_client._handle_response(invalid_json_response)
            assert "Invalid JSON response" in str(exc_info.value)
    
    def test_get_method(self, api_client):
        """Test the GET convenience method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        
        # Mock the request method
        with patch.object(api_client, 'request', return_value=response_data) as mock_request:
            result = api_client.get('endpoint', params={"param": "value"}, headers={"Custom": "Header"})
        
        # Verify the request was made correctly
        mock_request.assert_called_once_with(
            'GET', 
            'endpoint', 
            params={"param": "value"}, 
            headers={"Custom": "Header"}
        )
        assert result == response_data
    
    def test_post_method(self, api_client):
        """Test the POST convenience method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        
        # Mock the request method
        with patch.object(api_client, 'request', return_value=response_data) as mock_request:
            result = api_client.post(
                'endpoint', 
                params={"param": "value"}, 
                data={"data": "value"}, 
                headers={"Custom": "Header"}
            )
        
        # Verify the request was made correctly
        mock_request.assert_called_once_with(
            'POST', 
            'endpoint', 
            params={"param": "value"}, 
            data={"data": "value"}, 
            headers={"Custom": "Header"}
        )
        assert result == response_data
    
    @pytest.mark.asyncio
    async def test_get_async_method(self, api_client):
        """Test the GET async convenience method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        
        # Mock the request_async method
        with patch.object(api_client, 'request_async', AsyncMock(return_value=response_data)) as mock_request:
            result = await api_client.get_async('endpoint', params={"param": "value"}, headers={"Custom": "Header"})
        
        # Verify the request was made correctly
        mock_request.assert_called_once_with(
            'GET', 
            'endpoint', 
            params={"param": "value"}, 
            headers={"Custom": "Header"}
        )
        assert result == response_data
    
    @pytest.mark.asyncio
    async def test_post_async_method(self, api_client):
        """Test the POST async convenience method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        
        # Mock the request_async method
        with patch.object(api_client, 'request_async', AsyncMock(return_value=response_data)) as mock_request:
            result = await api_client.post_async(
                'endpoint', 
                params={"param": "value"}, 
                data={"data": "value"}, 
                headers={"Custom": "Header"}
            )
        
        # Verify the request was made correctly
        mock_request.assert_called_once_with(
            'POST', 
            'endpoint', 
            params={"param": "value"}, 
            data={"data": "value"}, 
            headers={"Custom": "Header"}
        )
        assert result == response_data
    
    @pytest.mark.asyncio
    async def test_aenter_aexit(self, api_client):
        """Test async context manager protocol."""
        # Set up an async mock
        api_client._async_client = MagicMock()
        api_client._async_client.aclose = AsyncMock()

        async with api_client as client:
            assert client is api_client

        # aclose should be called during __aexit__
        api_client._async_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_async(self, api_client):
        """Test async client cleanup."""
        # Create async client with AsyncMock
        async_client_mock = MagicMock()
        async_client_mock.aclose = AsyncMock()
        api_client._async_client = async_client_mock
        
        await api_client.close_async()
        
        # Verify async client was closed
        api_client._async_client.aclose.assert_called_once()
    
    def test_request(self, api_client):
        """Test the request method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        
        # Mock the client's request method
        with patch.object(api_client._client, 'request', return_value=mock_response) as mock_request:
            with patch.object(api_client, '_handle_response', return_value=response_data) as mock_handle_response:
                result = api_client.request(
                    'GET', 
                    'test-endpoint',
                    params={"param": "value"},
                    data={"data": "value"},
                    headers={"Custom": "Header"}
                )
        
        # Verify the client's request was called with correct arguments
        mock_request.assert_called_once_with(
            method='GET',
            url='https://test-api.example.com/api/v1/test-endpoint',
            params={"param": "value"},
            json={"data": "value"},
            headers={
                'X-API-Key': 'test-api-key',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Custom': 'Header'
            }
        )
        
        # Verify handle_response was called with the response
        mock_handle_response.assert_called_once_with(mock_response)
        
        # Verify the result
        assert result == response_data
    
    @pytest.mark.asyncio
    async def test_request_async(self, api_client):
        """Test the async request method."""
        response_data = {"status": "success", "data": {"key": "value"}}
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        
        # Create an AsyncMock for the async client
        mock_async_client = MagicMock()
        mock_async_client.request = AsyncMock(return_value=mock_response)
        api_client._async_client = mock_async_client
        
        # Mock handle_response
        with patch.object(api_client, '_handle_response', return_value=response_data) as mock_handle_response:
            result = await api_client.request_async(
                'GET', 
                'test-endpoint',
                params={"param": "value"},
                data={"data": "value"},
                headers={"Custom": "Header"}
            )
        
        # Verify the async client's request was called with correct arguments
        mock_async_client.request.assert_called_once_with(
            method='GET',
            url='https://test-api.example.com/api/v1/test-endpoint',
            params={"param": "value"},
            json={"data": "value"},
            headers={
                'X-API-Key': 'test-api-key',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Custom': 'Header'
            }
        )
        
        # Verify handle_response was called with the response
        mock_handle_response.assert_called_once_with(mock_response)
        
        # Verify the result
        assert result == response_data