#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import threading
from typing import Dict, Optional

# Global logger registry to prevent duplicate loggers
_LOGGERS: Dict[str, logging.Logger] = {}
_LOGGER_LOCK = threading.RLock()

# Default logging format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_LEVEL = logging.INFO

def get_logger(
    name: str, 
    level: Optional[int] = None, 
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    use_timed_rotating: bool = False
) -> logging.Logger:
    """
    Get or create a logger with the specified name and configuration.
    
    Args:
        name: Logger name
        level: Logging level (if None, uses the module default)
        log_format: Format string for log messages
        log_file: Optional file path to write logs to
        max_bytes: Maximum size in bytes before rotating the log file
        backup_count: Number of backup files to keep
        use_timed_rotating: Use time-based rotation instead of size-based
        
    Returns:
        logging.Logger: Configured logger
    """
    with _LOGGER_LOCK:
        # Check if logger already exists
        if name in _LOGGERS:
            return _LOGGERS[name]
        
        # Create new logger
        logger = logging.getLogger(name)
        
        # Only set up handlers if this is the first time getting this logger
        if not logger.handlers:
            # Set level
            if level is not None:
                logger.setLevel(level)
            else:
                logger.setLevel(DEFAULT_LOG_LEVEL)
            
            # Create formatter
            formatter = logging.Formatter(log_format)
            
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # File handler (if log_file is specified)
            if log_file:
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                
                if use_timed_rotating:
                    file_handler = TimedRotatingFileHandler(
                        log_file, 
                        when='midnight', 
                        interval=1, 
                        backupCount=backup_count
                    )
                else:
                    file_handler = RotatingFileHandler(
                        log_file, 
                        maxBytes=max_bytes, 
                        backupCount=backup_count
                    )
                
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        
        _LOGGERS[name] = logger
        return logger


def configure_root_logger(
    level: int = logging.INFO,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    Configure the root logger.
    
    Args:
        level: Logging level
        log_format: Format string for log messages
        log_file: Optional file path to write logs to
        console: Whether to log to console
        
    Returns:
        logging.Logger: Root logger
    """
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set level
    root_logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def configure_logging_from_config(config) -> None:
    """
    Configure logging from a config object.
    
    Args:
        config: Configuration object with log settings
    """
    # Convert string level to logging constant
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING, 
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    level = level_map.get(config.log_level.upper(), logging.INFO)
    
    # Configure root logger
    configure_root_logger(
        level=level,
        log_format=config.log_format,
        log_file=config.log_file
    )
    
    # Update existing loggers
    with _LOGGER_LOCK:
        for logger in _LOGGERS.values():
            logger.setLevel(level)
            
            # Update handler formatters
            formatter = logging.Formatter(config.log_format)
            for handler in logger.handlers:
                handler.setFormatter(formatter)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter to add context information to log messages.
    """
    
    def __init__(self, logger, extra=None):
        """
        Initialize the logger adapter.
        
        Args:
            logger: Logger to adapt
            extra: Extra context to add to all log messages
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        """
        Process the log message.
        
        Args:
            msg: Log message
            kwargs: Keyword arguments
            
        Returns:
            Tuple: (processed_message, kwargs)
        """
        # Add context info to the message
        context_info = ' '.join([f"[{k}={v}]" for k, v in self.extra.items()])
        if context_info:
            return f"{msg} {context_info}", kwargs
        return msg, kwargs


def get_contextual_logger(name, **context):
    """
    Get a logger that includes context information in each log message.
    
    Args:
        name: Logger name
        context: Key-value pairs to include in log messages
        
    Returns:
        LoggerAdapter: Logger adapter with context
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)