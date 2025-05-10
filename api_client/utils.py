"""
Utility functions for the API client.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def load_env(file_path: str = '.env') -> Dict[str, str]:
    """
    Load environment variables from a .env file.
    
    Args:
        file_path: Path to the .env file
        
    Returns:
        Dictionary of loaded environment variables
        
    Example:
        ```python
        # Load variables from .env
        load_env()
        
        # Use environment variables in API client
        from api_client import ApiClient
        client = ApiClient()  # Will use API_KEY and API_BASE_URL from .env
        ```
    """
    if not os.path.exists(file_path):
        logger.warning(f".env file not found at {file_path}")
        return {}
        
    env_vars = {}
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                    
                # Parse key-value pairs
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                        
                    # Set environment variable
                    os.environ[key] = value
                    env_vars[key] = value
                except ValueError:
                    logger.warning(f"Invalid .env line: {line}")
    except Exception as e:
        logger.error(f"Error loading .env file: {str(e)}")
        
    return env_vars

def safe_get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely get an environment variable, returning a default value if not found.
    
    Args:
        key: Environment variable name
        default: Default value to return if variable not found
        
    Returns:
        Environment variable value or default
    """
    return os.environ.get(key, default)