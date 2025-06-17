# Alpaca Position Management

## Overview

The position management system has been updated to work seamlessly with Alpaca Markets. It provides automatic synchronization between Alpaca's position data and the internal position tracking systems.

## Components

### 1. AlpacaPositionSync (`src/position/alpaca_sync.py`)

The main component responsible for synchronizing positions between Alpaca and internal tracking.

**Features:**
- Fetches positions from Alpaca
- Converts Alpaca position format to internal format
- Updates internal position trackers
- Handles discrepancies between Alpaca and internal state
- Provides periodic synchronization

**Key Methods:**
- `sync_positions()` - Performs full position synchronization
- `sync_single_position(symbol)` - Syncs a specific position
- `start_periodic_sync(interval)` - Starts automatic periodic sync
- `stop_periodic_sync()` - Stops periodic sync

### 2. Position Data Flow

```
Alpaca API
    ↓
AlpacaConnection.get_positions()
    ↓
AlpacaPositionSync
    ↓
    ├── PositionTracker (Event-based tracking)
    └── PositionManager (Order-based tracking)
```

### 3. Position Format Conversion

Alpaca positions are converted to internal format:

```python
# Alpaca Position
{
    'symbol': 'AAPL',
    'qty': '100',
    'avg_entry_price': '150.00',
    'market_value': '15500.00',
    'cost_basis': '15000.00',
    'unrealized_pl': '500.00'
}

# Internal Position
{
    'symbol': 'AAPL',
    'quantity': 100.0,
    'entry_price': 150.00,
    'current_price': 155.00,
    'unrealized_pnl': 500.00,
    'status': PositionStatus.OPEN
}
```

## Integration with Main App

The position sync is integrated into the main trading application:

1. **Initialization**: Position tracker and manager are initialized before order manager
2. **Initial Sync**: Performs immediate sync on startup
3. **Periodic Sync**: Runs every 30 seconds by default
4. **Graceful Shutdown**: Stops sync before disconnecting

## Usage Examples

### Manual Position Sync

```python
# Perform manual sync
sync_result = await position_sync.sync_positions()

if sync_result['status'] == 'success':
    print(f"Synced {sync_result['alpaca_positions']} positions")
    if sync_result['discrepancies']:
        print(f"Found {len(sync_result['discrepancies'])} discrepancies")
```

### Single Position Sync

```python
# Sync specific position
pos_data = await position_sync.sync_single_position('AAPL')
if pos_data:
    print(f"AAPL position: {pos_data['qty']} @ ${pos_data['avg_entry_price']}")
```

### Position Summary

```python
# Get position summary
summary = await position_tracker.get_position_summary()
print(f"Total positions: {summary['total_positions']}")
print(f"Total value: ${summary['total_value']}")
print(f"Unrealized P/L: ${summary['total_unrealized_pnl']}")
```

## Discrepancy Handling

The system handles two types of discrepancies:

1. **Missing Internal**: Position exists in Alpaca but not internally
   - Automatically creates internal position
   - Logs the discrepancy

2. **Missing Alpaca**: Position exists internally but not in Alpaca
   - Logs warning
   - Does not automatically close (requires manual review)

## Configuration

Position sync interval can be configured:

```python
# Start with custom interval (seconds)
await position_sync.start_periodic_sync(interval=60)  # Sync every minute
```

## Testing

Run the position sync test:

```bash
python test_alpaca_position_sync.py
```

This will:
1. Connect to Alpaca
2. Fetch current positions
3. Perform synchronization
4. Test periodic sync
5. Display position summary

## Best Practices

1. **Initial Sync**: Always perform initial sync on startup
2. **Periodic Sync**: Use reasonable intervals (30-60 seconds)
3. **Error Handling**: Monitor sync failures in logs
4. **Manual Review**: Review discrepancies before taking action
5. **Position Updates**: Use position tracker for price updates

## Troubleshooting

### Common Issues

1. **Sync Failures**
   - Check Alpaca connection
   - Verify API credentials
   - Check network connectivity

2. **Discrepancies**
   - Review trading logs
   - Check for manual trades
   - Verify order fills

3. **Performance**
   - Adjust sync interval if needed
   - Monitor API rate limits 