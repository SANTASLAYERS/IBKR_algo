"""
Alpaca Position Synchronization

This module provides synchronization between Alpaca positions and the internal
position tracking system.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.alpaca_connection import AlpacaConnection
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager
from src.event.bus import EventBus
from src.event.position import PositionUpdateEvent, PositionStatus

logger = logging.getLogger(__name__)


class AlpacaPositionSync:
    """
    Synchronizes positions between Alpaca and internal tracking systems.
    
    This class handles:
    1. Fetching positions from Alpaca
    2. Converting to internal format
    3. Updating position trackers
    4. Reconciling discrepancies
    """
    
    def __init__(self, 
                 connection: AlpacaConnection,
                 position_tracker: PositionTracker,
                 position_manager: PositionManager,
                 event_bus: EventBus):
        """
        Initialize the position synchronizer.
        
        Args:
            connection: Alpaca connection instance
            position_tracker: Internal position tracker
            position_manager: Position manager for order tracking
            event_bus: Event bus for position events
        """
        self.connection = connection
        self.position_tracker = position_tracker
        self.position_manager = position_manager
        self.event_bus = event_bus
        
        # Sync state
        self._last_sync: Optional[datetime] = None
        self._sync_interval = 30  # seconds
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("AlpacaPositionSync initialized")
    
    async def start_periodic_sync(self, interval: int = 30):
        """
        Start periodic position synchronization.
        
        Args:
            interval: Sync interval in seconds
        """
        if self._running:
            logger.warning("Position sync already running")
            return
        
        self._sync_interval = interval
        self._running = True
        self._sync_task = asyncio.create_task(self._periodic_sync_loop())
        logger.info(f"Started periodic position sync (interval: {interval}s)")
    
    async def stop_periodic_sync(self):
        """Stop periodic position synchronization."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped periodic position sync")
    
    async def sync_positions(self) -> Dict[str, Any]:
        """
        Perform a full position synchronization.
        
        Returns:
            Dict containing sync results and any discrepancies
        """
        logger.info("Starting position synchronization with Alpaca")
        
        try:
            # Get positions from Alpaca
            alpaca_positions = self.connection.get_positions()
            if alpaca_positions is None:
                logger.error("Failed to fetch positions from Alpaca")
                return {"status": "error", "message": "Failed to fetch positions"}
            
            # Get internal positions
            internal_positions = await self.position_tracker.get_all_positions()
            pm_positions = self.position_manager.get_all_active_positions()
            
            # Convert Alpaca positions to internal format
            alpaca_by_symbol = {}
            for pos in alpaca_positions:
                alpaca_by_symbol[pos.symbol] = {
                    'symbol': pos.symbol,
                    'qty': float(pos.qty),
                    'side': 'long' if float(pos.qty) > 0 else 'short',
                    'avg_entry_price': float(pos.avg_entry_price),
                    'market_value': float(pos.market_value),
                    'cost_basis': float(pos.cost_basis),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'current_price': float(pos.current_price) if hasattr(pos, 'current_price') else None
                }
            
            # Reconcile positions
            discrepancies = []
            updates = []
            
            # Check Alpaca positions against internal
            for symbol, alpaca_pos in alpaca_by_symbol.items():
                # Find in position tracker
                tracker_positions = [p for p in internal_positions if p.symbol == symbol and p.status == PositionStatus.OPEN]
                
                if not tracker_positions:
                    # Position exists in Alpaca but not internally
                    discrepancies.append({
                        'type': 'missing_internal',
                        'symbol': symbol,
                        'alpaca_qty': alpaca_pos['qty'],
                        'alpaca_value': alpaca_pos['market_value']
                    })
                    
                    # Create position in tracker
                    await self._create_position_from_alpaca(alpaca_pos)
                    updates.append(f"Created position for {symbol}")
                else:
                    # Update existing position
                    for pos in tracker_positions:
                        if alpaca_pos['current_price']:
                            await self.position_tracker.update_position_price(
                                pos.position_id, 
                                alpaca_pos['current_price']
                            )
                            updates.append(f"Updated price for {symbol}")
            
            # Check internal positions against Alpaca
            for pos in internal_positions:
                if pos.status == PositionStatus.OPEN and pos.symbol not in alpaca_by_symbol:
                    # Position exists internally but not in Alpaca
                    discrepancies.append({
                        'type': 'missing_alpaca',
                        'symbol': pos.symbol,
                        'internal_qty': pos.quantity,
                        'position_id': pos.position_id
                    })
                    
                    # Consider closing the internal position
                    logger.warning(f"Position {pos.symbol} exists internally but not in Alpaca")
            
            # Update sync timestamp
            self._last_sync = datetime.now()
            
            result = {
                'status': 'success',
                'timestamp': self._last_sync,
                'alpaca_positions': len(alpaca_positions),
                'internal_positions': len([p for p in internal_positions if p.status == PositionStatus.OPEN]),
                'discrepancies': discrepancies,
                'updates': updates
            }
            
            if discrepancies:
                logger.warning(f"Position sync found {len(discrepancies)} discrepancies")
            else:
                logger.info("Position sync completed successfully - all positions match")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during position sync: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now()
            }
    
    async def _create_position_from_alpaca(self, alpaca_pos: Dict[str, Any]):
        """
        Create an internal position from Alpaca position data.
        
        Args:
            alpaca_pos: Alpaca position data
        """
        try:
            symbol = alpaca_pos['symbol']
            quantity = alpaca_pos['qty']
            entry_price = alpaca_pos['avg_entry_price']
            
            # Create position in tracker
            position = await self.position_tracker.create_stock_position(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                strategy="alpaca_sync",
                metadata={
                    'source': 'alpaca_sync',
                    'sync_time': datetime.now().isoformat(),
                    'cost_basis': alpaca_pos['cost_basis'],
                    'unrealized_pl': alpaca_pos['unrealized_pl']
                }
            )
            
            # Also update position manager if needed
            if not self.position_manager.has_active_position(symbol):
                pm_position = self.position_manager.open_position(
                    symbol=symbol,
                    side='BUY' if quantity > 0 else 'SELL'
                )
                pm_position.entry_price = entry_price
                pm_position.current_quantity = abs(quantity)
                pm_position.total_quantity = abs(quantity)
            
            logger.info(f"Created position for {symbol} from Alpaca sync")
            
        except Exception as e:
            logger.error(f"Error creating position from Alpaca data: {e}")
    
    async def _periodic_sync_loop(self):
        """Periodic sync loop."""
        while self._running:
            try:
                await asyncio.sleep(self._sync_interval)
                if self.connection.is_connected():
                    await self.sync_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
    
    async def sync_single_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Sync a single position by symbol.
        
        Args:
            symbol: Symbol to sync
            
        Returns:
            Position data if found
        """
        try:
            alpaca_pos = self.connection.get_position(symbol)
            if not alpaca_pos:
                return None
            
            pos_data = {
                'symbol': alpaca_pos.symbol,
                'qty': float(alpaca_pos.qty),
                'side': 'long' if float(alpaca_pos.qty) > 0 else 'short',
                'avg_entry_price': float(alpaca_pos.avg_entry_price),
                'market_value': float(alpaca_pos.market_value),
                'cost_basis': float(alpaca_pos.cost_basis),
                'unrealized_pl': float(alpaca_pos.unrealized_pl),
                'current_price': float(alpaca_pos.current_price) if hasattr(alpaca_pos, 'current_price') else None
            }
            
            # Update internal tracking
            positions = await self.position_tracker.get_positions_for_symbol(symbol)
            for pos in positions:
                if pos.status == PositionStatus.OPEN and pos_data['current_price']:
                    await self.position_tracker.update_position_price(
                        pos.position_id,
                        pos_data['current_price']
                    )
            
            return pos_data
            
        except Exception as e:
            logger.error(f"Error syncing position for {symbol}: {e}")
            return None
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last sync timestamp."""
        return self._last_sync 