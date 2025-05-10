#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import pytest
import time
from unittest.mock import MagicMock, patch

from src.heartbeat import HeartbeatMonitor


class TestHeartbeatMonitor:
    """Tests for the HeartbeatMonitor class."""

    def test_init(self):
        """Test initialization of the HeartbeatMonitor."""
        # Test default initialization
        monitor = HeartbeatMonitor()
        assert monitor.heartbeat_timeout == 10.0
        assert monitor.heartbeat_interval == 5.0
        assert monitor.on_timeout is None
        assert not monitor.is_running()
        
        # Test custom initialization
        timeout_callback = MagicMock()
        monitor = HeartbeatMonitor(
            heartbeat_timeout=15.0,
            heartbeat_interval=3.0,
            on_timeout=timeout_callback
        )
        assert monitor.heartbeat_timeout == 15.0
        assert monitor.heartbeat_interval == 3.0
        assert monitor.on_timeout == timeout_callback
        assert not monitor.is_running()

    def test_start_stop(self, heartbeat_monitor):
        """Test starting and stopping the heartbeat monitor."""
        # Start monitor
        heartbeat_monitor.start()
        assert heartbeat_monitor.is_running()
        
        # Start again (should do nothing)
        heartbeat_monitor.start()
        assert heartbeat_monitor.is_running()
        
        # Stop monitor
        heartbeat_monitor.stop()
        assert not heartbeat_monitor.is_running()
        
        # Stop again (should do nothing)
        heartbeat_monitor.stop()
        assert not heartbeat_monitor.is_running()

    def test_received_heartbeat(self, heartbeat_monitor):
        """Test updating the heartbeat time."""
        # Get initial heartbeat time
        initial_time = heartbeat_monitor._last_heartbeat_time
        
        # Update heartbeat and check time changed
        time.sleep(0.1)  # Small delay to ensure time difference
        heartbeat_monitor.received_heartbeat()
        assert heartbeat_monitor._last_heartbeat_time > initial_time
        
        # Check time since last heartbeat
        assert heartbeat_monitor.time_since_last_heartbeat() > 0

    @pytest.mark.asyncio
    async def test_timeout_callback(self):
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
            await asyncio.sleep(0.5)  # Wait longer than timeout
            
            # Check timeout callback was called
            timeout_callback.assert_called_once()
        finally:
            # Clean up
            monitor.stop()

    @pytest.mark.asyncio
    async def test_no_timeout_with_heartbeat(self):
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
                await asyncio.sleep(0.1)
            
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
                assert monitor.is_running()
                assert monitor._monitor_thread is not None
                
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
        assert monitor.time_since_last_heartbeat() == 0.0
        
        # After receiving a heartbeat
        monitor.received_heartbeat()
        time.sleep(0.1)
        assert monitor.time_since_last_heartbeat() > 0.0
        assert monitor.time_since_last_heartbeat() < 0.2  # Sanity check

    def test_callback_exception_handling(self):
        """Test that exceptions in timeout callback are handled."""
        # Create a callback that raises an exception
        def error_callback():
            raise ValueError("Test exception")
        
        # Create monitor with the error callback
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0.1,
            heartbeat_interval=0.05,
            on_timeout=error_callback
        )
        
        try:
            # Start monitor
            with patch('src.logger.get_logger') as mock_logger:
                monitor.start()
                time.sleep(0.2)  # Wait for timeout
                
                # Verify error was logged
                for call in mock_logger().error.call_args_list:
                    if "Error in heartbeat timeout callback" in call[0][0]:
                        break
                else:
                    pytest.fail("Error message not logged")
        finally:
            # Clean up
            monitor.stop()

    @pytest.mark.asyncio
    async def test_edge_case_zero_timeout(self):
        """Test edge case with zero timeout."""
        timeout_callback = MagicMock()
        
        # Create monitor with zero timeout
        monitor = HeartbeatMonitor(
            heartbeat_timeout=0,
            heartbeat_interval=0.1,
            on_timeout=timeout_callback
        )
        
        try:
            # Start monitor
            monitor.start()
            
            # Wait for a cycle
            await asyncio.sleep(0.2)
            
            # Should call timeout immediately
            timeout_callback.assert_called()
        finally:
            # Clean up
            monitor.stop()

    @pytest.mark.asyncio
    async def test_edge_case_negative_timeout(self):
        """Test edge case with negative timeout."""
        timeout_callback = MagicMock()
        
        # Create monitor with negative timeout
        monitor = HeartbeatMonitor(
            heartbeat_timeout=-1,
            heartbeat_interval=0.1,
            on_timeout=timeout_callback
        )
        
        try:
            # Start monitor
            monitor.start()
            
            # Wait for a cycle
            await asyncio.sleep(0.2)
            
            # Should call timeout immediately
            timeout_callback.assert_called()
        finally:
            # Clean up
            monitor.stop()
            
    @pytest.mark.asyncio
    async def test_async_cancel_handling(self):
        """Test that cancellation of the async task is handled properly."""
        monitor = HeartbeatMonitor(heartbeat_timeout=10, heartbeat_interval=0.1)
        
        try:
            # Start monitor
            monitor.start()
            assert monitor.is_running()
            
            # Get the monitor task if running in async mode
            if hasattr(monitor, '_monitor_task') and monitor._monitor_task:
                # Cancel the task
                monitor._monitor_task.cancel()
                await asyncio.sleep(0.2)  # Give it time to process
                
                # The monitor should still be "running" from its perspective
                # but the task should be cancelled
                assert monitor._running
                assert monitor._monitor_task.cancelled() or monitor._monitor_task.done()
        finally:
            # Clean up
            monitor.stop()
            assert not monitor.is_running()