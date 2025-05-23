#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ibapi.order import Order as IBOrder

# Create a new order
order = IBOrder()

# Print all default attributes and their values
print("Default IBOrder attributes:")
for attr_name in dir(order):
    # Skip internal attributes
    if attr_name.startswith('__'):
        continue
    
    # Skip methods
    if callable(getattr(order, attr_name)):
        continue
    
    # Print attribute and value
    value = getattr(order, attr_name)
    print(f"{attr_name}: {value}")

# Check if eTradeOnly exists
print("\nChecking for eTradeOnly attribute:")
print(f"Has eTradeOnly: {'eTradeOnly' in dir(order)}")
if 'eTradeOnly' in dir(order):
    print(f"eTradeOnly value: {order.eTradeOnly}")