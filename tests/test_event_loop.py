#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import concurrent.futures
import pytest
import signal
import threading
import time
from unittest.mock import MagicMock, patch

from src.event_loop import IBKREventLoop


class TestIBKREventLoop:
    """Tests for the IBKREventLoop class."""

    def test_init(self):
        """Test initialization of the IBKREventLoop."""
        # Test default initialization
        loop = IBKREventLoop()
        assert not loop._running
        assert loop._thread is None
        assert loop._stop_event is not None
        assert loop._loop is None
        assert loop._thread_pool is not None
        assert len(loop._message_processors) == 0
        assert len(loop._scheduled_tasks) == 0
        
        # Test custom initialization
        loop = IBKREventLoop(max_workers=5)
        assert loop._thread_pool._max_workers == 5

    def test_start_stop(self, event_loop_instance):
        """Test starting and stopping the event loop."""
        # Start loop
        event_loop_instance.start()
        assert event_loop_instance.is_running()
        assert event_loop_instance._thread is not None
        assert event_loop_instance._loop is not None
        
        # Stop loop
        event_loop_instance.stop()
        assert not event_loop_instance.is_running()
        assert event_loop_instance._thread is None
        
        # Start again
        event_loop_instance.start()
        assert event_loop_instance.is_running()
        
        # Stop again
        event_loop_instance.stop()
        assert not event_loop_instance.is_running()

    def test_add_remove_message_processor(self, event_loop_instance):
        """Test adding and removing message processors."""
        # Create test processors
        processor1 = MagicMock(__name__="processor1")
        processor2 = MagicMock(__name__="processor2")
        
        # Add processors
        event_loop_instance.add_message_processor(processor1)
        assert len(event_loop_instance._message_processors) == 1
        assert processor1 in event_loop_instance._message_processors
        
        event_loop_instance.add_message_processor(processor2)
        assert len(event_loop_instance._message_processors) == 2
        assert processor2 in event_loop_instance._message_processors
        
        # Add duplicate (should be ignored)
        event_loop_instance.add_message_processor(processor1)
        assert len(event_loop_instance._message_processors) == 2
        
        # Remove processor
        event_loop_instance.remove_message_processor(processor1)
        assert len(event_loop_instance._message_processors) == 1
        assert processor1 not in event_loop_instance._message_processors
        assert processor2 in event_loop_instance._message_processors
        
        # Remove non-existent processor (should do nothing)
        event_loop_instance.remove_message_processor(processor1)
        assert len(event_loop_instance._message_processors) == 1
        
        # Remove remaining processor
        event_loop_instance.remove_message_processor(processor2)
        assert len(event_loop_instance._message_processors) == 0

    @pytest.mark.asyncio
    async def test_process_messages(self, event_loop_instance):
        """Test that message processors are called in the event loop."""
        # Create test processor
        processor = MagicMock(__name__="test_processor")
        event_loop_instance.add_message_processor(processor)
        
        try:
            # Start loop
            event_loop_instance.start()
            
            # Wait for processor to be called
            # The loop runs continuously so it should call the processor multiple times
            await asyncio.sleep(0.5)
            
            # Verify processor was called
            assert processor.call_count > 0
        finally:
            # Clean up
            event_loop_instance.stop()

    @pytest.mark.asyncio
    async def test_processor_exception_handling(self, event_loop_instance):
        """Test that exceptions in processors are handled."""
        # Create processor that raises an exception
        def error_processor():
            raise ValueError("Test exception")
        
        error_processor.__name__ = "error_processor"
        event_loop_instance.add_message_processor(error_processor)
        
        try:
            # Start loop with mocked logger
            with patch('src.logger.get_logger') as mock_logger:
                event_loop_instance.start()
                
                # Wait for processor to be called
                await asyncio.sleep(0.5)
                
                # Verify error was logged
                mock_logger().error.assert_called()
        finally:
            # Clean up
            event_loop_instance.stop()

    @pytest.mark.asyncio
    async def test_schedule_task(self, event_loop_instance):
        """Test scheduling an async task in the event loop."""
        # Create a coroutine for testing
        result = None
        
        async def test_coroutine():
            nonlocal result
            await asyncio.sleep(0.1)
            result = "done"
            return "success"
        
        try:
            # Start loop
            event_loop_instance.start()
            
            # Schedule task
            with pytest.raises(RuntimeError):
                # Should fail when not running
                event_loop_instance.stop()
                event_loop_instance.schedule_task(test_coroutine())
            
            # Start again and schedule task
            event_loop_instance.start()
            task_future = event_loop_instance.schedule_task(test_coroutine())
            
            # Wait for task to complete
            await asyncio.sleep(0.3)
            
            # Verify task was completed
            assert result == "done"
            
            # Check task_id is removed from scheduled tasks
            # Since the task is probably done by now, it should be cleaned up
            assert len(event_loop_instance._scheduled_tasks) == 0
        finally:
            # Clean up
            event_loop_instance.stop()

    @pytest.mark.asyncio
    async def test_cancel_task(self, event_loop_instance):
        """Test cancelling a scheduled task."""
        # Create a long-running coroutine
        result = None
        
        async def long_coroutine():
            nonlocal result
            await asyncio.sleep(5)  # Long enough to be cancelled
            result = "done"
            return "success"
        
        try:
            # Start loop
            event_loop_instance.start()
            
            # Schedule task
            task_id = "test_task"
            task_future = event_loop_instance.schedule_task(long_coroutine(), task_id)
            
            # Wait briefly for task to start
            await asyncio.sleep(0.1)
            
            # Cancel task
            event_loop_instance.cancel_task(task_id)
            
            # Wait briefly for cancellation
            await asyncio.sleep(0.1)
            
            # Verify task was cancelled
            assert task_id not in event_loop_instance._scheduled_tasks
            assert result is None  # Task shouldn't have completed
        finally:
            # Clean up
            event_loop_instance.stop()

    def test_signal_handling(self, event_loop_instance):
        """Test that signal handlers are set up correctly."""
        # Mock signal module
        with patch('signal.signal') as mock_signal:
            # Start loop
            event_loop_instance.start()
            
            # Verify signal handlers were set up
            assert mock_signal.call_count >= 2  # Should set handlers for at least SIGINT and SIGTERM
            
            # Stop loop
            event_loop_instance.stop()
            
            # Verify signal handlers were restored
            assert mock_signal.call_count >= 4  # Should restore original handlers

    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self, event_loop_instance):
        """Test cancelling all tasks."""
        # Create multiple coroutines
        results = [None, None]
        
        async def coroutine1():
            await asyncio.sleep(5)
            results[0] = "done"
            
        async def coroutine2():
            await asyncio.sleep(5)
            results[1] = "done"
        
        try:
            # Start loop
            event_loop_instance.start()
            
            # Schedule tasks
            event_loop_instance.schedule_task(coroutine1(), "task1")
            event_loop_instance.schedule_task(coroutine2(), "task2")
            
            # Wait briefly for tasks to start
            await asyncio.sleep(0.1)
            assert len(event_loop_instance._scheduled_tasks) == 2
            
            # Call _cancel_all_tasks
            event_loop_instance._cancel_all_tasks()
            
            # Wait briefly for cancellation
            await asyncio.sleep(0.1)
            
            # Verify all tasks were cancelled
            assert len(event_loop_instance._scheduled_tasks) == 0
            assert results == [None, None]  # Tasks shouldn't have completed
        finally:
            # Clean up
            event_loop_instance.stop()

    @pytest.mark.asyncio
    async def test_run_coroutine(self, event_loop_instance):
        """Test running a coroutine in the event loop."""
        # Create a coroutine for testing
        async def test_coroutine():
            await asyncio.sleep(0.1)
            return "success"
        
        try:
            # Should fail when not running
            with pytest.raises(RuntimeError):
                event_loop_instance.run_coroutine(test_coroutine())
            
            # Start loop
            event_loop_instance.start()
            
            # Run coroutine
            result = event_loop_instance.run_coroutine(test_coroutine())
            
            # Verify result
            assert result == "success"
            
            # Test running coroutine asynchronously
            future = event_loop_instance.run_coroutine_async(test_coroutine())
            result = future.result(timeout=1.0)
            assert result == "success"
        finally:
            # Clean up
            event_loop_instance.stop()

    def test_loop_shutdown_exception_handling(self):
        """Test that exceptions during loop shutdown are handled."""
        loop = IBKREventLoop()
        
        # Patch methods to simulate exceptions during shutdown
        with patch.object(asyncio, 'all_tasks', side_effect=RuntimeError("Test exception")), \
             patch('src.logger.get_logger') as mock_logger:
                
            # Start and stop loop
            loop.start()
            loop.stop()
            
            # Verify error was logged
            mock_logger().error.assert_called()

    def test_thread_join_timeout(self):
        """Test handling of thread join timeout during stop."""
        loop = IBKREventLoop()
        
        # Create a mock thread that never joins
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread.join = MagicMock()
        
        # Start the loop and replace thread with our mock
        loop.start()
        original_thread = loop._thread
        loop._thread = mock_thread
        
        # Patch logger to check warnings
        with patch('src.logger.get_logger') as mock_logger:
            # Stop the loop
            loop.stop()
            
            # Verify warning was logged
            mock_logger().warning.assert_called_with(
                "Event loop thread did not terminate within timeout"
            )
        
        # Clean up the original thread
        original_thread.join()

    @pytest.mark.asyncio
    async def test_edge_case_empty_loop(self):
        """Test edge case with an empty event loop."""
        loop = IBKREventLoop()
        
        try:
            # Start with no processors
            loop.start()
            
            # Wait for a cycle
            await asyncio.sleep(0.2)
            
            # Nothing should happen, but loop should still be running
            assert loop.is_running()
        finally:
            # Clean up
            loop.stop()

    @pytest.mark.asyncio
    async def test_edge_case_rapid_start_stop(self):
        """Test edge case with rapid start/stop cycles."""
        loop = IBKREventLoop()
        
        # Perform rapid start/stop cycles
        for _ in range(5):
            loop.start()
            assert loop.is_running()
            await asyncio.sleep(0.05)
            loop.stop()
            assert not loop.is_running()
            await asyncio.sleep(0.05)
        
        # One final cycle to verify stability
        loop.start()
        assert loop.is_running()
        await asyncio.sleep(0.1)
        loop.stop()
        assert not loop.is_running()