#!/usr/bin/env python3
"""
Rule Listing Utility
====================

This script lists all rules in your trading system and shows their configuration.

Usage:
    python list_all_rules.py
"""

import asyncio
import logging
from typing import Dict, List
from datetime import datetime

# Import all necessary components
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.rule.engine import RuleEngine
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from main_trading_app import TradingApplication

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RuleLister:
    """Utility to list and analyze all rules in the trading system."""
    
    def __init__(self):
        self.app = TradingApplication()
    
    async def list_rules_from_app(self):
        """Initialize the app and show all rules it creates."""
        print("🔍 ANALYZING TRADING SYSTEM RULES")
        print("=" * 50)
        
        try:
            # Initialize the application
            await self.app.initialize()
            
            # Setup strategies (this creates all the rules)
            self.app.setup_strategies()
            
            # Get all rules from the rule engine
            all_rules = self.app.rule_engine.get_all_rules()
            
            print(f"\n📋 TOTAL RULES REGISTERED: {len(all_rules)}")
            print("=" * 50)
            
            # Group rules by type
            buy_rules = []
            sell_rules = []
            scalein_rules = []
            other_rules = []
            
            for rule in all_rules:
                if "buy_rule" in rule.rule_id:
                    buy_rules.append(rule)
                elif "sell_rule" in rule.rule_id:
                    sell_rules.append(rule)
                elif "scalein_rule" in rule.rule_id:
                    scalein_rules.append(rule)
                else:
                    other_rules.append(rule)
            
            # Display rules by category
            self._display_rule_category("🟢 BUY RULES", buy_rules)
            self._display_rule_category("🔄 SCALE-IN RULES", scalein_rules)
            self._display_rule_category("🔴 SELL RULES", sell_rules)
            self._display_rule_category("⚙️ OTHER RULES", other_rules)
            
            # Show summary
            self._display_summary(all_rules)
            
        except Exception as e:
            logger.error(f"Error listing rules: {e}")
        finally:
            await self.app.stop_trading()
    
    def _display_rule_category(self, category_name: str, rules: List):
        """Display rules in a specific category."""
        if not rules:
            return
            
        print(f"\n{category_name}")
        print("-" * 40)
        
        for rule in sorted(rules, key=lambda r: r.rule_id):
            print(f"\n📌 Rule ID: {rule.rule_id}")
            print(f"   Name: {rule.name}")
            print(f"   Description: {rule.description}")
            print(f"   Priority: {rule.priority}")
            print(f"   Enabled: {'✅' if rule.enabled else '❌'}")
            print(f"   Cooldown: {rule.cooldown_seconds}s")
            
            # Show condition details
            if hasattr(rule.condition, 'field_conditions'):
                print(f"   Triggers on: {self._format_condition(rule.condition)}")
            
            # Show action details
            print(f"   Action: {self._format_action(rule.action)}")
    
    def _format_condition(self, condition) -> str:
        """Format condition details for display."""
        if hasattr(condition, 'field_conditions'):
            conditions = []
            for field, value in condition.field_conditions.items():
                if field == "symbol":
                    conditions.append(f"Symbol={value}")
                elif field == "signal":
                    conditions.append(f"Signal={value}")
                elif field == "confidence":
                    if callable(value):
                        conditions.append("Confidence>=threshold")
                    else:
                        conditions.append(f"Confidence={value}")
                else:
                    conditions.append(f"{field}={value}")
            return ", ".join(conditions)
        return str(type(condition).__name__)
    
    def _format_action(self, action) -> str:
        """Format action details for display."""
        action_type = type(action).__name__
        
        if hasattr(action, 'symbol') and hasattr(action, 'quantity'):
            return f"{action_type}(symbol={action.symbol}, quantity={action.quantity})"
        elif hasattr(action, 'reason'):
            return f"{action_type}(reason='{action.reason}')"
        else:
            return action_type
    
    def _display_summary(self, all_rules: List):
        """Display a summary of all rules."""
        print(f"\n📊 RULE SUMMARY")
        print("=" * 50)
        
        # Count by type
        buy_count = sum(1 for r in all_rules if "buy_rule" in r.rule_id)
        sell_count = sum(1 for r in all_rules if "sell_rule" in r.rule_id)
        scalein_count = sum(1 for r in all_rules if "scalein_rule" in r.rule_id)
        other_count = len(all_rules) - buy_count - sell_count - scalein_count
        
        print(f"🟢 Buy Rules: {buy_count}")
        print(f"🔄 Scale-in Rules: {scalein_count}")
        print(f"🔴 Sell Rules: {sell_count}")
        print(f"⚙️ Other Rules: {other_count}")
        print(f"📋 Total Rules: {len(all_rules)}")
        
        # Count enabled/disabled
        enabled_count = sum(1 for r in all_rules if r.enabled)
        disabled_count = len(all_rules) - enabled_count
        
        print(f"\n✅ Enabled: {enabled_count}")
        print(f"❌ Disabled: {disabled_count}")
        
        # Show priority distribution
        priorities = [r.priority for r in all_rules]
        print(f"\n🎯 Priority Range: {min(priorities)} - {max(priorities)}")
        
        # Show tickers covered
        tickers = set()
        for rule in all_rules:
            if hasattr(rule.condition, 'field_conditions'):
                symbol = rule.condition.field_conditions.get('symbol')
                if symbol:
                    tickers.add(symbol)
        
        print(f"📈 Tickers Covered: {', '.join(sorted(tickers))}")

