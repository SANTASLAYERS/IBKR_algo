#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Basic TWS connection tests.

These tests validate the fundamental connection capabilities with TWS.
"""

import pytest
import logging

from tests.integration.conftest import get_tws_credentials, is_tws_available

logger = logging.getLogger("basic_tws_tests")


class TestBasicTWSConnection:
    """Basic tests for TWS connection functionality."""

    def test_tws_availability_check(self):
        """Test that we can check if TWS is available."""
        credentials = get_tws_credentials()
        
        # This should not raise an exception
        available = is_tws_available(credentials["host"], credentials["port"])
        
        # The result should be a boolean
        assert isinstance(available, bool)
        logger.info(f"TWS availability at {credentials['host']}:{credentials['port']}: {available}")

    def test_tws_credentials_format(self):
        """Test that TWS credentials are in the expected format."""
        credentials = get_tws_credentials()
        
        # Check required fields exist
        assert "host" in credentials
        assert "port" in credentials
        assert "client_id" in credentials
        assert "account" in credentials
        
        # Check types
        assert isinstance(credentials["host"], str)
        assert isinstance(credentials["port"], int)
        assert isinstance(credentials["client_id"], int)
        assert isinstance(credentials["account"], str)
        
        # Check reasonable values
        assert credentials["port"] > 0
        assert credentials["client_id"] >= 0
        
        logger.info(f"TWS credentials: {credentials}")

    @pytest.mark.usefixtures("check_tws")
    def test_tws_socket_connection(self):
        """Test basic socket connection to TWS (requires TWS to be running)."""
        credentials = get_tws_credentials()
        
        # This should succeed if TWS is running
        available = is_tws_available(credentials["host"], credentials["port"], timeout=5.0)
        
        assert available, f"Cannot connect to TWS at {credentials['host']}:{credentials['port']}"
        logger.info("✅ Successfully verified socket connection to TWS") 