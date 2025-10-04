"""
Kite Auto-Trading Application

An automated trading system that integrates with Zerodha's Kite Connect API
to execute trading strategies with proper risk management.
"""

__version__ = "0.1.0"
__author__ = "Auto-Trading System"

# Import key interfaces and classes for easy access
from .models import (
    Order,
    Position,
    RiskParameters,
    StrategyConfig,
    OrderType,
    TransactionType,
    OrderStatus,
)

from .api import (
    APIClient,
    TradingAPIClient,
    MarketDataAPIClient,
)

from .services import (
    ConfigurationService,
    PortfolioService,
    LoggingService,
    StrategyService,
)

from .strategies import (
    TechnicalStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
    StrategyManager,
)

__all__ = [
    # Version info
    '__version__',
    '__author__',
    
    # Core models
    'Order',
    'Position',
    'RiskParameters', 
    'StrategyConfig',
    'OrderType',
    'TransactionType',
    'OrderStatus',
    
    # API interfaces
    'APIClient',
    'TradingAPIClient',
    'MarketDataAPIClient',
    
    # Service interfaces
    'ConfigurationService',
    'PortfolioService',
    'LoggingService',
    'StrategyService',
    
    # Strategy classes
    'TechnicalStrategy',
    'MeanReversionStrategy', 
    'TrendFollowingStrategy',
    'StrategyManager',
]