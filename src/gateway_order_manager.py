#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gateway to Order Manager Integration

This module provides the integration between IBGateway and OrderManager,
connecting IBKR Gateway callbacks to the order management system.
"""

import asyncio
import logging
from typing import Optional, Dict, List

from src.gateway import IBGateway
from src.order.manager import OrderManager
from src.event.bus import EventBus

logger = logging.getLogger(__name__)

class OrderGatewayIntegration:
    """
    Integrates IBGateway with OrderManager for bidirectional order communication.
    
    This class sets up the necessary callbacks and event handlers to ensure
    order status updates and execution details flow between the IBKR Gateway
    and the order management system.
    """
    
    def __init__(self, gateway: IBGateway, order_manager: OrderManager):
        """
        Initialize the order gateway integration.
        
        Args:
            gateway: The IB Gateway instance
            order_manager: The Order Manager instance
        """
        self.gateway = gateway
        self.order_manager = order_manager
        self._initialized = False
        
        # Store gateway's original callbacks
        self._original_order_status = gateway.orderStatus
        self._original_exec_details = gateway.execDetails
        self._original_commission_report = gateway.commissionReport
        
        # Execution ID to commission mapping
        self._pending_commissions: Dict[str, Dict] = {}
    
    def initialize(self) -> None:
        """Set up the gateway callbacks to route to the order manager."""
        if self._initialized:
            return
        
        # Override the gateway callbacks
        self.gateway.orderStatus = self._order_status_callback
        self.gateway.execDetails = self._exec_details_callback
        self.gateway.commissionReport = self._commission_report_callback
        
        # Store reference to order manager in gateway
        self.gateway.order_manager = self.order_manager
        
        # Set the gateway reference in the order manager
        self.order_manager.gateway = self.gateway
        
        logger.info("Order Gateway Integration initialized")
        self._initialized = True
    
    def shutdown(self) -> None:
        """Restore original gateway callbacks."""
        if not self._initialized:
            return
        
        # Restore original callbacks
        self.gateway.orderStatus = self._original_order_status
        self.gateway.execDetails = self._original_exec_details
        self.gateway.commissionReport = self._original_commission_report
        
        # Clear references
        self.gateway.order_manager = None
        
        logger.info("Order Gateway Integration shutdown")
        self._initialized = False
    
    def _order_status_callback(
        self, 
        orderId: int, 
        status: str, 
        filled: float,
        remaining: float, 
        avgFillPrice: float, 
        permId: int,
        parentId: int, 
        lastFillPrice: float, 
        clientId: int,
        whyHeld: str, 
        mktCapPrice: float
    ) -> None:
        """Handle order status updates from IB and route to order manager."""
        # First call the original callback
        self._original_order_status(
            orderId, status, filled, remaining, avgFillPrice,
            permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice
        )
        
        # Create a task to handle the order status in the order manager
        asyncio.create_task(
            self.order_manager.handle_order_status_update(
                broker_order_id=str(orderId),
                status=status,
                filled=filled,
                remaining=remaining,
                avg_fill_price=avgFillPrice,
                last_fill_price=lastFillPrice
            )
        )
    
    def _exec_details_callback(self, reqId: int, contract, execution) -> None:
        """Handle execution details from IB and route to order manager."""
        # First call the original callback
        self._original_exec_details(reqId, contract, execution)
        
        # Store execution for later when we get the commission report
        # Commission is sent in a separate callback
        exec_id = execution.execId
        symbol = contract.symbol
        side = execution.side
        quantity = execution.shares
        price = execution.price
        order_id = execution.orderId
        
        # Create a pending commission entry
        self._pending_commissions[exec_id] = {
            "broker_order_id": str(order_id),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "commission": None  # Will be filled in commission report callback
        }
        
        # If we don't receive a commission report soon, process without it
        asyncio.create_task(self._process_execution_after_delay(exec_id))
    
    async def _process_execution_after_delay(self, exec_id: str, delay: float = 1.0) -> None:
        """Process execution after waiting for a commission report."""
        await asyncio.sleep(delay)
        
        if exec_id in self._pending_commissions:
            # We waited for the commission but didn't get it
            exec_data = self._pending_commissions.pop(exec_id)
            
            # Process the execution
            await self.order_manager.handle_execution_update(
                broker_order_id=exec_data["broker_order_id"],
                exec_id=exec_id,
                symbol=exec_data["symbol"],
                side=exec_data["side"],
                quantity=exec_data["quantity"],
                price=exec_data["price"],
                commission=exec_data.get("commission")
            )
    
    def _commission_report_callback(self, commissionReport) -> None:
        """Handle commission report and associate with execution."""
        # First call the original callback
        self._original_commission_report(commissionReport)
        
        # Get the execution ID and commission
        exec_id = commissionReport.execId
        commission = commissionReport.commission
        
        # Update pending execution with commission
        if exec_id in self._pending_commissions:
            exec_data = self._pending_commissions.pop(exec_id)
            exec_data["commission"] = commission
            
            # Process the execution with commission
            asyncio.create_task(
                self.order_manager.handle_execution_update(
                    broker_order_id=exec_data["broker_order_id"],
                    exec_id=exec_id,
                    symbol=exec_data["symbol"],
                    side=exec_data["side"],
                    quantity=exec_data["quantity"],
                    price=exec_data["price"],
                    commission=commission
                )
            )