#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Alpaca Position Synchronization

This script tests the position synchronization between Alpaca and internal tracking.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alpaca_config import AlpacaConfig
from src.alpaca_connection import AlpacaConnection
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.position.alpaca_sync import AlpacaPositionSync
from src.event.bus import EventBus
from src.logger import get_logger


async def test_position_sync():
    """Test position synchronization with Alpaca."""
    print("\n=== Testing Alpaca Position Synchronization ===\n")
    
    # Setup logging
    logger = get_logger(__name__)
    
    # Initialize components
    config = AlpacaConfig.from_env()
    print(f"Config loaded: {config}")
    print(f"API Key present: {'Yes' if config.api_key else 'No'}")
    print(f"Secret Key present: {'Yes' if config.secret_key else 'No'}")
    
    connection = AlpacaConnection(config)
    event_bus = EventBus()
    position_tracker = PositionTracker(event_bus)
    position_manager = PositionManager()
    
    # Initialize position tracker
    await position_tracker.initialize()
    
    # Create position sync
    position_sync = AlpacaPositionSync(
        connection=connection,
        position_tracker=position_tracker,
        position_manager=position_manager,
        event_bus=event_bus
    )
    
    # Connect to Alpaca
    print("1. Connecting to Alpaca...")
    connected = await connection.connect()
    if not connected:
        print("❌ Failed to connect to Alpaca")
        return
    
    print("✅ Connected to Alpaca\n")
    
    # Get current positions from Alpaca
    print("2. Fetching positions from Alpaca...")
    alpaca_positions = connection.get_positions()
    
    if alpaca_positions:
        print(f"Found {len(alpaca_positions)} positions in Alpaca:")
        for pos in alpaca_positions:
            print(f"  - {pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price}")
            print(f"    Market Value: ${pos.market_value}")
            print(f"    Unrealized P/L: ${pos.unrealized_pl}")
    else:
        print("No positions found in Alpaca account")
    
    # Perform position sync
    print("\n3. Performing position synchronization...")
    sync_result = await position_sync.sync_positions()
    
    print(f"\nSync Status: {sync_result['status']}")
    print(f"Timestamp: {sync_result.get('timestamp', 'N/A')}")
    
    if sync_result['status'] == 'success':
        print(f"Alpaca Positions: {sync_result['alpaca_positions']}")
        print(f"Internal Positions: {sync_result['internal_positions']}")
        
        if sync_result['discrepancies']:
            print(f"\n⚠️  Found {len(sync_result['discrepancies'])} discrepancies:")
            for disc in sync_result['discrepancies']:
                print(f"  - Type: {disc['type']}")
                print(f"    Symbol: {disc['symbol']}")
                if disc['type'] == 'missing_internal':
                    print(f"    Alpaca Qty: {disc['alpaca_qty']}")
                    print(f"    Alpaca Value: ${disc['alpaca_value']}")
                else:
                    print(f"    Internal Qty: {disc.get('internal_qty', 'N/A')}")
        else:
            print("\n✅ All positions are synchronized")
        
        if sync_result['updates']:
            print(f"\nUpdates performed:")
            for update in sync_result['updates']:
                print(f"  - {update}")
    
    # Test single position sync
    if alpaca_positions and len(alpaca_positions) > 0:
        test_symbol = alpaca_positions[0].symbol
        print(f"\n4. Testing single position sync for {test_symbol}...")
        
        single_pos = await position_sync.sync_single_position(test_symbol)
        if single_pos:
            print(f"✅ Successfully synced {test_symbol}:")
            print(f"  Qty: {single_pos['qty']}")
            print(f"  Side: {single_pos['side']}")
            print(f"  Avg Entry: ${single_pos['avg_entry_price']}")
            print(f"  Unrealized P/L: ${single_pos['unrealized_pl']}")
    
    # Test periodic sync
    print("\n5. Testing periodic sync (will run for 10 seconds)...")
    await position_sync.start_periodic_sync(interval=5)
    
    # Wait for a couple of sync cycles
    await asyncio.sleep(10)
    
    await position_sync.stop_periodic_sync()
    print("✅ Periodic sync stopped")
    
    # Check internal positions after sync
    print("\n6. Checking internal position state...")
    internal_positions = await position_tracker.get_all_positions()
    pm_positions = position_manager.get_all_active_positions()
    
    print(f"\nPosition Tracker has {len(internal_positions)} positions:")
    for pos in internal_positions:
        if pos.status.value == 'open':
            print(f"  - {pos.symbol}: {pos.quantity} @ ${pos.entry_price}")
            print(f"    Status: {pos.status.value}")
            print(f"    Unrealized P/L: ${pos.unrealized_pnl}")
    
    print(f"\nPosition Manager has {len(pm_positions)} active positions:")
    for symbol, pos in pm_positions.items():
        print(f"  - {symbol}: {pos.side} {pos.current_quantity}")
        if pos.entry_price:
            print(f"    Entry Price: ${pos.entry_price}")
    
    # Get position summary
    print("\n7. Position Summary:")
    summary = await position_tracker.get_position_summary()
    print(f"Total Positions: {summary['total_positions']}")
    print(f"Total Value: ${summary['total_value']:.2f}")
    print(f"Total Unrealized P/L: ${summary['total_unrealized_pnl']:.2f}")
    print(f"Total Realized P/L: ${summary['total_realized_pnl']:.2f}")
    
    if summary['by_symbol']:
        print("\nBy Symbol:")
        for symbol, data in summary['by_symbol'].items():
            print(f"  {symbol}:")
            print(f"    Count: {data['count']}")
            print(f"    Value: ${data['value']:.2f}")
            print(f"    Unrealized P/L: ${data['unrealized_pnl']:.2f}")
    
    # Disconnect
    print("\n8. Disconnecting...")
    connection.disconnect()
    print("✅ Test completed")


if __name__ == "__main__":
    asyncio.run(test_position_sync()) 