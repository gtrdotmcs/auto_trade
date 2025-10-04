"""
Base service interfaces for the Kite Auto-Trading application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from kite_auto_trading.models.base import Order, Position, StrategyConfig


class ConfigurationService(ABC):
    """Abstract interface for configuration management."""
    
    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure and values."""
        pass
    
    @abstractmethod
    def get_strategy_configs(self) -> List[StrategyConfig]:
        """Get all strategy configurations."""
        pass
    
    @abstractmethod
    def reload_config(self) -> None:
        """Reload configuration from source."""
        pass


class PortfolioService(ABC):
    """Abstract interface for portfolio management."""
    
    @abstractmethod
    def update_position(self, trade: Dict[str, Any]) -> None:
        """Update position based on trade execution."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all current positions."""
        pass
    
    @abstractmethod
    def calculate_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L."""
        pass
    
    @abstractmethod
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Generate portfolio summary report."""
        pass


class LoggingService(ABC):
    """Abstract interface for logging and monitoring."""
    
    @abstractmethod
    def log_trade(self, order: Order, execution_details: Dict[str, Any]) -> None:
        """Log trade execution details."""
        pass
    
    @abstractmethod
    def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error with context information."""
        pass
    
    @abstractmethod
    def log_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """Log performance metrics."""
        pass
    
    @abstractmethod
    def send_notification(self, message: str, level: str) -> None:
        """Send notification for critical events."""
        pass


class StrategyService(ABC):
    """Abstract interface for strategy management."""
    
    @abstractmethod
    def register_strategy(self, strategy_config: StrategyConfig) -> None:
        """Register a new strategy."""
        pass
    
    @abstractmethod
    def enable_strategy(self, strategy_name: str) -> None:
        """Enable a strategy."""
        pass
    
    @abstractmethod
    def disable_strategy(self, strategy_name: str) -> None:
        """Disable a strategy."""
        pass
    
    @abstractmethod
    def evaluate_strategies(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate all enabled strategies and return signals."""
        pass