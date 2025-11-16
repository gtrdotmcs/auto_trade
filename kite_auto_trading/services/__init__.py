"""
Service layer for the Kite Auto-Trading application.

This module contains business logic and service classes that orchestrate
the application's core functionality.
"""

from .base import (
    ConfigurationService,
    PortfolioService,
    LoggingService,
    StrategyService,
)

from .market_data_feed import (
    MarketDataFeed,
    ConnectionState,
)

from .risk_manager import (
    RiskManagerService,
    RiskValidationResult,
    PositionSizeResult,
    EmergencyStopReason,
    DrawdownMetrics,
)

from .order_manager import (
    OrderManager,
    OrderUpdate,
    OrderRecord,
    OrderValidationError,
    OrderExecutionError,
)

from .portfolio_manager import (
    PortfolioManager,
    Position,
    Trade,
    PortfolioSnapshot,
)

from .portfolio_metrics import (
    PortfolioMetricsCalculator,
    PerformanceMetrics,
    RiskMetrics,
    DailyReport,
)

__all__ = [
    'ConfigurationService',
    'PortfolioService',
    'LoggingService', 
    'StrategyService',
    'MarketDataFeed',
    'ConnectionState',
    'RiskManagerService',
    'RiskValidationResult',
    'PositionSizeResult',
    'EmergencyStopReason',
    'DrawdownMetrics',
    'OrderManager',
    'OrderUpdate',
    'OrderRecord',
    'OrderValidationError',
    'OrderExecutionError',
    'PortfolioManager',
    'Position',
    'Trade',
    'PortfolioSnapshot',
    'PortfolioMetricsCalculator',
    'PerformanceMetrics',
    'RiskMetrics',
    'DailyReport',
]