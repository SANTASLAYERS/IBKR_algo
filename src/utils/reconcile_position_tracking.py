"""
Reconciliation script for comparing TradeTracker and PositionManager.

This script compares the two position tracking systems to ensure they're in sync
during the dual-write migration period.
"""

import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple

from src.trade_tracker import TradeTracker
from src.position.position_manager import PositionManager

logger = logging.getLogger(__name__)


class PositionReconciler:
    """Reconciles positions between TradeTracker and PositionManager."""
    
    def __init__(self):
        self.trade_tracker = TradeTracker()
        self.position_manager = PositionManager()
        self.discrepancies: List[Dict] = []
    
    def reconcile(self) -> Dict[str, any]:
        """
        Compare TradeTracker and PositionManager states.
        
        Returns:
            Dict containing reconciliation results and any discrepancies
        """
        self.discrepancies = []
        timestamp = datetime.now()
        
        # Get active positions from both systems
        tt_active = self.trade_tracker.get_all_active_trades()
        pm_active = self.position_manager.get_all_active_positions()
        
        # Compare active positions
        tt_symbols = set(tt_active.keys())
        pm_symbols = set(pm_active.keys())
        
        # Check for positions only in TradeTracker
        only_in_tt = tt_symbols - pm_symbols
        for symbol in only_in_tt:
            self.discrepancies.append({
                "type": "MISSING_IN_PM",
                "symbol": symbol,
                "details": f"Position exists in TradeTracker but not in PositionManager",
                "tt_data": {
                    "side": tt_active[symbol].side,
                    "entry_time": tt_active[symbol].entry_time.isoformat()
                }
            })
        
        # Check for positions only in PositionManager
        only_in_pm = pm_symbols - tt_symbols
        for symbol in only_in_pm:
            self.discrepancies.append({
                "type": "MISSING_IN_TT",
                "symbol": symbol,
                "details": f"Position exists in PositionManager but not in TradeTracker",
                "pm_data": {
                    "side": pm_active[symbol].side,
                    "entry_time": pm_active[symbol].entry_time.isoformat(),
                    "orders": len(pm_active[symbol].get_all_orders())
                }
            })
        
        # Check positions in both for consistency
        common_symbols = tt_symbols & pm_symbols
        for symbol in common_symbols:
            tt_trade = tt_active[symbol]
            pm_position = pm_active[symbol]
            
            # Check side matches
            if tt_trade.side != pm_position.side:
                self.discrepancies.append({
                    "type": "SIDE_MISMATCH",
                    "symbol": symbol,
                    "details": f"Side mismatch: TT={tt_trade.side}, PM={pm_position.side}"
                })
            
            # Check order tracking (PM should have orders, TT doesn't track them)
            if len(pm_position.get_all_orders()) == 0:
                self.discrepancies.append({
                    "type": "NO_ORDERS",
                    "symbol": symbol,
                    "details": f"PositionManager has no orders tracked for {symbol}"
                })
        
        # Generate summary
        summary = {
            "timestamp": timestamp.isoformat(),
            "trade_tracker": {
                "active_positions": len(tt_active),
                "symbols": list(tt_symbols)
            },
            "position_manager": {
                "active_positions": len(pm_active),
                "symbols": list(pm_symbols),
                "total_orders_tracked": sum(len(p.get_all_orders()) for p in pm_active.values())
            },
            "discrepancies": {
                "count": len(self.discrepancies),
                "details": self.discrepancies
            },
            "status": "IN_SYNC" if len(self.discrepancies) == 0 else "DISCREPANCIES_FOUND"
        }
        
        return summary
    
    def generate_alert_message(self, summary: Dict) -> str:
        """Generate a human-readable alert message from reconciliation summary."""
        lines = [
            "=" * 60,
            "POSITION TRACKING RECONCILIATION REPORT",
            f"Timestamp: {summary['timestamp']}",
            "=" * 60,
            "",
            f"TradeTracker: {summary['trade_tracker']['active_positions']} active positions",
            f"PositionManager: {summary['position_manager']['active_positions']} active positions",
            f"Total orders tracked: {summary['position_manager']['total_orders_tracked']}",
            "",
            f"Status: {summary['status']}",
            ""
        ]
        
        if summary['discrepancies']['count'] > 0:
            lines.append(f"⚠️  Found {summary['discrepancies']['count']} discrepancies:")
            lines.append("")
            
            for disc in summary['discrepancies']['details']:
                lines.append(f"  • {disc['symbol']}: {disc['details']}")
                if 'tt_data' in disc:
                    lines.append(f"    TradeTracker data: {disc['tt_data']}")
                if 'pm_data' in disc:
                    lines.append(f"    PositionManager data: {disc['pm_data']}")
                lines.append("")
        else:
            lines.append("✅ All systems in sync!")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def log_reconciliation(self, summary: Dict):
        """Log reconciliation results."""
        message = self.generate_alert_message(summary)
        
        if summary['status'] == "IN_SYNC":
            logger.info(message)
        else:
            logger.warning(message)
    
    def get_position_details(self, symbol: str) -> Dict:
        """Get detailed comparison for a specific symbol."""
        details = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat()
        }
        
        # TradeTracker info
        tt_trade = self.trade_tracker.get_active_trade(symbol)
        if tt_trade:
            details["trade_tracker"] = {
                "exists": True,
                "side": tt_trade.side,
                "entry_time": tt_trade.entry_time.isoformat(),
                "status": tt_trade.status.value
            }
        else:
            details["trade_tracker"] = {"exists": False}
        
        # PositionManager info
        pm_position = self.position_manager.get_position(symbol)
        if pm_position and pm_position.status.value == "active":
            details["position_manager"] = {
                "exists": True,
                "side": pm_position.side,
                "entry_time": pm_position.entry_time.isoformat(),
                "status": pm_position.status.value,
                "orders": {
                    "main": list(pm_position.main_orders),
                    "stop": list(pm_position.stop_orders),
                    "target": list(pm_position.target_orders),
                    "doubledown": list(pm_position.doubledown_orders),
                    "total": len(pm_position.get_all_orders())
                }
            }
        else:
            details["position_manager"] = {"exists": False}
        
        return details


def run_reconciliation():
    """Run a reconciliation check and log results."""
    reconciler = PositionReconciler()
    summary = reconciler.reconcile()
    reconciler.log_reconciliation(summary)
    return summary


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run reconciliation
    summary = run_reconciliation()
    
    # Print to console as well
    print(PositionReconciler().generate_alert_message(summary)) 