"""
Feature flags for controlling system behavior.
"""

import os
from typing import Dict, Any


class FeatureFlags:
    """Central location for all feature flags."""
    
    # Feature flags
    RECONCILIATION_ENABLED = False  # Enable position reconciliation checks
    
    @classmethod
    def get(cls, flag_name: str, default: Any = None) -> Any:
        """Get a feature flag value with a default."""
        return getattr(cls, flag_name, default)
    
    @classmethod
    def get_flags(cls) -> Dict[str, Any]:
        """Get all feature flags as a dictionary."""
        return {
            "RECONCILIATION_ENABLED": cls.RECONCILIATION_ENABLED
        }
    
    @classmethod
    def log_flags(cls, logger):
        """Log current feature flag settings."""
        flags = cls.get_flags()
        if flags:
            logger.info("Feature Flags:")
            for flag, value in flags.items():
                logger.info(f"  {flag}: {value}")
        else:
            logger.info("No feature flags currently active") 