def show_static_rule_configuration():
    """Show the static rule configuration from the main app."""
    print("\n🔧 STATIC RULE CONFIGURATION")
    print("=" * 50)
    
    # This is the configuration from main_trading_app.py
    strategies = [
        {
            "ticker": "AAPL",
            "confidence_threshold": 0.80,
            "quantity": 100,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.08,
            "cooldown_minutes": 5
        },
        {
            "ticker": "MSFT", 
            "confidence_threshold": 0.85,
            "quantity": 50,
            "stop_loss_pct": 0.025,
            "take_profit_pct": 0.10,
            "cooldown_minutes": 10
        },
        {
            "ticker": "TSLA",
            "confidence_threshold": 0.90,
            "quantity": 25,
            "stop_loss_pct": 0.04,
            "take_profit_pct": 0.12,
            "cooldown_minutes": 15
        },
        {
            "ticker": "NVDA",
            "confidence_threshold": 0.85,
            "quantity": 30,
            "stop_loss_pct": 0.035,
            "take_profit_pct": 0.09,
            "cooldown_minutes": 8
        }
    ]
    
    print("\n📊 STRATEGY PARAMETERS:")
    print("-" * 40)
    
    for strategy in strategies:
        ticker = strategy["ticker"]
        print(f"\n🎯 {ticker}:")
        print(f"   📈 Initial Buy: {strategy['confidence_threshold']:.0%} confidence → {strategy['quantity']} shares")
        print(f"   🔄 Scale-in: {strategy['confidence_threshold'] + 0.05:.0%} confidence → +{strategy['quantity']//2} shares")
        print(f"   🛑 Stop Loss: {strategy['stop_loss_pct']:.1%}")
        print(f"   🎯 Take Profit: {strategy['take_profit_pct']:.1%}")
        print(f"   ⏰ Cooldown: {strategy['cooldown_minutes']} minutes")
    
    print(f"\n📅 END-OF-DAY RULE:")
    print(f"   ⏰ Time: 3:45 PM - 3:55 PM")
    print(f"   📅 Days: Monday - Friday")
    print(f"   🎯 Action: Close all positions")

def show_rule_file_locations():
    """Show where rules are defined in the codebase."""
    print("\n📁 RULE FILE LOCATIONS")
    print("=" * 50)
    
    locations = [
        {
            "file": "main_trading_app.py",
            "lines": "145-180",
            "description": "BUY rules - Create initial positions based on prediction signals"
        },
        {
            "file": "main_trading_app.py", 
            "lines": "181-270",
            "description": "SCALE-IN rules - Add to existing profitable positions"
        },
        {
            "file": "main_trading_app.py",
            "lines": "301-325",
            "description": "SELL rules - Create short positions or close longs"
        },
        {
            "file": "main_trading_app.py",
            "lines": "339-365",
            "description": "END-OF-DAY rule - Close all positions before market close"
        },
        {
            "file": "src/rule/engine.py",
            "lines": "All",
            "description": "Rule Engine - Manages rule execution and evaluation"
        },
        {
            "file": "src/rule/condition.py",
            "lines": "All", 
            "description": "Condition classes - Define when rules should trigger"
        },
        {
            "file": "src/rule/action.py",
            "lines": "All",
            "description": "Action classes - Define what rules should do"
        }
    ]
    
    for location in locations:
        print(f"\n📄 {location['file']} (lines {location['lines']})")
        print(f"   📝 {location['description']}")

async def main():
    """Main entry point."""
    print("🚀 TRADING SYSTEM RULE ANALYZER")
    print("=" * 50)
    print(f"⏰ Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show static configuration
    show_static_rule_configuration()
    
    # Show file locations
    show_rule_file_locations()
    
    # Analyze live rules
    lister = RuleLister()
    await lister.list_rules_from_app()
    
    print(f"\n✅ ANALYSIS COMPLETE!")
    print(f"💡 To modify rules, edit the 'strategies' list in main_trading_app.py")
    print(f"🔧 To add new rule types, edit the '_create_strategy_rules' method")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Analysis stopped by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}") 