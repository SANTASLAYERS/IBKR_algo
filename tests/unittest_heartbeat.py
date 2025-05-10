#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, '/home/pangasa/IBKR')

from src.heartbeat import HeartbeatMonitor


class TestHeartbeatMonitor(unittest.TestCase):
    """Tests for the HeartbeatMonitor class."""

    def test_init(self):
        """Test initialization of the HeartbeatMonitor."""
        # Test default initialization
        monitor = HeartbeatMonitor()
        self.assertEqual(monitor.heartbeat_timeout, 10.0)
        self.assertEqual(monitor.heartbeat_interval, 5.0)
        self.assertIsNone(monitor.on_timeout)
        self.assertFalse(monitor.is_running())
        
        # Test custom initialization
        timeout_callback = MagicMock()
        monitor = HeartbeatMonitor(
            heartbeat_timeout=15.0,
            heartbeat_interval=3.0,
            on_timeout=timeout_callback
        )
        self.assertEqual(monitor.heartbeat_timeout, 15.0)
        self.assertEqual(monitor.heartbeat_interval, 3.0)
        self.assertEqual(monitor.on_timeout, timeout_callback)
        self.assertFalse(monitor.is_running())

    def test_start_stop(self):
        """Test starting and stopping the heartbeat monitor."""
        # Create monitor
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0.5,  # Short timeout for testing
            heartbeat_interval=0.2,  # Short interval for testing
            on_timeout=lambda: None
        )
        
        try:
            # Start monitor
            monitor.start()
            self.assertTrue(monitor.is_running())
            
            # Start again (should do nothing)
            monitor.start()
            self.assertTrue(monitor.is_running())
            
            # Stop monitor
            monitor.stop()
            self.assertFalse(monitor.is_running())
            
            # Stop again (should do nothing)
            monitor.stop()
            self.assertFalse(monitor.is_running())
        finally:
            # Cleanup
            if monitor.is_running():
                monitor.stop()

    def test_received_heartbeat(self):
        """Test updating the heartbeat time."""
        # Create monitor
        monitor = HeartbeatMonitor()
        
        # Get initial heartbeat time
        initial_time = monitor._last_heartbeat_time
        
        # Update heartbeat and check time changed
        time.sleep(0.1)  # Small delay to ensure time difference
        monitor.received_heartbeat()
        self.assertGreater(monitor._last_heartbeat_time, initial_time)
        
        # Check time since last heartbeat
        self.assertGreater(monitor.time_since_last_heartbeat(), 0)

    def test_timeout_callback(self):
        """Test that timeout callback is called when heartbeat times out."""
        timeout_callback = MagicMock()
        
        # Create monitor with short timeout for testing
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0.3,  # 300ms timeout
            heartbeat_interval=0.1,  # 100ms check interval
            on_timeout=timeout_callback
        )
        
        try:
            # Start monitor
            monitor.start()
            
            # Wait for timeout
            time.sleep(0.5)  # Wait longer than timeout
            
            # Check timeout callback was called
            timeout_callback.assert_called_once()
        finally:
            # Clean up
            monitor.stop()

    def test_no_timeout_with_heartbeat(self):
        """Test that timeout callback is not called when heartbeat is received."""
        timeout_callback = MagicMock()
        
        # Create monitor with short timeout for testing
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0.3,  # 300ms timeout
            heartbeat_interval=0.1,  # 100ms check interval
            on_timeout=timeout_callback
        )
        
        try:
            # Start monitor
            monitor.start()
            
            # Send heartbeats regularly
            for _ in range(4):
                monitor.received_heartbeat()
                time.sleep(0.1)
            
            # Verify timeout callback was not called
            timeout_callback.assert_not_called()
        finally:
            # Clean up
            monitor.stop()

    def test_threaded_monitor(self):
        """Test the threaded implementation of the heartbeat monitor."""
        timeout_callback = MagicMock()
        
        # Create monitor
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0.3,
            heartbeat_interval=0.1,
            on_timeout=timeout_callback
        )
        
        try:
            # Patch asyncio.get_event_loop to raise RuntimeError
            # This will force the monitor to use threading
            with patch('asyncio.get_event_loop', side_effect=RuntimeError):
                monitor.start()
                self.assertTrue(monitor.is_running())
                self.assertIsNotNone(monitor._monitor_thread)
                
                # Wait for thread to check heartbeat
                time.sleep(0.5)
                
                # Verify timeout callback was called
                timeout_callback.assert_called()
        finally:
            # Clean up
            monitor.stop()

    def test_time_since_last_heartbeat(self):
        """Test calculating time since last heartbeat."""
        monitor = HeartbeatMonitor()
        
        # When no heartbeat has been received
        self.assertEqual(monitor.time_since_last_heartbeat(), 0.0)
        
        # After receiving a heartbeat
        monitor.received_heartbeat()
        time.sleep(0.1)
        self.assertGreater(monitor.time_since_last_heartbeat(), 0.0)
        self.assertLess(monitor.time_since_last_heartbeat(), 0.2)  # Sanity check


if __name__ == '__main__':
    unittest.main()