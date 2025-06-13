# TWS Order Management Tests

This directory contains integration tests for the TWS (Trader Workstation) order management system. These tests were created to diagnose and fix various issues with order submission, tracking, and management.

## Overview

These tests interact with a live TWS connection and create real orders. They helped identify and fix critical issues in the trading system's order management capabilities.

## Test Files

### Core Tests (Main Problem Solvers)

#### 1. `test_trade_tracker_duplicate_prevention.py`
**Purpose:** Tests the TradeTracker's ability to prevent duplicate trades on the same symbol while allowing position reversals.

**What it tests:**
- Duplicate trade prevention for same symbol/same side
- Allowing trades when no active position exists
- Allowing position reversal (BUY → SELL or SELL → BUY)
- TradeTracker state management

**Problems it helped solve:**
- System was creating multiple positions for the same symbol when receiving multiple signals
- Needed a way to track active trades persistently across rule executions

**Key outcomes:**
- Created the `TradeTracker` singleton class
- Integrated duplicate checking into `LinkedCreateOrderAction`

#### 2. `test_multi_symbol_trades.py`
**Purpose:** Verifies that TradeTracker allows simultaneous trades on different symbols.

**What it tests:**
- Creating trades on multiple symbols (SLV, SPY, GLD) simultaneously
- Confirming TradeTracker is symbol-specific, not global
- Duplicate prevention still works per symbol

**Problems it helped solve:**
- Concern that TradeTracker might block all trades globally
- Needed to confirm multi-symbol trading still works

**Key outcomes:**
- Confirmed TradeTracker tracks per-symbol, not globally
- System can handle multiple simultaneous positions on different symbols

#### 3. `test_order_management.py`
**Purpose:** Tests comprehensive order management including cancellation and updates after double down fills.

**What it tests:**
- Creating positions with all protective orders (stop, target, double down)
- Context tracking of order relationships
- Simulating double down fills and subsequent updates
- Bulk order cancellation

**Problems it helped solve:**
- Understanding how context tracks order relationships
- Verifying order cancellation mechanisms
- Testing double down fill handling

**Key outcomes:**
- Confirmed context properly tracks all order IDs and relationships
- Verified `LinkedCloseAllAction` can cancel all related orders
- Demonstrated importance of context for complex order management

#### 4. `test_context_order_tracking.py`
**Purpose:** Demonstrates the value of context-based order tracking vs manual management.

**What it tests:**
- Context creation and order tracking
- Manual vs automatic order cancellation
- Benefits of context-based management

**Problems it helped solve:**
- Question of whether context was still needed with TradeTracker
- Understanding the complementary roles of context and TradeTracker

**Key outcomes:**
- Context is essential for order relationship tracking
- TradeTracker and context serve different, complementary purposes

#### 5. `test_context_capabilities.py`
**Purpose:** Comprehensive demonstration of context-based order management capabilities.

**What it tests:**
- Creating multiple related orders with one action
- Canceling all orders with one command
- How double down fills trigger automatic updates
- Benefits of context vs manual order management

**Problems it helped solve:**
- Final validation that context is essential
- Clear demonstration of all context capabilities
- Documentation of the complete order lifecycle

**Key outcomes:**
- Context enables sophisticated order management
- One command can manage complex order relationships
- Position parameters (ATR multipliers) are preserved

### Supporting Tests

#### 6. `test_live_slv_buy_flow.py`
**Purpose:** Initial test that discovered order submission issues.
- First test to identify stop/target/double down orders weren't submitting
- Led to the `auto_submit=True` fix

#### 7. `test_simple_order.py`
**Purpose:** Basic order submission test.
- Tests simple market order submission
- Verifies basic TWS connection and order flow

#### 8. `test_duplicate_signals.py`
**Purpose:** Tests handling of duplicate trading signals.
- Verifies system behavior with rapid duplicate signals
- Tests signal filtering and order management

#### 9. `test_simple_context_check.py`
**Purpose:** Simple context verification test.
- Basic context creation and tracking
- Verifies context persistence during trades

#### 10. `test_context_after_trade.py`
**Purpose:** Tests context state after trade completion.
- Verifies context cleanup after trades
- Tests state management lifecycle

#### 11. `test_doubledown_fill_update.py`
**Purpose:** Tests stop/target updates after double down fills.
- Verifies automatic order updates
- Tests position averaging calculations

#### 12. `test_auto_doubledown.py`
**Purpose:** Tests automatic double down order creation.
- Verifies double down price calculations
- Tests ATR-based positioning

#### 13. `test_doubledown_example.py`
**Purpose:** Example implementation of double down logic.
- Reference implementation
- Testing double down scenarios

## Common Issues Fixed

### Order Submission Issues
- **Problem:** Stop, target, and double down orders weren't being submitted to TWS
- **Fix:** Added `auto_submit=True` parameter to all order creation calls

### Order ID Management
- **Problem:** `get_next_order_id()` was returning the same ID without incrementing
- **Fix:** Modified to increment `_next_order_id` after returning it
- **Fix:** Added proactive request for 50 order IDs on connection

### Thread Safety
- **Problem:** "No running event loop" error from TWS callbacks
- **Fix:** Changed from `asyncio.create_task()` to `asyncio.run_coroutine_threadsafe()`

### ATR Calculation Issues
- **Problem:** Missing timezone in IB API calls, date parsing issues
- **Fix:** Added " UTC" suffix to date strings
- **Fix:** Added Unix timestamp string parsing
- **Fix:** Added error codes 2174, 2176 to non-critical list

### IB Order Object Issues
- **Problem:** "Error 321: Cannot set VOL attribute on non-VOL order"
- **Fix:** Only set necessary fields in IB Order object
- **Fix:** Disabled deprecated attributes (`eTradeOnly`, `firmQuoteOnly`)

## Running the Tests

**Prerequisites:**
1. TWS or IB Gateway must be running
2. API connections must be enabled in TWS
3. Environment variables must be set (see main README)

**Warning:** These tests create REAL orders in TWS. Run them only in a paper trading account or when you're prepared for real trades.

**To run a test:**
```bash
cd tests/tws_order_management
python test_name.py
```

Each test will prompt for confirmation before creating orders.

## Test Logs

Each test creates a corresponding `.log` file with detailed execution information. These logs are useful for debugging and understanding the order flow.

## Architecture Insights

These tests revealed the complementary nature of two key components:

1. **TradeTracker**: Simple, persistent trade state tracking
   - Prevents duplicate entries
   - Tracks active trades per symbol
   - Lightweight yes/no decisions

2. **Context**: Rich order relationship management
   - Tracks all order IDs and their relationships
   - Preserves position parameters
   - Enables bulk operations
   - Handles complex order lifecycle

Together, they provide a robust order management system that prevents duplicates while maintaining sophisticated order relationships and enabling complex operations like automatic stop/target updates after scale-ins.

## Legacy flow (DEPRECATED) 