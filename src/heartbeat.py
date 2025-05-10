#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import time
from typing import Callable, Optional
import threading

from .logger import get_logger

logger = get_logger(__name__)

class HeartbeatMonitor:
    """
    Monitors the heartbeat of the connection to IBKR's TWS or Gateway.
    Triggers a callback when the heartbeat times out, indicating a potential connection loss.
    """
    
    def __init__(
        self, 
        heartbeat_timeout: float = 10.0, 
        heartbeat_interval: float = 5.0,
        on_timeout: Optional[Callable] = None
    ):
        """
        Initialize the heartbeat monitor
        
        Args:
            heartbeat_timeout: Time in seconds after which connection is considered lost
            heartbeat_interval: Time in seconds between heartbeat checks
            on_timeout: Callback to call when heartbeat times out
        """
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_interval = heartbeat_interval
        self.on_timeout = on_timeout
        
        self._last_heartbeat_time = 0.0
        self._running = False
        self._monitor_task = None
        self._loop = None
        self._monitor_thread = None
        self._thread_stop_event = threading.Event()
        
    def start(self):
        """Start the heartbeat monitoring"""
        if self._running:
            return
            
        self._running = True
        self._last_heartbeat_time = time.time()
        
        # Check if running in an asyncio context
        try:
            self._loop = asyncio.get_event_loop()
            self._start_async_monitor()
        except RuntimeError:
            # Not in asyncio context, use threading
            self._start_threaded_monitor()
            
        logger.debug("Heartbeat monitor started")
        
    def _start_async_monitor(self):
        """Start the heartbeat monitor using asyncio"""
        self._monitor_task = asyncio.create_task(self._monitor_heartbeat_async())
        
    def _start_threaded_monitor(self):
        """Start the heartbeat monitor using threading"""
        self._thread_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_heartbeat_threaded,
            daemon=True
        )
        self._monitor_thread.start()
    
    async def _monitor_heartbeat_async(self):
        """Monitor the heartbeat asynchronously"""
        while self._running:
            self._check_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
    
    def _monitor_heartbeat_threaded(self):
        """Monitor the heartbeat in a separate thread"""
        while self._running and not self._thread_stop_event.is_set():
            self._check_heartbeat()
            time.sleep(self.heartbeat_interval)
    
    def _check_heartbeat(self):
        """Check if heartbeat has timed out"""
        if not self._running:
            return
            
        current_time = time.time()
        time_since_last_heartbeat = current_time - self._last_heartbeat_time
        
        if time_since_last_heartbeat > self.heartbeat_timeout:
            logger.warning(
                f"Heartbeat timeout: {time_since_last_heartbeat:.2f}s " 
                f"(threshold: {self.heartbeat_timeout:.2f}s)"
            )
            
            if self.on_timeout:
                try:
                    self.on_timeout()
                except Exception as e:
                    logger.error(f"Error in heartbeat timeout callback: {str(e)}")
    
    def stop(self):
        """Stop the heartbeat monitoring"""
        if not self._running:
            return
            
        self._running = False
        
        # Stop the async task if it exists
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
            
        # Stop the thread if it exists
        if self._monitor_thread:
            self._thread_stop_event.set()
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
            
        logger.debug("Heartbeat monitor stopped")
    
    def received_heartbeat(self):
        """Update the last heartbeat time"""
        self._last_heartbeat_time = time.time()
        logger.debug("Heartbeat received")
        
    def is_running(self) -> bool:
        """Check if the heartbeat monitor is running"""
        return self._running
        
    def time_since_last_heartbeat(self) -> float:
        """Get the time since the last heartbeat in seconds"""
        if self._last_heartbeat_time == 0:
            return 0.0
        return time.time() - self._last_heartbeat_time