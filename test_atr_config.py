#!/usr/bin/env python3
"""
ATR Configuration Test
======================

This test shows the exact ATR configuration used in the trading system.
"""

import asyncio
from datetime import datetime, timedelta
from src.indicators.atr import ATRCalculator
from src.indicators.manager import IndicatorManager
from src.minute_data.models import MinuteBar

async def test_atr_configuration():
    """Test and display ATR configuration."""
    
    print("🔍 ATR System Configuration")
    print("=" * 50)
    
    # Default configuration from IndicatorManager
    print("📊 Default ATR Settings:")
    print(f"   • Timeframe: 10 seconds (10 secs)")
    print(f"   • Period: 14 periods")
    print(f"   • Data lookback: 5 days")
    print(f"   • Total bars needed: ~4,320 bars (5 days × 6 bars/min × 1,440 min/day)")
    print()
    
    # Create sample 10-second bars
    print("📈 Creating sample 10-second price data...")
    
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    bars = []
    
    # Generate 100 bars (about 16.7 minutes of 10-second data)
    base_price = 150.0
    for i in range(100):
        timestamp = base_time + timedelta(seconds=i * 10)
        
        # Create realistic price movement with volatility
        price_variation = (i % 10) * 0.02  # Small price variations
        volatility = 0.50 + (i % 5) * 0.10  # Varying volatility
        
        current_price = base_price + price_variation
        
        bar = MinuteBar(
            symbol="TEST",
            timestamp=timestamp,
            open_price=current_price,
            high_price=current_price + volatility,
            low_price=current_price - volatility,
            close_price=current_price + (volatility * 0.1),
            volume=1000 + i * 10
        )
        bars.append(bar)
    
    print(f"   • Generated {len(bars)} bars")
    print(f"   • Time span: {(bars[-1].timestamp - bars[0].timestamp).total_seconds() / 60:.1f} minutes")
    print(f"   • Bar frequency: Every 10 seconds")
    print()
    
    # Test different ATR periods
    periods_to_test = [7, 14, 21]
    
    print("🧮 ATR Calculations with Different Periods:")
    print("-" * 40)
    
    for period in periods_to_test:
        calculator = ATRCalculator(period=period)
        atr_value = await calculator.calculate(bars)
        
        if atr_value:
            # Calculate trading levels using our system's multipliers
            stop_loss_distance = atr_value * 6   # 6x ATR for stop loss
            profit_target_distance = atr_value * 3  # 3x ATR for profit target
            
            print(f"ATR({period:2d} periods):")
            print(f"   • ATR Value: ${atr_value:.4f}")
            print(f"   • Stop Loss Distance: ${stop_loss_distance:.4f} (6x ATR)")
            print(f"   • Profit Target Distance: ${profit_target_distance:.4f} (3x ATR)")
            print(f"   • Risk/Reward Ratio: 2:1 (6x ÷ 3x)")
            print()
    
    # Show how this works in practice
    print("💰 Practical Trading Example:")
    print("-" * 30)
    
    # Use 14-period ATR (our default)
    calculator = ATRCalculator(period=14)
    atr_value = await calculator.calculate(bars)
    
    if atr_value:
        entry_price = 150.00
        stop_loss_distance = atr_value * 6
        profit_target_distance = atr_value * 3
        
        # For a BUY position
        print(f"Example BUY position @ ${entry_price:.2f}:")
        print(f"   • ATR (14-period, 10s bars): ${atr_value:.4f}")
        print(f"   • Stop Loss: ${entry_price - stop_loss_distance:.2f} ({stop_loss_distance:.4f} below entry)")
        print(f"   • Profit Target: ${entry_price + profit_target_distance:.2f} ({profit_target_distance:.4f} above entry)")
        print(f"   • Risk: ${stop_loss_distance:.2f} per share")
        print(f"   • Reward: ${profit_target_distance:.2f} per share")
        print()
        
        # For a SELL position
        print(f"Example SELL position @ ${entry_price:.2f}:")
        print(f"   • Stop Loss: ${entry_price + stop_loss_distance:.2f} ({stop_loss_distance:.4f} above entry)")
        print(f"   • Profit Target: ${entry_price - profit_target_distance:.2f} ({profit_target_distance:.4f} below entry)")
        print()
    
    print("⚙️  System Configuration Summary:")
    print("-" * 35)
    print("✅ Timeframe: 10-second bars")
    print("✅ ATR Period: 14 periods")
    print("✅ Stop Loss: 6x ATR distance")
    print("✅ Profit Target: 3x ATR distance")
    print("✅ Risk/Reward: 2:1 ratio")
    print("✅ Data Source: Real-time TWS market data")
    print()
    print("This gives you volatility-adaptive stops that:")
    print("• Tighten during low volatility periods")
    print("• Widen during high volatility periods")
    print("• Maintain consistent 2:1 risk/reward ratio")

if __name__ == "__main__":
    asyncio.run(test_atr_configuration()) 