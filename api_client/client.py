"""
Base API client for the Multi-Ticker Options Flow Monitor API.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin

import httpx
from httpx import Response, HTTPStatusError

logger = logging.getLogger(__name__)

class ApiException(Exception):
    """Exception raised for API errors."""
    
    def __init__(self, message: str, status_code: int = None, response: Any = None):
        """
        Initialize API exception.
        
        Args:
            message: Error message
            status_code: HTTP status code
            response: Full API response
        """
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)
        
    def __str__(self) -> str:
        """
        Format exception message with status code if available.
        """
        if self.status_code:
            return f"{self.message} (Status code: {self.status_code})"
        return self.message


class ApiClient:
    """
    Base client for the Multi-Ticker Options Flow Monitor API.
    
    This class handles authentication, request preparation, and error handling.
    """
    
    def __init__(
        self, 
        base_url: str = None, 
        api_key: str = None,
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """
        Initialize API client.
        
        Args:
            base_url: API base URL (defaults to environment variable API_BASE_URL)
            api_key: API key for authentication (defaults to environment variable API_KEY)
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url or os.environ.get('API_BASE_URL')
        
        if not self.base_url:
            raise ValueError("Base URL is required. "
                             "Provide it directly or set API_BASE_URL environment variable.")
            
        # Ensure base URL ends with a trailing slash
        if not self.base_url.endswith('/'):
            self.base_url += '/'
            
        self.api_key = api_key or os.environ.get('API_KEY')
        
        if not self.api_key:
            raise ValueError("API key is required. "
                             "Provide it directly or set API_KEY environment variable.")
            
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client = httpx.Client(
            timeout=timeout,
            verify=verify_ssl,
            headers=self._get_default_headers()
        )
        self._async_client = None  # Lazy-loaded
        
    def _get_default_headers(self) -> Dict[str, str]:
        """
        Get default headers for API requests.
        
        Returns:
            Dictionary of headers
        """
        return {
            'X-API-Key': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL for the given endpoint.
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            Full URL
        """
        # Strip leading slash from endpoint if present
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
            
        return urljoin(self.base_url, endpoint)
        
    def _handle_response(self, response: Response) -> Dict[str, Any]:
        """
        Handle API response and extract data or raise appropriate exceptions.
        
        Args:
            response: HTTP response object
            
        Returns:
            Response data as dictionary
            
        Raises:
            ApiException: For API-specific errors
        """
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            error_data = {}
            status_code = response.status_code
            
            try:
                error_data = response.json()
            except json.JSONDecodeError:
                error_message = f"HTTP Error {status_code}: {response.text}"
            else:
                error_message = error_data.get('error', f"HTTP Error {status_code}")
                
            if status_code == 401:
                error_message = "Authentication failed: Invalid API key"
            elif status_code == 429:
                error_message = "Rate limit exceeded"
                
            logger.error(f"API Error: {error_message}")
            raise ApiException(error_message, status_code, error_data) from e
            
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ApiException(f"Invalid JSON response: {response.text}")
            
        # Check for API-level errors in the response
        if data.get('status') == 'error':
            error_message = data.get('error', 'Unknown API error')
            logger.error(f"API Error: {error_message}")
            raise ApiException(error_message, response.status_code, data)
            
        return data
        
    def request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API endpoint.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            ApiException: For request or API errors
        """
        url = self._build_url(endpoint)
        
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
            
        logger.debug(f"Making {method} request to {url}")
        
        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers
            )
            return self._handle_response(response)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error(f"Request failed: {str(e)}")
            raise ApiException(f"Request failed: {str(e)}") from e
            
    def get(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request to API endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response data as dictionary
        """
        return self.request('GET', endpoint, params=params, headers=headers)
        
    def post(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request to API endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response data as dictionary
        """
        return self.request('POST', endpoint, params=params, data=data, headers=headers)
        
    async def request_async(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make asynchronous HTTP request to API endpoint.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            ApiException: For request or API errors
        """
        # Lazy-load async client
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self._get_default_headers()
            )
            
        url = self._build_url(endpoint)
        
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
            
        logger.debug(f"Making async {method} request to {url}")
        
        try:
            response = await self._async_client.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers
            )
            return self._handle_response(response)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error(f"Async request failed: {str(e)}")
            raise ApiException(f"Async request failed: {str(e)}") from e
            
    async def get_async(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make asynchronous GET request to API endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response data as dictionary
        """
        return await self.request_async('GET', endpoint, params=params, headers=headers)
        
    async def post_async(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make asynchronous POST request to API endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response data as dictionary
        """
        return await self.request_async('POST', endpoint, params=params, data=data, headers=headers)
        
    def close(self):
        """
        Close HTTP sessions.
        """
        self._client.close()
        if self._async_client is not None:
            self._async_client.aclose()
            
    async def close_async(self):
        """
        Close asynchronous HTTP session.
        """
        if self._async_client is not None:
            await self._async_client.aclose()
            
    def __enter__(self):
        """
        Support for 'with' context manager.
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Clean up resources on exit from 'with' context.
        """
        self.close()
        
    async def __aenter__(self):
        """
        Support for asynchronous 'with' context manager.
        """
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Clean up resources on exit from asynchronous 'with' context.
        """
        await self.close_async()