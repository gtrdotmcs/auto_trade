"""
Trading strategies for the Kite Auto-Trading application.

This module contains the strategy engine and various trading strategy
implementations.
"""

from .base import (
    TechnicalStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
    StrategyManager,
)

__all__ = [
    'TechnicalStrategy',
    'MeanReversionStrategy',
    'TrendFollowingStrategy',
    'StrategyManager',
]