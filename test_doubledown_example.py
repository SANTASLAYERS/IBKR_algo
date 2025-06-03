#!/usr/bin/env python3
"""
DoubleDown Rule Example and Test
================================

This file demonstrates how the new DoubleDown rule works in the trading system.
The DoubleDown rule places limit orders at configurable levels below the entry price
to allow for averaging down on positions when the price moves against you.

Example Usage:
    python test_doubledown_example.py
"""

import asyncio
import logging
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from src.rule.linked_order_actions import LinkedDoubleDownAction, LinkedOrderManager
from src.order import OrderType

# Configure logging for demo
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_doubledown_calculation():
    """Demonstrate how the DoubleDown rule calculates prices and quantities."""
    
    print("🎯 DoubleDown Rule Demonstration")
    print("=" * 50)
    
    # Example scenario: CVNA trade
    symbol = "CVNA"
    current_price = 60.12
    atr_value = 0.47
    stop_multiplier = 6.0  # Same as main strategy
    original_quantity = 166  # From $10,000 allocation
    
    print(f"\n📊 Trade Setup:")
    print(f"Symbol: {symbol}")
    print(f"Current Price: ${current_price:.2f}")
    print(f"ATR Value: ${atr_value:.4f}")
    print(f"Original Position: {original_quantity} shares")
    
    # Calculate stop distance
    stop_distance = atr_value * stop_multiplier
    stop_price = current_price - stop_distance
    
    print(f"\n🛡️ Risk Management:")
    print(f"Stop Distance: ${stop_distance:.2f} (ATR {atr_value:.4f} × {stop_multiplier})")
    print(f"Stop Loss Price: ${stop_price:.2f}")
    
    # Test different double down configurations
    configs = [
        {"distance_multiplier": 0.5, "quantity_multiplier": 1.0, "name": "Standard (50% to stop, 1x size)"},
        {"distance_multiplier": 0.3, "quantity_multiplier": 0.5, "name": "Conservative (30% to stop, 0.5x size)"},
        {"distance_multiplier": 0.7, "quantity_multiplier": 1.5, "name": "Aggressive (70% to stop, 1.5x size)"},
    ]
    
    print(f"\n📈 DoubleDown Configurations:")
    print("-" * 80)
    
    for config in configs:
        distance_mult = config["distance_multiplier"]
        quantity_mult = config["quantity_multiplier"]
        
        # Calculate double down price
        dd_distance = stop_distance * distance_mult
        dd_price = current_price - dd_distance
        dd_quantity = int(original_quantity * quantity_mult)
        
        print(f"\n{config['name']}:")
        print(f"  Distance from entry: ${dd_distance:.2f} ({distance_mult:.1%} of stop distance)")
        print(f"  Limit Order Price: ${dd_price:.2f}")
        print(f"  Quantity: {dd_quantity} shares")
        print(f"  Dollar Amount: ${dd_quantity * dd_price:,.0f}")
        
        # Calculate new average if filled
        total_shares = original_quantity + dd_quantity
        total_cost = (original_quantity * current_price) + (dd_quantity * dd_price)
        new_avg = total_cost / total_shares
        
        print(f"  If Filled - New Average: ${new_avg:.2f} ({total_shares} shares)")
        print(f"  Breakeven Needs: ${new_avg:.2f} (vs original ${current_price:.2f})")


async def demo_doubledown_action():
    """Demonstrate the LinkedDoubleDownAction in action."""
    
    print(f"\n\n🔧 LinkedDoubleDownAction Demo")
    print("=" * 50)
    
    # Mock context setup
    mock_order_manager = AsyncMock()
    mock_price_service = AsyncMock()
    mock_indicator_manager = AsyncMock()
    
    # Setup mock returns
    mock_price_service.get_price.return_value = 60.12
    mock_indicator_manager.get_atr.return_value = 0.47
    
    # Mock order creation
    mock_order = MagicMock()
    mock_order.order_id = "DD001"
    mock_order_manager.create_order.return_value = mock_order
    
    # Create context
    context = {
        "order_manager": mock_order_manager,
        "price_service": mock_price_service,
        "indicator_manager": mock_indicator_manager,
        "CVNA": {
            "status": "active",
            "side": "BUY",
            "quantity": 166,
            "allocation": 10000
        }
    }
    
    # Mock existing orders
    LinkedOrderManager.get_linked_orders = MagicMock()
    LinkedOrderManager.get_linked_orders.side_effect = lambda ctx, symbol, order_type: {
        "doubledown1": [],  # No existing double down
        "main": ["MAIN001"],  # Has main order
        "stop": ["STOP001"],  # Has stop order
    }.get(order_type, [])
    
    LinkedOrderManager.add_order = MagicMock()
    
    # Create and execute double down action
    dd_action = LinkedDoubleDownAction(
        symbol="CVNA",
        distance_to_stop_multiplier=0.5,  # 50% to stop
        quantity_multiplier=1.0,          # Same size
        level_name="doubledown1"
    )
    
    print(f"\n📋 Executing DoubleDown Action:")
    print(f"Symbol: CVNA")
    print(f"Distance to Stop: 50% (0.5)")
    print(f"Quantity Multiplier: 100% (1.0)")
    print(f"Level Name: doubledown1")
    
    # Execute the action
    result = await dd_action.execute(context)
    
    if result:
        print(f"\n✅ DoubleDown Order Created Successfully!")
        
        # Verify the order creation call
        order_call = mock_order_manager.create_order.call_args
        if order_call:
            kwargs = order_call.kwargs
            print(f"📞 Order Manager Called With:")
            print(f"  Symbol: {kwargs.get('symbol')}")
            print(f"  Quantity: {kwargs.get('quantity')}")
            print(f"  Order Type: {kwargs.get('order_type')}")
            print(f"  Limit Price: ${kwargs.get('limit_price'):.2f}")
            
        # Verify linking
        link_call = LinkedOrderManager.add_order.call_args
        if link_call:
            args = link_call.args
            print(f"🔗 Order Linked With:")
            print(f"  Symbol: {args[1]}")
            print(f"  Order ID: {args[2]}")
            print(f"  Type: {args[3]}")
            print(f"  Side: {args[4]}")
    else:
        print(f"\n❌ DoubleDown Order Failed!")


