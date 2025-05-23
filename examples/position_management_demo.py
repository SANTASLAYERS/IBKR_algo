#!/usr/bin/env python3
"""
Position Management Demo

This script demonstrates the basic usage of the event system and position management
components of the IBKR Trading Framework.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.event.bus import EventBus
from src.event.market import PriceEvent
from src.event.api import PredictionSignalEvent
from src.event.position import PositionOpenEvent, PositionUpdateEvent, PositionCloseEvent
from src.position.tracker import PositionTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("position_demo")


class PositionDemoHandler:
    """Demo handler for position management."""
    
    def __init__(self, event_bus, position_tracker):
        """Initialize the demo handler."""
        self.event_bus = event_bus
        self.position_tracker = position_tracker
        
        # Track processed prediction IDs to avoid duplicates
        self.processed_predictions = set()
    
    async def initialize(self):
        """Set up event subscriptions."""
        # Subscribe to market data events
        await self.event_bus.subscribe(PriceEvent, self.handle_price_event)
        
        # Subscribe to prediction signals
        await self.event_bus.subscribe(PredictionSignalEvent, self.handle_prediction_event)
        
        # Subscribe to position events for logging
        await self.event_bus.subscribe(PositionOpenEvent, self.log_position_event)
        await self.event_bus.subscribe(PositionUpdateEvent, self.log_position_event)
        await self.event_bus.subscribe(PositionCloseEvent, self.log_position_event)
        
        logger.info("PositionDemoHandler initialized and subscribed to events")
    
    async def handle_price_event(self, event):
        """Handle price update events."""
        logger.debug(f"Received price update for {event.symbol}: {event.price}")
        
        # Update all positions for this symbol
        await self.position_tracker.update_all_positions_price(event.symbol, event.price)
        
        # Check for stop loss/take profit triggers
        positions = await self.position_tracker.get_positions_for_symbol(event.symbol)
        for position in positions:
            if position.status.value != "open":
                continue
                
            # Check stop loss
            if position.stop_loss is not None:
                if (position.is_long and event.price <= position.stop_loss) or \
                   (not position.is_long and event.price >= position.stop_loss):
                    logger.info(f"Stop loss triggered for {position}")
                    await self.position_tracker.close_position(
                        position.position_id,
                        event.price,
                        "Stop loss triggered"
                    )
                    continue
            
            # Check take profit
            if position.take_profit is not None:
                if (position.is_long and event.price >= position.take_profit) or \
                   (not position.is_long and event.price <= position.take_profit):
                    logger.info(f"Take profit triggered for {position}")
                    await self.position_tracker.close_position(
                        position.position_id,
                        event.price,
                        "Take profit triggered"
                    )
                    continue
            
            # Update trailing stop if appropriate
            if position.unrealized_pnl_pct > 0.05:  # If position is in >5% profit
                # Calculate new stop loss at 50% of profits
                if position.is_long:
                    new_stop = max(position.entry_price, event.price * 0.98)
                    if position.stop_loss is None or new_stop > position.stop_loss:
                        await self.position_tracker.update_stop_loss(
                            position.position_id,
                            new_stop,
                            "Trailing stop adjusted"
                        )
                else:
                    new_stop = min(position.entry_price, event.price * 1.02)
                    if position.stop_loss is None or new_stop < position.stop_loss:
                        await self.position_tracker.update_stop_loss(
                            position.position_id,
                            new_stop,
                            "Trailing stop adjusted"
                        )
    
    async def handle_prediction_event(self, event):
        """Handle prediction signal events."""
        logger.info(f"Received prediction for {event.symbol}: {event.signal} ({event.confidence:.2f})")
        
        # Check if we've already processed this prediction
        prediction_id = event.flow_data.get('prediction_id', event.event_id)
        if prediction_id in self.processed_predictions:
            logger.debug(f"Skipping already processed prediction {prediction_id}")
            return
        
        # Mark as processed
        self.processed_predictions.add(prediction_id)
        
        # Check if confidence meets threshold
        if event.confidence < 0.8:
            logger.debug(f"Prediction confidence too low: {event.confidence:.2f}")
            return
        
        # Check if we already have a position for this symbol
        has_position = await self.position_tracker.has_open_positions(event.symbol)
        
        if event.signal == "BUY" and not has_position:
            # Create a long position
            logger.info(f"Creating LONG position for {event.symbol} based on prediction")
            
            # Calculate position size (simplified)
            quantity = 100  # Fixed quantity for demo
            
            # Calculate stop loss and take profit
            stop_loss = event.price * 0.95  # 5% stop loss
            take_profit = event.price * 1.15  # 15% take profit
            
            await self.position_tracker.create_stock_position(
                event.symbol,
                quantity=quantity,
                entry_price=event.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy="PredictionSignal",
                metadata={
                    "prediction_id": prediction_id,
                    "confidence": event.confidence,
                    "signal": event.signal
                }
            )
            
        elif event.signal == "SELL" and not has_position:
            # Create a short position
            logger.info(f"Creating SHORT position for {event.symbol} based on prediction")
            
            # Calculate position size (simplified)
            quantity = -100  # Negative for short positions
            
            # Calculate stop loss and take profit
            stop_loss = event.price * 1.05  # 5% stop loss
            take_profit = event.price * 0.85  # 15% take profit
            
            await self.position_tracker.create_stock_position(
                event.symbol,
                quantity=quantity,
                entry_price=event.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy="PredictionSignal",
                metadata={
                    "prediction_id": prediction_id,
                    "confidence": event.confidence,
                    "signal": event.signal
                }
            )
            
        elif event.signal in ["SELL", "EXIT"] and has_position:
            # Close existing positions for this symbol
            positions = await self.position_tracker.get_positions_for_symbol(event.symbol)
            for position in positions:
                if position.status.value == "open":
                    logger.info(f"Closing position {position} based on prediction")
                    await self.position_tracker.close_position(
                        position.position_id,
                        event.price,
                        f"Prediction signal: {event.signal}"
                    )
    
    async def log_position_event(self, event):
        """Log position events."""
        if isinstance(event, PositionOpenEvent):
            logger.info(f"EVENT: Position opened: {event.symbol} - Qty: {event.quantity} @ {event.entry_price} - ID: {event.position_id}")
        elif isinstance(event, PositionUpdateEvent):
            if event.stop_loss_updated:
                logger.info(f"EVENT: Stop loss updated for {event.symbol}: {event.new_stop_loss} - ID: {event.position_id}")
            if event.take_profit_updated:
                logger.info(f"EVENT: Take profit updated for {event.symbol}: {event.new_take_profit} - ID: {event.position_id}")
            if event.current_price:
                logger.info(f"EVENT: Price updated for {event.symbol}: {event.current_price} - PnL: {event.unrealized_pnl:.2f} - ID: {event.position_id}")
        elif isinstance(event, PositionCloseEvent):
            logger.info(f"EVENT: Position closed: {event.symbol} - P&L: {event.realized_pnl:.2f} - Reason: {event.reason} - ID: {event.position_id}")


async def simulate_trading_session():
    """Simulate a trading session for demonstration."""
    # Create the event bus
    event_bus = EventBus()
    
    # Create position tracker
    position_tracker = PositionTracker(event_bus)
    
    # Create the demo handler
    demo_handler = PositionDemoHandler(event_bus, position_tracker)
    await demo_handler.initialize()
    
    logger.info("Starting simulation")
    
    # Simulate a series of events
    
    # 1. Initial prediction signals
    await event_bus.emit(PredictionSignalEvent(
        symbol="AAPL",
        signal="BUY",
        confidence=0.85,
        price=150.0,
        flow_data={"prediction_id": "pred_1"}
    ))
    
    await event_bus.emit(PredictionSignalEvent(
        symbol="MSFT",
        signal="SELL",
        confidence=0.9,
        price=300.0,
        flow_data={"prediction_id": "pred_2"}
    ))
    
    # Wait for positions to be created
    await asyncio.sleep(0.5)

    # Log current positions
    positions = await position_tracker.get_all_positions()
    logger.info(f"Active positions after creation: {len(positions)}")
    for position in positions:
        logger.info(f"Position created: {position}")
    
    # 2. Price updates
    for i in range(10):
        # AAPL price increases
        await event_bus.emit(PriceEvent(
            symbol="AAPL",
            price=150.0 + (i * 2),  # Price increases by $2 each time
            change=2.0,
            change_percent=2.0/150.0
        ))
        
        # MSFT price decreases
        await event_bus.emit(PriceEvent(
            symbol="MSFT",
            price=300.0 - (i * 3),  # Price decreases by $3 each time
            change=-3.0,
            change_percent=-3.0/300.0
        ))
        
        await asyncio.sleep(0.2)
    
    # Check positions after price updates
    positions = await position_tracker.get_all_positions()
    logger.info(f"Active positions after price updates: {len(positions)}")
    for position in positions:
        logger.info(f"Position status: {position} - P&L: {position.unrealized_pnl:.2f}")

    # 3. New prediction for AAPL
    await event_bus.emit(PredictionSignalEvent(
        symbol="AAPL",
        signal="SELL",
        confidence=0.95,
        price=170.0,
        flow_data={"prediction_id": "pred_3"}
    ))
    
    # Wait for position to be closed
    await asyncio.sleep(0.5)
    
    # 4. Final summary
    summary = await position_tracker.get_position_summary()
    logger.info(f"Position summary: {summary}")
    
    closed_positions = await position_tracker.get_closed_positions()
    logger.info(f"Closed positions: {len(closed_positions)}")
    for position in closed_positions:
        logger.info(f"  {position}")
    
    logger.info("Simulation completed")


if __name__ == "__main__":
    asyncio.run(simulate_trading_session())