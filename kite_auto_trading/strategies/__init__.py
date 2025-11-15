"""
Trading strategies for the Kite Auto-Trading application.

This module contains the strategy engine and various trading strategy
implementations.
"""

from .base import (
    StrategyBase,
    TechnicalStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
    StrategyManager,
)

from .conditions import (
    Condition,
    CompositeCondition,
    ConditionOperator,
    ConditionEvaluator,
    create_price_condition,
    create_indicator_condition,
    create_volume_condition,
)

__all__ = [
    'StrategyBase',
    'TechnicalStrategy',
    'MeanReversionStrategy',
    'TrendFollowingStrategy',
    'StrategyManager',
    'Condition',
    'CompositeCondition',
    'ConditionOperator',
    'ConditionEvaluator',
    'create_price_condition',
    'create_indicator_condition',
    'create_volume_condition',
]