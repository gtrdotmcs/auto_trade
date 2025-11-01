"""
Configuration module for Kite Auto Trading application.

This module provides comprehensive configuration management with support for:
- Type-safe configuration models using dataclasses
- YAML and JSON configuration file loading
- Environment-specific configuration overrides
- Environment variable integration
- Configuration validation
- Hot-reloading of configuration files
- Configuration change notifications
"""

from .models import (
    TradingConfig,
    AppConfig,
    APIConfig,
    MarketDataConfig,
    RiskManagementConfig,
    StrategyConfig,
    PortfolioConfig,
    LoggingConfig,
    MonitoringConfig,
    DatabaseConfig,
    AlertThresholds,
    Environment,
    LogLevel
)

from .loader import (
    ConfigLoader,
    ConfigurationError,
    load_config,
    save_config
)

from .manager import (
    ConfigManager,
    get_config_manager,
    get_config,
    reload_config
)

from .constants import *
from .logging_config import setup_logging, get_logger

__all__ = [
    # Models
    'TradingConfig',
    'AppConfig', 
    'APIConfig',
    'MarketDataConfig',
    'RiskManagementConfig',
    'StrategyConfig',
    'PortfolioConfig',
    'LoggingConfig',
    'MonitoringConfig',
    'DatabaseConfig',
    'AlertThresholds',
    'Environment',
    'LogLevel',
    
    # Loader
    'ConfigLoader',
    'ConfigurationError',
    'load_config',
    'save_config',
    
    # Manager
    'ConfigManager',
    'get_config_manager',
    'get_config',
    'reload_config',
    
    # Logging
    'setup_logging',
    'get_logger'
]