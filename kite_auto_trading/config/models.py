"""
Configuration data models for Kite Auto Trading application.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class Environment(Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AppConfig:
    """Application configuration."""
    name: str = "Kite Auto Trading"
    version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True


@dataclass
class APIConfig:
    """API configuration for Kite Connect."""
    base_url: str = "https://api.kite.trade"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 0.5
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    api_secret: Optional[str] = None


@dataclass
class MarketDataConfig:
    """Market data configuration."""
    instruments: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=lambda: ["minute", "5minute", "15minute", "day"])
    buffer_size: int = 1000
    reconnect_interval: int = 10
    max_reconnect_attempts: int = 5
    timeout: int = 30


@dataclass
class RiskManagementConfig:
    """Risk management configuration."""
    max_daily_loss: float = 10000.0
    max_position_size_percent: float = 2.0
    max_positions_per_instrument: int = 1
    stop_loss_percent: float = 2.0
    target_profit_percent: float = 4.0
    emergency_stop_enabled: bool = True


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    enabled: List[str] = field(default_factory=list)
    config_path: str = "strategies/"


@dataclass
class PortfolioConfig:
    """Portfolio configuration."""
    initial_capital: float = 100000.0
    currency: str = "INR"
    brokerage_per_trade: float = 20.0
    tax_rate: float = 0.15


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/trading.log"
    max_file_size: str = "10MB"
    backup_count: int = 5
    console_output: bool = True


@dataclass
class AlertThresholds:
    """Alert threshold configuration."""
    daily_loss_percent: float = 5.0
    drawdown_percent: float = 10.0
    connection_failures: int = 3


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration."""
    performance_metrics_interval: int = 300  # seconds
    health_check_interval: int = 60  # seconds
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    type: str = "sqlite"
    path: str = "data/trading.db"
    backup_enabled: bool = True
    backup_interval: int = 3600  # seconds


@dataclass
class TradingConfig:
    """Main trading configuration containing all sub-configurations."""
    app: AppConfig = field(default_factory=AppConfig)
    api: APIConfig = field(default_factory=APIConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    risk_management: RiskManagementConfig = field(default_factory=RiskManagementConfig)
    strategies: StrategyConfig = field(default_factory=StrategyConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of validation errors.
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Validate API configuration
        if not self.api.base_url:
            errors.append("API base_url is required")
        if self.api.timeout <= 0:
            errors.append("API timeout must be positive")
        if self.api.max_retries < 0:
            errors.append("API max_retries must be non-negative")
        
        # Validate risk management
        if self.risk_management.max_daily_loss <= 0:
            errors.append("Risk management max_daily_loss must be positive")
        if not (0 < self.risk_management.max_position_size_percent <= 100):
            errors.append("Risk management max_position_size_percent must be between 0 and 100")
        if self.risk_management.stop_loss_percent <= 0:
            errors.append("Risk management stop_loss_percent must be positive")
        if self.risk_management.target_profit_percent <= 0:
            errors.append("Risk management target_profit_percent must be positive")
        
        # Validate portfolio
        if self.portfolio.initial_capital <= 0:
            errors.append("Portfolio initial_capital must be positive")
        if not (0 <= self.portfolio.tax_rate <= 1):
            errors.append("Portfolio tax_rate must be between 0 and 1")
        
        # Validate market data
        if self.market_data.buffer_size <= 0:
            errors.append("Market data buffer_size must be positive")
        if self.market_data.reconnect_interval <= 0:
            errors.append("Market data reconnect_interval must be positive")
        
        # Validate monitoring
        if self.monitoring.performance_metrics_interval <= 0:
            errors.append("Monitoring performance_metrics_interval must be positive")
        if self.monitoring.health_check_interval <= 0:
            errors.append("Monitoring health_check_interval must be positive")
        
        return errors

    def is_valid(self) -> bool:
        """
        Check if configuration is valid.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        return len(self.validate()) == 0