#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from .logger import get_logger

logger = get_logger(__name__)

@dataclass
class Config:
    """
    Configuration class for IBKR connection and behavior settings.
    """
    # Connection settings
    host: str = "127.0.0.1"
    port: int = 7497  # 7497 for TWS, 4002 for Gateway in paper trading, 4001 for Gateway in live trading
    client_id: int = 1
    
    # Heartbeat settings
    heartbeat_timeout: float = 10.0  # Seconds until connection is considered lost
    heartbeat_interval: float = 5.0  # Seconds between heartbeat checks
    
    # Reconnection settings
    reconnect_delay: float = 1.0  # Base delay in seconds before reconnection attempts
    max_reconnect_attempts: int = 5  # Maximum number of reconnection attempts
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None  # If None, logs to console only
    
    # Timeouts
    request_timeout: float = 30.0  # Seconds to wait for a request to complete
    
    # Account settings
    account_ids: List[str] = field(default_factory=list)  # List of account IDs to use
    
    # Custom settings
    custom_settings: Dict[str, str] = field(default_factory=dict)  # Custom settings for extensions
    
    @classmethod
    def from_file(cls, config_file: str) -> 'Config':
        """
        Load configuration from a file.
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            Config: Configuration object
        """
        if not os.path.exists(config_file):
            logger.warning(f"Configuration file not found: {config_file}")
            return cls()
            
        config = configparser.ConfigParser()
        try:
            config.read(config_file)
            return cls.from_configparser(config)
        except Exception as e:
            logger.error(f"Error loading configuration file: {str(e)}")
            return cls()
    
    @classmethod
    def from_configparser(cls, config: configparser.ConfigParser) -> 'Config':
        """
        Load configuration from a ConfigParser object.
        
        Args:
            config: ConfigParser object
            
        Returns:
            Config: Configuration object
        """
        conf = cls()
        
        # Connection settings
        if 'Connection' in config:
            conn_section = config['Connection']
            conf.host = conn_section.get('host', conf.host)
            conf.port = conn_section.getint('port', conf.port)
            conf.client_id = conn_section.getint('client_id', conf.client_id)
        
        # Heartbeat settings
        if 'Heartbeat' in config:
            hb_section = config['Heartbeat']
            conf.heartbeat_timeout = hb_section.getfloat('timeout', conf.heartbeat_timeout)
            conf.heartbeat_interval = hb_section.getfloat('interval', conf.heartbeat_interval)
        
        # Reconnection settings
        if 'Reconnection' in config:
            reconn_section = config['Reconnection']
            conf.reconnect_delay = reconn_section.getfloat('delay', conf.reconnect_delay)
            conf.max_reconnect_attempts = reconn_section.getint('max_attempts', conf.max_reconnect_attempts)
        
        # Logging settings
        if 'Logging' in config:
            log_section = config['Logging']
            conf.log_level = log_section.get('level', conf.log_level)
            conf.log_format = log_section.get('format', conf.log_format)
            conf.log_file = log_section.get('file', conf.log_file)
            if conf.log_file == 'None':
                conf.log_file = None
        
        # Timeouts
        if 'Timeouts' in config:
            timeout_section = config['Timeouts']
            conf.request_timeout = timeout_section.getfloat('request', conf.request_timeout)
        
        # Account settings
        if 'Account' in config:
            account_section = config['Account']
            account_ids = account_section.get('account_ids', '')
            if account_ids:
                conf.account_ids = [aid.strip() for aid in account_ids.split(',')]
        
        # Custom settings
        for section in config.sections():
            if section not in ['Connection', 'Heartbeat', 'Reconnection', 'Logging', 'Timeouts', 'Account']:
                for key, value in config[section].items():
                    conf.custom_settings[f"{section}.{key}"] = value
        
        return conf
    
    def to_file(self, config_file: str) -> bool:
        """
        Save configuration to a file.
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        config = configparser.ConfigParser()
        
        # Connection settings
        config['Connection'] = {
            'host': self.host,
            'port': str(self.port),
            'client_id': str(self.client_id),
        }
        
        # Heartbeat settings
        config['Heartbeat'] = {
            'timeout': str(self.heartbeat_timeout),
            'interval': str(self.heartbeat_interval),
        }
        
        # Reconnection settings
        config['Reconnection'] = {
            'delay': str(self.reconnect_delay),
            'max_attempts': str(self.max_reconnect_attempts),
        }
        
        # Logging settings
        config['Logging'] = {
            'level': self.log_level,
            'format': self.log_format,
            'file': str(self.log_file) if self.log_file else 'None',
        }
        
        # Timeouts
        config['Timeouts'] = {
            'request': str(self.request_timeout),
        }
        
        # Account settings
        config['Account'] = {
            'account_ids': ','.join(self.account_ids),
        }
        
        # Custom settings
        custom_sections = {}
        for key, value in self.custom_settings.items():
            if '.' in key:
                section, option = key.split('.', 1)
                if section not in custom_sections:
                    custom_sections[section] = {}
                custom_sections[section][option] = value
        
        for section, options in custom_sections.items():
            config[section] = options
        
        try:
            os.makedirs(os.path.dirname(os.path.abspath(config_file)), exist_ok=True)
            with open(config_file, 'w') as f:
                config.write(f)
            return True
        except Exception as e:
            logger.error(f"Error saving configuration file: {str(e)}")
            return False
    
    def get_custom_setting(self, key: str, default: str = None) -> str:
        """
        Get a custom setting.
        
        Args:
            key: Setting key in format "section.option"
            default: Default value if setting is not found
            
        Returns:
            str: Setting value
        """
        return self.custom_settings.get(key, default)
    
    def set_custom_setting(self, key: str, value: str):
        """
        Set a custom setting.
        
        Args:
            key: Setting key in format "section.option"
            value: Setting value
        """
        self.custom_settings[key] = value
    
    def __str__(self) -> str:
        """String representation of the configuration"""
        return (
            f"Config(host={self.host}, port={self.port}, client_id={self.client_id}, "
            f"heartbeat_timeout={self.heartbeat_timeout}, reconnect_attempts={self.max_reconnect_attempts})"
        )


def create_default_config(config_file: str = None) -> Config:
    """
    Create a default configuration and optionally save it to a file.
    
    Args:
        config_file: Optional path to save the configuration
        
    Returns:
        Config: Default configuration
    """
    config = Config()
    
    if config_file:
        config.to_file(config_file)
    
    return config