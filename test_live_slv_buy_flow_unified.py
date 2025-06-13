# Create BUY action with automatic stops
buy_action = LinkedCreateOrderAction(
    symbol="SLV",
    quantity=10000,  # $10K allocation
    side="BUY",
    order_type=OrderType.MARKET,
    auto_create_stops=True,
    atr_stop_multiplier=1.5,      # 1.5x ATR for stop loss
    atr_target_multiplier=1.5     # 1.5x ATR for take profit
) 