async def demo_multiple_doubledown_levels():
    """Demonstrate how to set up multiple double down levels."""
    
    print(f"\n\n🎯 Multiple DoubleDown Levels Example")
    print("=" * 50)
    
    symbol = "SOXL"
    current_price = 45.30
    atr_value = 1.20
    stop_distance = atr_value * 6.0  # $7.20
    original_quantity = 220  # $10K allocation
    
    print(f"📊 Base Trade: {symbol} @ ${current_price:.2f}")
    print(f"Original Position: {original_quantity} shares")
    print(f"Stop Distance: ${stop_distance:.2f}")
    
    # Multiple double down levels
    levels = [
        {"name": "doubledown1", "distance": 0.25, "quantity": 0.5, "desc": "Light add at 25% to stop"},
        {"name": "doubledown2", "distance": 0.50, "quantity": 1.0, "desc": "Full add at 50% to stop"},
        {"name": "doubledown3", "distance": 0.75, "quantity": 1.5, "desc": "Heavy add at 75% to stop"},
    ]
    
    print(f"\n📈 Multiple DoubleDown Configuration:")
    print("-" * 70)
    
    total_potential_shares = original_quantity
    total_potential_cost = original_quantity * current_price
    
    for level in levels:
        dd_distance = stop_distance * level["distance"]
        dd_price = current_price - dd_distance
        dd_quantity = int(original_quantity * level["quantity"])
        
        print(f"\n{level['name'].upper()}: {level['desc']}")
        print(f"  Trigger Price: ${dd_price:.2f} ({level['distance']:.0%} to stop)")
        print(f"  Quantity: {dd_quantity} shares ({level['quantity']:.1f}x original)")
        print(f"  Dollar Risk: ${dd_quantity * dd_price:,.0f}")
        
        # Add to potential totals
        total_potential_shares += dd_quantity
        total_potential_cost += dd_quantity * dd_price
    
    print(f"\n💰 If All Levels Fill:")
    print(f"Total Shares: {total_potential_shares}")
    print(f"Total Cost: ${total_potential_cost:,.0f}")
    print(f"Average Price: ${total_potential_cost / total_potential_shares:.2f}")
    print(f"Max Risk: ${current_price - (current_price - stop_distance):.2f} per share")


def show_rule_integration_example():
    """Show how to integrate multiple double down rules in main_trading_app.py"""
    
    print(f"\n\n🔧 Integration Example for main_trading_app.py")
    print("=" * 60)
    
    example_code = '''
# Example: Adding multiple double down levels to a strategy

# Level 1: Conservative double down
doubledown1_action = LinkedDoubleDownAction(
    symbol=ticker,
    distance_to_stop_multiplier=0.25,  # 25% to stop
    quantity_multiplier=0.5,           # Half size
    level_name="doubledown1"
)

doubledown1_rule = Rule(
    rule_id=f"{ticker.lower()}_doubledown1_rule",
    name=f"{ticker} Double Down Level 1",
    description=f"Conservative double down at 25% to stop",
    condition=buy_condition,  # Same as main buy
    action=doubledown1_action,
    priority=95,
    cooldown_seconds=strategy["cooldown_minutes"] * 60
)

# Level 2: Standard double down  
doubledown2_action = LinkedDoubleDownAction(
    symbol=ticker,
    distance_to_stop_multiplier=0.5,   # 50% to stop
    quantity_multiplier=1.0,           # Same size
    level_name="doubledown2"
)

doubledown2_rule = Rule(
    rule_id=f"{ticker.lower()}_doubledown2_rule",
    name=f"{ticker} Double Down Level 2", 
    description=f"Standard double down at 50% to stop",
    condition=buy_condition,
    action=doubledown2_action,
    priority=94,
    cooldown_seconds=strategy["cooldown_minutes"] * 60
)

# Register both levels
self.rule_engine.register_rule(doubledown1_rule)
self.rule_engine.register_rule(doubledown2_rule)
'''
    
    print(example_code)


async def main():
    """Run all demonstrations."""
    await demo_doubledown_calculation()
    await demo_doubledown_action()
    await demo_multiple_doubledown_levels()
    show_rule_integration_example()
    
    print(f"\n\n🎉 DoubleDown Rule Demo Complete!")
    print("=" * 50)
    print("The DoubleDown rule is now ready for use in your trading system.")
    print("You can configure multiple levels with different distances and quantities.")
    print("Each level will place a limit order when a BUY signal is received.")


if __name__ == "__main__":
    asyncio.run(main()) 