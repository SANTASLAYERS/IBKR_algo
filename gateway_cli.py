#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB Gateway CLI - Command-line tool for IB Gateway connection management.
"""

import argparse
import asyncio
import configparser
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler
from src.logger import configure_root_logger, get_logger
from src.minute_data.manager import MinuteBarManager
from src.minute_data.models import MinuteBarCollection
from src.subscription_manager import SubscriptionManager
from ibapi.contract import Contract, ContractDetails

# Set up logger
logger = get_logger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='IB Gateway CLI')
    
    # Connection settings
    conn_group = parser.add_argument_group('Connection')
    conn_group.add_argument('--host', type=str, default='127.0.0.1', help='Gateway hostname or IP')
    conn_group.add_argument('--port', type=int, help='Gateway port (4001 for live, 4002 for paper)')
    conn_group.add_argument('--client-id', type=int, default=1, help='Client ID')
    conn_group.add_argument('--account-id', type=str, help='IB account ID')
    conn_group.add_argument('--read-only', action='store_true', help='Connect in read-only mode')
    conn_group.add_argument('--gateway-path', type=str, help='Path to IB Gateway installation')
    conn_group.add_argument('--trading-mode', type=str, choices=['paper', 'live'], default='paper', 
                          help='Trading mode (paper or live)')
    
    # Security settings
    sec_group = parser.add_argument_group('Security')
    sec_group.add_argument('--user-id', type=str, help='IB Gateway user ID (username)')
    sec_group.add_argument('--password-file', type=str, help='Path to file containing password')
    
    # Config file
    parser.add_argument('--config', type=str, help='Path to config file')
    
    # Logging settings
    log_group = parser.add_argument_group('Logging')
    log_group.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                         default='INFO', help='Logging level')
    log_group.add_argument('--log-file', type=str, help='Log file path')
    
    # Actions
    action_group = parser.add_argument_group('Actions')
    action_group.add_argument('--check', action='store_true', help='Check Gateway connection')
    action_group.add_argument('--start', action='store_true', help='Start Gateway')
    action_group.add_argument('--stop', action='store_true', help='Stop Gateway')
    action_group.add_argument('--subscribe', type=str, help='Subscribe to market data for symbol')
    action_group.add_argument('--unsubscribe', type=str, help='Unsubscribe from market data for symbol')
    action_group.add_argument('--list-subscriptions', action='store_true', help='List active market data subscriptions')
    action_group.add_argument('--persistent', action='store_true', help='Use persistent subscriptions with auto-reconnect capability')
    action_group.add_argument('--watch', action='store_true', help='Enable continuous monitoring mode for subscriptions')
    action_group.add_argument('--duration', type=int, default=10, help='Duration in seconds for market data subscription (default: 10, 0 for indefinite)')
    action_group.add_argument('--positions', action='store_true', help='Show current positions')
    action_group.add_argument('--account', action='store_true', help='Show account values')
    
    # Add minute data arguments
    add_minute_data_arguments(parser)
    
    # Add subscription arguments
    add_subscription_arguments(parser)
    
    return parser.parse_args()


def add_minute_data_arguments(parser):
    """Add minute data arguments to the parser."""
    minute_group = parser.add_argument_group('Minute Data')
    minute_group.add_argument('--fetch-minutes', type=str, metavar='SYMBOL',
                           help='Fetch historical minute data for symbol')
    minute_group.add_argument('--duration', type=str, default='1 D',
                           help='Duration string (e.g., "1 D", "1 W")')
    minute_group.add_argument('--bar-size', type=str, default='1 min',
                           help='Bar size string (e.g., "1 min", "5 mins")')
    minute_group.add_argument('--end-date', type=str,
                           help='End date for historical data (format: YYYY-MM-DD HH:MM:SS)')
    minute_group.add_argument('--output-format', type=str, choices=['csv', 'json'], default='csv',
                           help='Output format for minute data')
    minute_group.add_argument('--output-file', type=str,
                           help='Output file path (defaults to stdout)')
    minute_group.add_argument('--no-cache', action='store_true',
                           help='Disable cache for minute data')


def add_subscription_arguments(parser):
    """Add market data subscription arguments to the parser."""
    sub_group = parser.add_argument_group('Subscription Options')
    sub_group.add_argument('--sec-type', type=str, default='STK', choices=['STK', 'OPT', 'FUT', 'CASH', 'IND', 'FOP', 'BOND'],
                           help='Security type')
    sub_group.add_argument('--exchange', type=str, default='SMART',
                           help='Exchange (e.g., SMART, NASDAQ, NYSE)')
    sub_group.add_argument('--currency', type=str, default='USD',
                           help='Currency (e.g., USD, EUR, GBP)')
    sub_group.add_argument('--expiry', type=str,
                           help='Expiration date for derivatives (format: YYYYMMDD)')
    sub_group.add_argument('--strike', type=float,
                           help='Strike price for options')
    sub_group.add_argument('--right', type=str, choices=['C', 'P'],
                           help='Option right (C for Call, P for Put)')
    sub_group.add_argument('--local-symbol', type=str,
                           help='Local symbol as an alternative to the above parameters')


def create_contract(args, symbol):
    """
    Create a contract object based on the command-line arguments.
    
    Args:
        args: Command-line arguments
        symbol: Symbol to create contract for
        
    Returns:
        Contract: IBKR Contract object
    """
    contract = Contract()
    contract.symbol = symbol
    
    # Set contract properties from args
    contract.secType = args.sec_type if hasattr(args, 'sec_type') else 'STK'
    contract.exchange = args.exchange if hasattr(args, 'exchange') else 'SMART'
    contract.currency = args.currency if hasattr(args, 'currency') else 'USD'
    
    # For options and futures
    if hasattr(args, 'expiry') and args.expiry:
        contract.lastTradeDateOrContractMonth = args.expiry
        
    # For options
    if contract.secType == 'OPT' or contract.secType == 'FOP':
        if hasattr(args, 'strike') and args.strike:
            contract.strike = args.strike
        
        if hasattr(args, 'right') and args.right:
            contract.right = args.right
            
    # Local symbol overrides other parameters if provided
    if hasattr(args, 'local_symbol') and args.local_symbol:
        contract.localSymbol = args.local_symbol
        
    return contract


def load_config(args):
    """Load configuration from file and command line arguments."""
    config = IBGatewayConfig()
    
    # Load from file if provided
    if args.config and os.path.exists(args.config):
        # Parse config file
        parser = configparser.ConfigParser()
        parser.read(args.config)
        
        # Connection settings
        if 'Connection' in parser:
            conn = parser['Connection']
            config.host = conn.get('host', config.host)
            config.port = conn.getint('port', config.port)
            config.client_id = conn.getint('client_id', config.client_id)
            config.account_id = conn.get('account_id', config.account_id)
            config.read_only = conn.getboolean('read_only', config.read_only)
            config.gateway_path = conn.get('gateway_path', config.gateway_path)
            config.trading_mode = conn.get('trading_mode', config.trading_mode)
        
        # Security settings
        if 'Security' in parser:
            sec = parser['Security']
            config.user_id = sec.get('user_id', config.user_id)
            password_file = sec.get('password_file', None)
            if password_file and os.path.exists(password_file):
                with open(password_file, 'r') as f:
                    config.password = f.read().strip()
        
        # Heartbeat settings
        if 'Heartbeat' in parser:
            hb = parser['Heartbeat']
            config.heartbeat_timeout = hb.getfloat('timeout', config.heartbeat_timeout)
            config.heartbeat_interval = hb.getfloat('interval', config.heartbeat_interval)
        
        # Reconnection settings
        if 'Reconnection' in parser:
            reconnect = parser['Reconnection']
            config.reconnect_delay = reconnect.getfloat('delay', config.reconnect_delay)
            config.max_reconnect_attempts = reconnect.getint('max_attempts', config.max_reconnect_attempts)
        
        # Logging settings
        if 'Logging' in parser:
            log = parser['Logging']
            config.log_level = log.get('level', config.log_level)
            config.log_format = log.get('format', config.log_format)
            config.log_file = log.get('file', config.log_file)
            if config.log_file == 'None':
                config.log_file = None
    
    # Override with command line arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.client_id:
        config.client_id = args.client_id
    if args.account_id:
        config.account_id = args.account_id
    if args.read_only:
        config.read_only = args.read_only
    if args.gateway_path:
        config.gateway_path = args.gateway_path
    if args.trading_mode:
        config.trading_mode = args.trading_mode
    if args.user_id:
        config.user_id = args.user_id
    if args.password_file and os.path.exists(args.password_file):
        with open(args.password_file, 'r') as f:
            config.password = f.read().strip()
    if args.log_level:
        config.log_level = args.log_level
    if args.log_file:
        config.log_file = args.log_file
    
    return config


async def check_gateway(gateway, args):
    """Check Gateway connection."""
    logger.info("Checking Gateway connection...")
    
    # Check if Gateway is running
    is_running = await gateway._is_gateway_running()
    logger.info(f"Gateway running: {is_running}")
    
    if is_running:
        # Try to connect
        logger.info("Attempting to connect...")
        connected = await gateway.connect_async()
        logger.info(f"Connection successful: {connected}")
        
        if connected:
            # Request current time to verify connection
            gateway.reqCurrentTime()
            await asyncio.sleep(1)  # Give time for response
            
            # Disconnect
            gateway.disconnect()
            logger.info("Disconnected from Gateway")
    
    return is_running


async def start_gateway(gateway, args):
    """Start Gateway process."""
    logger.info("Starting Gateway...")
    
    # Start Gateway
    started = await gateway.start_gateway()
    
    if started:
        logger.info("Gateway started successfully")
    else:
        logger.error("Failed to start Gateway")
    
    return started


async def stop_gateway(gateway, args):
    """Stop Gateway process."""
    logger.info("Stopping Gateway...")
    
    # Connect first to ensure clean shutdown
    connected = await gateway.connect_async()
    
    if connected:
        # Disconnect and stop Gateway
        await gateway.disconnect_gateway()
        logger.info("Gateway stopped successfully")
        return True
    else:
        # Try to stop Gateway directly
        stopped = await gateway.stop_gateway()
        if stopped:
            logger.info("Gateway stopped successfully")
        else:
            logger.error("Failed to stop Gateway")
        return stopped


async def subscribe_market_data(gateway, args):
    """Subscribe to market data for a symbol."""
    if not args.subscribe:
        logger.error("No symbol provided")
        return False

    symbol = args.subscribe.upper()
    logger.info(f"Subscribing to market data for {symbol}...")

    # Check if in continuous mode
    watch_mode = args.watch
    duration = args.duration if hasattr(args, 'duration') else 10
    
    # Log security type info
    sec_type = args.sec_type if hasattr(args, 'sec_type') else 'STK'
    
    if watch_mode:
        logger.info("Continuous monitoring mode enabled")
        if duration == 0:
            logger.info("Running indefinitely. Press Ctrl+C to stop.")
        else:
            logger.info(f"Running for {duration} seconds")
    
    logger.info(f"Security type: {sec_type}")

    # Connect to Gateway
    connected = await gateway.connect_async()

    if not connected:
        logger.error("Failed to connect to Gateway")
        return False

    try:
        # Create contract using helper function
        contract = create_contract(args, symbol)
        
        # Log contract details
        contract_desc = f"{contract.symbol} {contract.secType}"
        if hasattr(contract, 'lastTradeDateOrContractMonth') and contract.lastTradeDateOrContractMonth:
            contract_desc += f" {contract.lastTradeDateOrContractMonth}"
        if hasattr(contract, 'strike') and contract.strike:
            contract_desc += f" {contract.strike}"
        if hasattr(contract, 'right') and contract.right:
            contract_desc += f" {contract.right}"
        logger.info(f"Contract: {contract_desc} [{contract.exchange}:{contract.currency}]")

        # Create callback to print market data
        def market_data_callback(data):
            # Format as JSON for nicer output
            formatted_data = {k: v for k, v in data.items() if k != 'contract'}

            # Add timestamp for continuous mode
            if watch_mode:
                formatted_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            print(json.dumps(formatted_data, indent=2))
            
            # If there's an error, log it
            if 'error' in formatted_data:
                logger.error(f"Market data error: {formatted_data['error']}")

        # Subscribe to market data with optional tick list
        generic_tick_list = ""
        # Add more tick types for options
        if sec_type == 'OPT' or sec_type == 'FOP':
            # Include implied volatility, delta, gamma, etc.
            generic_tick_list = "106,100,101,104,106,291,292,293,294,295"
        
        req_id = gateway.subscribe_market_data(
            contract, 
            generic_tick_list=generic_tick_list,
            callback=market_data_callback
        )

        if req_id > 0:
            logger.info(f"Subscribed to {symbol} (ID: {req_id})")

            try:
                # In continuous mode, we wait until interrupted or duration reached
                if watch_mode:
                    if duration > 0:
                        # Wait for specified duration
                        await asyncio.sleep(duration)
                    else:
                        # Run indefinitely until interrupted
                        while True:
                            await asyncio.sleep(1)
                            # Request heartbeat every 30 seconds to keep connection alive
                            if int(time.time()) % 30 == 0:
                                gateway.reqHeartbeat()
                else:
                    # Regular mode - just wait for the specified duration
                    await asyncio.sleep(duration)
            except asyncio.CancelledError:
                logger.info("Subscription cancelled by user")

            # Unsubscribe
            gateway.unsubscribe_market_data(req_id)
            logger.info(f"Unsubscribed from {symbol}")

            # Disconnect
            gateway.disconnect()
            logger.info("Disconnected from Gateway")

            return True
        else:
            logger.error("Failed to subscribe to market data")
            return False

    except Exception as e:
        logger.error(f"Error subscribing to market data: {str(e)}")
        return False
    finally:
        # Ensure we disconnect
        if gateway.is_connected():
            gateway.disconnect()


async def subscribe_persistent_market_data(gateway, subscription_manager, args):
    """Subscribe to market data with persistent reconnection handling."""
    if not args.subscribe:
        logger.error("No symbol provided")
        return False
    
    symbol = args.subscribe.upper()
    logger.info(f"Creating persistent subscription for {symbol}...")
    
    # Check if in continuous mode
    watch_mode = args.watch
    duration = args.duration if hasattr(args, 'duration') else 10
    
    # Log security type info
    sec_type = args.sec_type if hasattr(args, 'sec_type') else 'STK'
    
    if watch_mode:
        logger.info("Continuous monitoring mode enabled")
        if duration == 0:
            logger.info("Running indefinitely. Press Ctrl+C to stop.")
        else:
            logger.info(f"Running for {duration} seconds")
    
    logger.info(f"Security type: {sec_type}")
    logger.info("Auto-reconnect enabled: Subscription will be maintained across connection losses")
    
    # Connect to Gateway
    connected = await gateway.connect_async()
    
    if not connected:
        logger.error("Failed to connect to Gateway")
        return False
    
    try:
        # Create contract using helper function
        contract = create_contract(args, symbol)
        
        # Log contract details
        contract_desc = f"{contract.symbol} {contract.secType}"
        if hasattr(contract, 'lastTradeDateOrContractMonth') and contract.lastTradeDateOrContractMonth:
            contract_desc += f" {contract.lastTradeDateOrContractMonth}"
        if hasattr(contract, 'strike') and contract.strike:
            contract_desc += f" {contract.strike}"
        if hasattr(contract, 'right') and contract.right:
            contract_desc += f" {contract.right}"
        logger.info(f"Contract: {contract_desc} [{contract.exchange}:{contract.currency}]")
        
        # Create callback to print market data
        def market_data_callback(data):
            # Format as JSON for nicer output
            formatted_data = {k: v for k, v in data.items() if k != 'contract'}
            
            # Add timestamp for continuous mode
            if watch_mode:
                formatted_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            print(json.dumps(formatted_data, indent=2))
            
            # If there's an error, log it but don't print it (subscription manager will handle it)
            if 'error' in formatted_data:
                logger.error(f"Market data error: {formatted_data['error']}")
        
        # Subscribe to market data with optional tick list
        generic_tick_list = ""
        # Add more tick types for options
        if sec_type == 'OPT' or sec_type == 'FOP':
            # Include implied volatility, delta, gamma, etc.
            generic_tick_list = "106,100,101,104,106,291,292,293,294,295"
        
        # Use subscription manager to create persistent subscription
        req_id = subscription_manager.subscribe(
            contract=contract,
            callback=market_data_callback,
            generic_tick_list=generic_tick_list,
            snapshot=False  # We want streaming data
        )
        
        if req_id > 0:
            logger.info(f"Created persistent subscription for {symbol} (ID: {req_id})")
            
            try:
                # In continuous mode, we wait until interrupted
                if watch_mode:
                    if duration > 0:
                        # Wait for specified duration
                        await asyncio.sleep(duration)
                    else:
                        # Run indefinitely until interrupted
                        while True:
                            await asyncio.sleep(1)
                            # Request heartbeat every 30 seconds to keep connection alive
                            if int(time.time()) % 30 == 0:
                                gateway.reqHeartbeat()
                else:
                    # Regular mode - just wait for the specified duration
                    await asyncio.sleep(duration)
            except asyncio.CancelledError:
                logger.info("Monitoring cancelled by user")
            
            # If not watch mode, unsubscribe
            if not watch_mode:
                # Get symbol key for unsubscribing
                symbol_key = subscription_manager._create_symbol_key(contract)
                subscription_manager.unsubscribe(symbol_key)
                logger.info(f"Unsubscribed from {symbol}")
                
                # Disconnect
                gateway.disconnect()
                logger.info("Disconnected from Gateway")
            
            return True
        else:
            logger.error("Failed to create subscription")
            return False
            
    except Exception as e:
        logger.error(f"Error in persistent subscription: {str(e)}")
        return False
    finally:
        # Only disconnect if not in watch mode
        if not watch_mode and gateway.is_connected():
            gateway.disconnect()


async def unsubscribe_market_data(gateway, subscription_manager, args):
    """Unsubscribe from market data for a symbol."""
    if not args.unsubscribe:
        logger.error("No symbol provided for unsubscription")
        return False
    
    symbol = args.unsubscribe.upper()
    logger.info(f"Unsubscribing from market data for {symbol}...")
    
    # Create contract to get symbol key
    contract = create_contract(args, symbol)
    symbol_key = subscription_manager._create_symbol_key(contract)
    
    # Unsubscribe
    success = subscription_manager.unsubscribe(symbol_key)
    
    if success:
        logger.info(f"Successfully unsubscribed from {symbol}")
    else:
        logger.warning(f"No active subscription found for {symbol}")
    
    return success

async def list_subscriptions(gateway, subscription_manager, args):
    """List all active market data subscriptions."""
    subscription_count = subscription_manager.get_subscription_count()
    
    if subscription_count == 0:
        logger.info("No active subscriptions found")
        print("No active subscriptions")
        return True
    
    # Get subscription symbols
    symbols = subscription_manager.get_subscription_symbols()
    
    logger.info(f"Found {subscription_count} active subscriptions")
    print(f"\nActive Market Data Subscriptions ({subscription_count}):")
    print("-" * 50)
    
    # Print each subscription
    for symbol_key in symbols:
        subscription = subscription_manager.active_subscriptions[symbol_key]
        contract = subscription["contract"]
        active_status = "Active" if subscription["active"] else "Inactive/Pending"
        
        # Format nicely for display
        symbol_info = f"{contract.symbol} {contract.secType}"
        if hasattr(contract, 'lastTradeDateOrContractMonth') and contract.lastTradeDateOrContractMonth:
            symbol_info += f" {contract.lastTradeDateOrContractMonth}"
        if hasattr(contract, 'strike') and contract.strike:
            symbol_info += f" {contract.strike}"
        if hasattr(contract, 'right') and contract.right:
            symbol_info += f" {contract.right}"
        
        print(f"{symbol_info:<30} | {active_status:<15} | ID: {subscription['req_id']}")
    
    return True


async def show_positions(gateway, args):
    """Show current positions."""
    logger.info("Retrieving positions...")
    
    # Connect to Gateway
    connected = await gateway.connect_async()
    
    if not connected:
        logger.error("Failed to connect to Gateway")
        return False
    
    try:
        # Request account updates
        account_id = args.account_id or gateway.account_id
        if account_id:
            gateway.reqAccountUpdates(True, account_id)
        else:
            gateway.reqAccountUpdates(True, "")
        
        # Wait for data
        await asyncio.sleep(3)
        
        # Get positions
        positions = gateway.get_positions()
        
        # Print positions
        print("\nCurrent Positions:")
        print("-----------------")
        
        if not positions:
            print("No positions found.")
        else:
            for account, acct_positions in positions.items():
                print(f"\nAccount: {account}")
                print("Symbol       | Quantity | Market Price | Market Value | Avg Cost | Unrealized P&L")
                print("-------------|----------|--------------|--------------|----------|--------------")
                
                if not acct_positions:
                    print("No positions for this account.")
                    continue
                
                for key, pos in acct_positions.items():
                    contract = pos['contract']
                    symbol = f"{contract.symbol} {contract.secType}"
                    print(f"{symbol:<13}| {pos['position']:<9.2f}| {pos['market_price']:<13.2f}| "
                          f"{pos['market_value']:<13.2f}| {pos['average_cost']:<9.2f}| {pos['unrealized_pnl']:<14.2f}")
        
        # Cancel account updates
        if account_id:
            gateway.reqAccountUpdates(False, account_id)
        else:
            gateway.reqAccountUpdates(False, "")
            
        # Disconnect
        gateway.disconnect()
        logger.info("Disconnected from Gateway")
        
        return True
        
    except Exception as e:
        logger.error(f"Error retrieving positions: {str(e)}")
        return False
    finally:
        # Ensure we disconnect
        if gateway.is_connected():
            gateway.disconnect()


async def show_account(gateway, args):
    """Show account values."""
    logger.info("Retrieving account information...")
    
    # Connect to Gateway
    connected = await gateway.connect_async()
    
    if not connected:
        logger.error("Failed to connect to Gateway")
        return False
    
    try:
        # Request account updates
        account_id = args.account_id or gateway.account_id
        if account_id:
            gateway.reqAccountUpdates(True, account_id)
        else:
            gateway.reqAccountUpdates(True, "")
        
        # Wait for data
        await asyncio.sleep(3)
        
        # Get account values
        account_values = gateway.get_account_values()
        
        # Print account information
        print("\nAccount Information:")
        print("-------------------")
        
        if not account_values:
            print("No account information found.")
        else:
            for account, values in account_values.items():
                print(f"\nAccount: {account}")
                print("Key                 | Value")
                print("--------------------|----------------------")
                
                if not values:
                    print("No values for this account.")
                    continue
                
                # Print key account metrics
                important_keys = [
                    "NetLiquidation_USD", "CashBalance_USD", "AvailableFunds_USD",
                    "BuyingPower_USD", "EquityWithLoanValue_USD", "UnrealizedPnL_USD",
                    "RealizedPnL_USD", "ExcessLiquidity_USD", "FullInitMarginReq_USD",
                    "FullMaintMarginReq_USD"
                ]
                
                # Print important keys first
                for key in important_keys:
                    if key in values:
                        print(f"{key:<20}| {values[key]}")
                
                # Print any remaining keys, sorted
                remaining_keys = sorted([k for k in values.keys() if k not in important_keys])
                for key in remaining_keys:
                    print(f"{key:<20}| {values[key]}")
        
        # Cancel account updates
        if account_id:
            gateway.reqAccountUpdates(False, account_id)
        else:
            gateway.reqAccountUpdates(False, "")
            
        # Disconnect
        gateway.disconnect()
        logger.info("Disconnected from Gateway")
        
        return True
        
    except Exception as e:
        logger.error(f"Error retrieving account information: {str(e)}")
        return False
    finally:
        # Ensure we disconnect
        if gateway.is_connected():
            gateway.disconnect()


async def fetch_minute_data(gateway, args):
    """Fetch historical minute data."""
    logger.info(f"Fetching minute data for {args.symbol}...")
    
    # Connect to Gateway
    connected = await gateway.connect_async()
    
    if not connected:
        logger.error("Failed to connect to Gateway")
        return False
    
    try:
        # Create contract
        contract = Contract()
        contract.symbol = args.symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Parse end date if provided
        end_date = None
        if args.end_date:
            try:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d %H:%M:%S")
                end_date = end_date.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error(f"Invalid end date format: {args.end_date}")
                return False
        
        # Get the minute bar manager
        manager = gateway.minute_bar_manager
        
        # Fetch minute bars
        bars = await manager.fetch_minute_bars(
            contract=contract,
            end_date=end_date,
            duration=args.duration,
            bar_size=args.bar_size,
            use_cache=not args.no_cache
        )
        
        logger.info(f"Retrieved {len(bars)} minute bars for {args.symbol}")
        
        # Output the data
        if args.output_format == 'csv':
            output = bars.to_csv()
        else:  # json
            output = bars.to_json()
        
        # Write to file or stdout
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            logger.info(f"Wrote output to {args.output_file}")
        else:
            print(output)
        
        # Disconnect
        gateway.disconnect()
        logger.info("Disconnected from Gateway")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fetching minute data: {str(e)}")
        sys.stderr.write(f"Error: {str(e)}\n")
        return False
    finally:
        # Ensure we disconnect
        if gateway.is_connected():
            gateway.disconnect()


async def main(args=None):
    """Main entry point."""
    # Parse command line arguments if not provided
    if args is None:
        args = parse_args()
    
    # Load configuration
    config = load_config(args)
    
    # Configure logging
    log_level = getattr(logging, config.log_level.upper())
    configure_root_logger(level=log_level, log_file=config.log_file)
    
    logger.info(f"IB Gateway CLI v1.0.0")
    logger.info(f"Using configuration: host={config.host}, port={config.port}, "
               f"client_id={config.client_id}, trading_mode={config.trading_mode}")
    
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create Gateway connection
    gateway = IBGateway(config, error_handler)
    
    # Create subscription manager
    subscription_manager = SubscriptionManager(gateway)
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(gateway, subscription_manager, loop)))
    
    # Execute requested action
    try:
        if args.check:
            await check_gateway(gateway, args)
        elif args.start:
            await start_gateway(gateway, args)
        elif args.stop:
            await stop_gateway(gateway, args)
        elif args.subscribe:
            if args.persistent:
                await subscribe_persistent_market_data(gateway, subscription_manager, args)
            else:
                await subscribe_market_data(gateway, args)
        elif args.unsubscribe:
            await unsubscribe_market_data(gateway, subscription_manager, args)
        elif args.list_subscriptions:
            await list_subscriptions(gateway, subscription_manager, args)
        elif args.positions:
            await show_positions(gateway, args)
        elif args.account:
            await show_account(gateway, args)
        elif hasattr(args, 'fetch_minutes') and args.fetch_minutes:
            args.symbol = args.fetch_minutes  # Set symbol for fetch_minute_data
            await fetch_minute_data(gateway, args)
        else:
            # Default action: check Gateway connection
            await check_gateway(gateway, args)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        # Clean up persistent subscriptions
        if hasattr(subscription_manager, 'unsubscribe_all'):
            subscription_manager.unsubscribe_all()
        
        # Clean up gateway connection
        if gateway.is_connected():
            gateway.disconnect()


async def shutdown(gateway, subscription_manager, loop):
    """Shutdown the asyncio event loop gracefully."""
    logger.info("Shutdown signal received - gracefully terminating")
    
    # Unsubscribe from all persistent subscriptions first
    if hasattr(subscription_manager, 'unsubscribe_all'):
        logger.info("Cleaning up persistent subscriptions")
        subscription_manager.unsubscribe_all()
    
    # Disconnect from Gateway
    if gateway.is_connected():
        try:
            # Cancel any remaining active subscriptions
            for req_id in list(gateway._market_data.keys()):
                try:
                    gateway.unsubscribe_market_data(req_id)
                    logger.info(f"Unsubscribed from request ID: {req_id}")
                except Exception as e:
                    logger.error(f"Error unsubscribing from {req_id}: {str(e)}")
                    
            gateway.disconnect()
            logger.info("Disconnected from Gateway")
        except Exception as e:
            logger.error(f"Error during disconnection: {str(e)}")
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    logger.debug(f"Cancelling {len(tasks)} pending tasks")
    
    for task in tasks:
        task.cancel()
    
    if tasks:
        # Wait for tasks to acknowledge cancellation
        await asyncio.gather(*tasks, return_exceptions=True)
    
    loop.stop()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())