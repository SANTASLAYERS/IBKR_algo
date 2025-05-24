#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from concurrent.futures import ThreadPoolExecutor
import signal
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .logger import get_logger

logger = get_logger(__name__)

class IBKREventLoop:
    """
    Manages the event loop for processing IBKR API messages.
    Handles both synchronous message processing with EClient and asynchronous tasks.
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize the IBKR event loop.
        
        Args:
            max_workers: Maximum number of workers for thread pool executor
        """
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._loop = None
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # List of client message processors to run in the event loop
        self._message_processors: List[Callable[[], None]] = []
        
        # Scheduled tasks
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        
        # Signal handling
        self._original_sigint_handler = None
        self._original_sigterm_handler = None
    
    def start(self):
        """
        Start the event loop in a separate thread.
        """
        if self._running:
            logger.warning("Event loop already running")
            return
        
        self._running = True
        self._stop_event.clear()
        
        # Create a new thread for the event loop
        self._thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name="IBKREventLoop"
        )
        self._thread.start()
        
        # Wait for the event loop to be ready
        while self._loop is None and self._running:
            time.sleep(0.01)
            
        logger.info("IBKR event loop started")
        
        # Set up signal handlers
        self._setup_signal_handlers()
    
    def _run_event_loop(self):
        """
        Run the asyncio event loop in the thread.
        """
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Schedule the message processing task
            self._loop.create_task(self._process_messages())
            
            # Run the event loop
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Error in event loop: {str(e)}")
        finally:
            try:
                self._cancel_all_tasks()
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception as e:
                # Log the error - this is tested in the test suite
                logger.error(f"Error shutting down event loop: {str(e)}")
                # In test mode, print to make the error visible in the test output as well
                if hasattr(self, '_testing') and self._testing:
                    print(f"Error shutting down event loop: {str(e)}")
            finally:
                asyncio.set_event_loop(None)
                self._loop.close()
                self._loop = None
                logger.debug("Event loop closed")
    
    async def _process_messages(self):
        """
        Process client messages and run scheduled tasks.
        """
        while self._running and not self._stop_event.is_set():
            try:
                # Run all message processors
                for processor in self._message_processors:
                    try:
                        # Run the message processor in the thread pool
                        await self._loop.run_in_executor(self._thread_pool, processor)
                    except Exception as e:
                        # Log the error - this is tested in the test suite
                        logger.error(f"Error in message processor: {str(e)}")
                        # In test mode, print to make the error visible in the test output as well
                        if hasattr(self, '_testing') and self._testing:
                            print(f"Error in message processor: {str(e)}")
                
                # Small sleep to prevent CPU hogging
                await asyncio.sleep(0.001)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing messages: {str(e)}")
                await asyncio.sleep(0.1)
    
    def stop(self):
        """
        Stop the event loop.
        """
        if not self._running:
            return
            
        logger.info("Stopping IBKR event loop")
        self._running = False
        self._stop_event.set()
        
        # Restore signal handlers
        self._restore_signal_handlers()
        
        # Stop the event loop
        if self._loop is not None:
            try:
                # Use call_soon_threadsafe to stop the loop from another thread
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception as e:
                logger.error(f"Error stopping event loop: {str(e)}")
        
        # Don't join the thread - use safe pattern like TWSConnection
        # DON'T JOIN THE THREAD - let daemon thread clean up naturally
        # This prevents potential blocking and timing issues
        self._thread = None
        logger.info("IBKR event loop stopped")
        
        # Shutdown thread pool
        self._thread_pool.shutdown()
    
    def add_message_processor(self, processor: Callable[[], None]):
        """
        Add a message processor function.
        
        Args:
            processor: Function that processes client messages
        """
        if processor not in self._message_processors:
            self._message_processors.append(processor)
            logger.debug(f"Added message processor: {processor.__name__ if hasattr(processor, '__name__') else processor}")
    
    def remove_message_processor(self, processor: Callable[[], None]):
        """
        Remove a message processor function.
        
        Args:
            processor: Function to remove
        """
        if processor in self._message_processors:
            self._message_processors.remove(processor)
            logger.debug(f"Removed message processor: {processor.__name__ if hasattr(processor, '__name__') else processor}")
    
    def schedule_task(self, coroutine, task_name: str = None):
        """
        Schedule a coroutine to run in the event loop.
        
        Args:
            coroutine: Coroutine to schedule
            task_name: Optional name for the task
        
        Returns:
            Task ID
        """
        if not self._running or self._loop is None:
            raise RuntimeError("Event loop is not running")
            
        task_id = task_name or f"task_{id(coroutine)}"
        
        # Use call_soon_threadsafe to create the task from another thread
        def _create_task():
            task = self._loop.create_task(coroutine)
            self._scheduled_tasks[task_id] = task
            
            # Set cleanup callback
            task.add_done_callback(
                lambda t: self._scheduled_tasks.pop(task_id, None)
            )
            return task
            
        return self._loop.call_soon_threadsafe(_create_task)
    
    def cancel_task(self, task_id: str):
        """
        Cancel a scheduled task.
        
        Args:
            task_id: ID of the task to cancel
        """
        if task_id in self._scheduled_tasks:
            task = self._scheduled_tasks[task_id]
            
            def _cancel_task():
                if not task.done():
                    task.cancel()
            
            self._loop.call_soon_threadsafe(_cancel_task)
            logger.debug(f"Cancelled task: {task_id}")
    
    def _cancel_all_tasks(self):
        """
        Cancel all scheduled tasks.
        """
        if self._loop is None:
            return
            
        # Get all tasks
        tasks = asyncio.all_tasks(self._loop)
        if not tasks:
            return
            
        # Cancel all tasks
        for task in tasks:
            task.cancel()
            
        # Wait for tasks to be cancelled
        self._loop.run_until_complete(
            asyncio.gather(*tasks, return_exceptions=True)
        )
        
        self._scheduled_tasks.clear()
    
    def _setup_signal_handlers(self):
        """
        Set up signal handlers for graceful shutdown.
        """
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down")
            self.stop()
            
            # Call original handler if it exists
            if signum == signal.SIGINT and self._original_sigint_handler:
                if self._original_sigint_handler is not signal.SIG_IGN and \
                   self._original_sigint_handler is not signal.SIG_DFL:
                    self._original_sigint_handler(signum, frame)
            elif signum == signal.SIGTERM and self._original_sigterm_handler:
                if self._original_sigterm_handler is not signal.SIG_IGN and \
                   self._original_sigterm_handler is not signal.SIG_DFL:
                    self._original_sigterm_handler(signum, frame)
        
        # Save original handlers
        self._original_sigint_handler = signal.signal(signal.SIGINT, signal_handler)
        self._original_sigterm_handler = signal.signal(signal.SIGTERM, signal_handler)
    
    def _restore_signal_handlers(self):
        """
        Restore original signal handlers.
        """
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        
        if self._original_sigterm_handler:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
    
    def is_running(self) -> bool:
        """
        Check if the event loop is running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def run_coroutine(self, coroutine) -> Any:
        """
        Run a coroutine in the event loop and wait for it to complete.
        
        Args:
            coroutine: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        if not self._running or self._loop is None:
            raise RuntimeError("Event loop is not running")
            
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result()
    
    def run_coroutine_async(self, coroutine) -> asyncio.Future:
        """
        Run a coroutine in the event loop asynchronously.
        
        Args:
            coroutine: Coroutine to run
            
        Returns:
            Future object that can be used to get the result
        """
        if not self._running or self._loop is None:
            raise RuntimeError("Event loop is not running")
            
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)