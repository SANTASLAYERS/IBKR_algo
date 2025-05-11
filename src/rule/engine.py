"""
Rule Engine implementation for the trading system.

This module contains the core RuleEngine class that manages rule registration,
evaluation, and execution.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Type

from src.event.base import BaseEvent
from src.event.bus import EventBus
from src.rule.base import Rule

logger = logging.getLogger(__name__)


class RuleEngine:
    """Core engine for evaluating and executing rules."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.rules: Dict[str, Rule] = {}
        self.running = False
        self.context: Dict[str, Any] = {}
        self.evaluation_interval = 1.0  # seconds
        self._evaluation_task = None
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def register_rule(self, rule: Rule) -> bool:
        """Register a rule with the engine."""
        if rule.rule_id in self.rules:
            logger.warning(f"Rule with ID {rule.rule_id} already exists and will be replaced")
            
        self.rules[rule.rule_id] = rule
        self._locks[rule.rule_id] = asyncio.Lock()
        return True
    
    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister a rule from the engine."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        del self.rules[rule_id]
        if rule_id in self._locks:
            del self._locks[rule_id]
        return True
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        self.rules[rule_id].enabled = True
        return True
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        self.rules[rule_id].enabled = False
        return True
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)
    
    def get_all_rules(self) -> List[Rule]:
        """Get all registered rules."""
        return list(self.rules.values())
    
    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the shared context."""
        self.context[key] = value
    
    def update_context(self, updates: Dict[str, Any]) -> None:
        """Update multiple values in the shared context."""
        self.context.update(updates)
    
    async def start(self) -> None:
        """Start the rule engine."""
        if self.running:
            logger.warning("Rule engine is already running")
            return

        self.running = True

        # In tests, we might want to skip the evaluation loop
        if not self.context.get("_skip_evaluation_loop_for_testing", False):
            self._evaluation_task = asyncio.create_task(self._evaluation_loop())

        # Subscribe to events
        await self.event_bus.subscribe(BaseEvent, self._handle_event)

        logger.info("Rule engine started")
    
    async def stop(self) -> None:
        """Stop the rule engine."""
        if not self.running:
            logger.warning("Rule engine is not running")
            return
            
        self.running = False
        
        # Cancel evaluation task
        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass
            
        # Unsubscribe from events
        await self.event_bus.unsubscribe(BaseEvent, self._handle_event)
        
        logger.info("Rule engine stopped")
    
    async def _evaluation_loop(self) -> None:
        """Background task for periodic rule evaluation."""
        while self.running:
            try:
                await self._evaluate_all_rules()
            except Exception as e:
                logger.error(f"Error in rule evaluation loop: {e}")
                
            await asyncio.sleep(self.evaluation_interval)
    
    async def _evaluate_all_rules(self) -> None:
        """Evaluate all rules against the current context."""
        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            [rule for rule in self.rules.values() if rule.enabled],
            key=lambda r: r.priority,
            reverse=True
        )
        
        for rule in sorted_rules:
            # Create rule-specific context
            rule_context = self.context.copy()
            rule_context.update(rule.context)
            
            # Acquire lock for this rule
            lock = self._locks.get(rule.rule_id)
            if not lock:
                # Create lock if it doesn't exist
                lock = asyncio.Lock()
                self._locks[rule.rule_id] = lock
                
            async with lock:
                try:
                    # Evaluate and execute rule
                    await rule.evaluate_and_execute(rule_context)
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
    
    async def _handle_event(self, event: BaseEvent) -> None:
        """Handle an incoming event."""
        # Add event to context
        self.context["event"] = event
        
        # Clone context for event handling
        event_context = self.context.copy()
        
        # Evaluate each rule with the event
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
                
            # Create rule-specific context
            rule_context = event_context.copy()
            rule_context.update(rule.context)
            
            # Acquire lock for this rule
            lock = self._locks.get(rule_id)
            if not lock:
                # Create lock if it doesn't exist
                lock = asyncio.Lock()
                self._locks[rule_id] = lock
                
            async with lock:
                try:
                    # Evaluate and execute rule
                    await rule.evaluate_and_execute(rule_context)
                except Exception as e:
                    logger.error(f"Error handling event for rule {rule_id}: {e}")