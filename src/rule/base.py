"""
Base classes for the rule engine system.

This module contains the foundation Rule, Condition, and Action classes
that form the building blocks of the rule engine.
"""

import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List, Type

logger = logging.getLogger(__name__)


class Condition(ABC):
    """Base abstract class for all conditions."""
    
    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition and return True if it is met."""
        pass
    
    def __and__(self, other: 'Condition') -> 'Condition':
        """Combine conditions with AND operator."""
        from src.rule.condition import AndCondition
        return AndCondition(self, other)
    
    def __or__(self, other: 'Condition') -> 'Condition':
        """Combine conditions with OR operator."""
        from src.rule.condition import OrCondition
        return OrCondition(self, other)
    
    def __invert__(self) -> 'Condition':
        """Negate condition with NOT operator."""
        from src.rule.condition import NotCondition
        return NotCondition(self)


class Action(ABC):
    """Base abstract class for all actions."""
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the action and return True if successful."""
        pass
    
    def __add__(self, other: 'Action') -> 'Action':
        """Combine actions to execute sequentially."""
        from src.rule.action import SequentialAction
        return SequentialAction(self, other)


@dataclass
class Rule:
    """Represents a configurable rule in the system."""
    
    # Core properties
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed Rule"
    description: str = ""
    enabled: bool = True
    
    # Rule logic
    condition: Condition = None
    action: Action = None
    
    # Execution characteristics
    priority: int = 0  # Higher numbers = higher priority
    cooldown_seconds: Optional[float] = None  # Minimum time between executions
    max_executions_per_day: Optional[int] = None  # Daily execution limit
    
    # Runtime tracking
    last_execution_time: Optional[datetime] = None
    execution_count: int = 0
    total_execution_count: int = 0
    
    # Lifecycle hooks
    pre_execution_hook: Optional[Callable] = None
    post_execution_hook: Optional[Callable] = None
    
    # Optional context data
    context: Dict[str, Any] = field(default_factory=dict)
    
    async def evaluate_and_execute(self, context: Dict[str, Any]) -> bool:
        """Evaluate the rule condition and execute the action if the condition is met."""
        # Check if rule is enabled
        if not self.enabled:
            return False
            
        # Check if rule is on cooldown
        if self.cooldown_seconds and self.last_execution_time:
            cooldown_expires = self.last_execution_time + timedelta(seconds=self.cooldown_seconds)
            if datetime.now() < cooldown_expires:
                return False
        
        # Check if rule has reached daily execution limit
        if self.max_executions_per_day and self.execution_count >= self.max_executions_per_day:
            return False
            
        # Merge context with rule-specific context
        merged_context = {**context, **self.context}
        
        # Execute pre-execution hook if provided
        if self.pre_execution_hook:
            self.pre_execution_hook(self, merged_context)
        
        try:
            # Evaluate condition
            if not await self.condition.evaluate(merged_context):
                return False
                
            # Execute action
            success = await self.action.execute(merged_context)
            
            # Update rule state if action was successful
            if success:
                self.last_execution_time = datetime.now()
                self.execution_count += 1
                self.total_execution_count += 1
                
                # Execute post-execution hook if provided
                if self.post_execution_hook:
                    self.post_execution_hook(self, merged_context, success)
                
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error evaluating rule {self.rule_id}: {e}")
            return False