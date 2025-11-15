"""
Condition evaluation logic for trading strategies.

This module provides utilities for evaluating entry and exit conditions
based on market data and technical indicators.
"""

from typing import Any, Dict, List, Callable, Optional
from enum import Enum
from dataclasses import dataclass


class ConditionOperator(Enum):
    """Operators for condition evaluation."""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="
    AND = "AND"
    OR = "OR"
    CROSSES_ABOVE = "CROSSES_ABOVE"
    CROSSES_BELOW = "CROSSES_BELOW"


@dataclass
class Condition:
    """
    Represents a single trading condition.
    
    Attributes:
        field: Field name to evaluate (e.g., 'price', 'rsi', 'volume')
        operator: Comparison operator
        value: Value to compare against
        description: Human-readable description
    """
    field: str
    operator: ConditionOperator
    value: Any
    description: str = ""
    
    def evaluate(self, data: Dict[str, Any], previous_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate the condition against provided data.
        
        Args:
            data: Current market data
            previous_data: Previous market data (for cross conditions)
            
        Returns:
            True if condition is met, False otherwise
        """
        if self.field not in data:
            return False
        
        field_value = data[self.field]
        
        if self.operator == ConditionOperator.GREATER_THAN:
            return field_value > self.value
        elif self.operator == ConditionOperator.LESS_THAN:
            return field_value < self.value
        elif self.operator == ConditionOperator.GREATER_EQUAL:
            return field_value >= self.value
        elif self.operator == ConditionOperator.LESS_EQUAL:
            return field_value <= self.value
        elif self.operator == ConditionOperator.EQUAL:
            return field_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUAL:
            return field_value != self.value
        elif self.operator == ConditionOperator.CROSSES_ABOVE:
            if previous_data is None or self.field not in previous_data:
                return False
            prev_value = previous_data[self.field]
            return prev_value <= self.value < field_value
        elif self.operator == ConditionOperator.CROSSES_BELOW:
            if previous_data is None or self.field not in previous_data:
                return False
            prev_value = previous_data[self.field]
            return prev_value >= self.value > field_value
        
        return False


@dataclass
class CompositeCondition:
    """
    Represents multiple conditions combined with AND/OR logic.
    
    Attributes:
        conditions: List of Condition objects
        operator: Logical operator (AND/OR)
        description: Human-readable description
    """
    conditions: List[Condition]
    operator: ConditionOperator
    description: str = ""
    
    def __post_init__(self):
        """Validate composite condition."""
        if self.operator not in [ConditionOperator.AND, ConditionOperator.OR]:
            raise ValueError(f"Invalid operator for composite condition: {self.operator}")
    
    def evaluate(self, data: Dict[str, Any], previous_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate all conditions with the specified logical operator.
        
        Args:
            data: Current market data
            previous_data: Previous market data
            
        Returns:
            True if composite condition is met, False otherwise
        """
        if not self.conditions:
            return False
        
        results = [cond.evaluate(data, previous_data) for cond in self.conditions]
        
        if self.operator == ConditionOperator.AND:
            return all(results)
        elif self.operator == ConditionOperator.OR:
            return any(results)
        
        return False


class ConditionEvaluator:
    """
    Evaluates trading conditions and generates signals.
    
    This class provides utilities for evaluating entry and exit conditions
    based on market data and technical indicators.
    """
    
    def __init__(self):
        self.custom_evaluators: Dict[str, Callable] = {}
    
    def register_custom_evaluator(self, name: str, evaluator: Callable) -> None:
        """
        Register a custom condition evaluator function.
        
        Args:
            name: Name of the custom evaluator
            evaluator: Function that takes (data, previous_data) and returns bool
        """
        self.custom_evaluators[name] = evaluator
    
    def evaluate_condition(
        self,
        condition: Condition,
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Evaluate a single condition.
        
        Args:
            condition: Condition to evaluate
            data: Current market data
            previous_data: Previous market data
            
        Returns:
            True if condition is met, False otherwise
        """
        return condition.evaluate(data, previous_data)
    
    def evaluate_composite_condition(
        self,
        composite: CompositeCondition,
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Evaluate a composite condition.
        
        Args:
            composite: CompositeCondition to evaluate
            data: Current market data
            previous_data: Previous market data
            
        Returns:
            True if composite condition is met, False otherwise
        """
        return composite.evaluate(data, previous_data)
    
    def evaluate_entry_conditions(
        self,
        conditions: List[Condition],
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None,
        require_all: bool = True
    ) -> bool:
        """
        Evaluate entry conditions.
        
        Args:
            conditions: List of conditions to evaluate
            data: Current market data
            previous_data: Previous market data
            require_all: If True, all conditions must be met (AND logic)
            
        Returns:
            True if entry conditions are met, False otherwise
        """
        if not conditions:
            return False
        
        results = [cond.evaluate(data, previous_data) for cond in conditions]
        
        if require_all:
            return all(results)
        else:
            return any(results)
    
    def evaluate_exit_conditions(
        self,
        conditions: List[Condition],
        data: Dict[str, Any],
        entry_price: float,
        current_price: float,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None
    ) -> tuple[bool, str]:
        """
        Evaluate exit conditions including stop loss and take profit.
        
        Args:
            conditions: List of exit conditions
            data: Current market data
            entry_price: Entry price of the position
            current_price: Current market price
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            
        Returns:
            Tuple of (should_exit, reason)
        """
        # Check stop loss
        if stop_loss_pct is not None:
            loss_pct = ((current_price - entry_price) / entry_price) * 100
            if loss_pct <= -stop_loss_pct:
                return True, f"Stop loss triggered: {loss_pct:.2f}%"
        
        # Check take profit
        if take_profit_pct is not None:
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            if profit_pct >= take_profit_pct:
                return True, f"Take profit triggered: {profit_pct:.2f}%"
        
        # Check custom exit conditions
        for condition in conditions:
            if condition.evaluate(data):
                return True, condition.description or "Exit condition met"
        
        return False, ""
    
    def evaluate_custom_condition(
        self,
        name: str,
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Evaluate a custom registered condition.
        
        Args:
            name: Name of the custom evaluator
            data: Current market data
            previous_data: Previous market data
            
        Returns:
            True if condition is met, False otherwise
        """
        if name not in self.custom_evaluators:
            raise ValueError(f"Custom evaluator '{name}' not registered")
        
        return self.custom_evaluators[name](data, previous_data)


def create_price_condition(operator: ConditionOperator, threshold: float, description: str = "") -> Condition:
    """
    Create a price-based condition.
    
    Args:
        operator: Comparison operator
        threshold: Price threshold
        description: Condition description
        
    Returns:
        Condition object
    """
    return Condition(
        field='price',
        operator=operator,
        value=threshold,
        description=description or f"Price {operator.value} {threshold}"
    )


def create_indicator_condition(
    indicator: str,
    operator: ConditionOperator,
    threshold: float,
    description: str = ""
) -> Condition:
    """
    Create an indicator-based condition.
    
    Args:
        indicator: Indicator name (e.g., 'rsi', 'macd')
        operator: Comparison operator
        threshold: Threshold value
        description: Condition description
        
    Returns:
        Condition object
    """
    return Condition(
        field=indicator,
        operator=operator,
        value=threshold,
        description=description or f"{indicator} {operator.value} {threshold}"
    )


def create_volume_condition(operator: ConditionOperator, threshold: int, description: str = "") -> Condition:
    """
    Create a volume-based condition.
    
    Args:
        operator: Comparison operator
        threshold: Volume threshold
        description: Condition description
        
    Returns:
        Condition object
    """
    return Condition(
        field='volume',
        operator=operator,
        value=threshold,
        description=description or f"Volume {operator.value} {threshold}"
    )
