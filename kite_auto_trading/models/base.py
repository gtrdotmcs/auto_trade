"""
Base data models and interfaces for the Kite Auto-Trading application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class OrderType(Enum):
    """Order types supported by the system."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class TransactionType(Enum):
    """Transaction types for orders."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order data model."""
    instrument: str
    transaction_type: TransactionType
    quantity: int
    order_type: OrderType
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    strategy_id: str = ""
    timestamp: Optional[datetime] = None
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING


@dataclass
class Position:
    """Position data model."""
    instrument: str
    quantity: int
    average_price: float
    current_price: float
    unrealized_pnl: float
    strategy_id: str
    entry_time: datetime


@dataclass
class RiskParameters:
    """Risk management parameters."""
    max_position_size: float
    stop_loss_percentage: float
    target_profit_percentage: float
    daily_loss_limit: float
    max_positions_per_instrument: int


@dataclass
class StrategyConfig:
    """Strategy configuration data model."""
    name: str
    enabled: bool
    instruments: List[str]
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    risk_params: RiskParameters
    timeframe: str


class MarketDataProvider(ABC):
    """Abstract interface for market data providers."""
    
    @abstractmethod
    def subscribe_instruments(self, instruments: List[str]) -> None:
        """Subscribe to market data for given instruments."""
        pass
    
    @abstractmethod
    def get_current_price(self, instrument: str) -> Optional[float]:
        """Get current price for an instrument."""
        pass
    
    @abstractmethod
    def get_historical_data(self, instrument: str, timeframe: str) -> List[Dict[str, Any]]:
        """Get historical data for an instrument."""
        pass


class OrderExecutor(ABC):
    """Abstract interface for order execution."""
    
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """Place an order and return order ID."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status."""
        pass


class RiskManager(ABC):
    """Abstract interface for risk management."""
    
    @abstractmethod
    def validate_order(self, order: Order) -> bool:
        """Validate if order meets risk criteria."""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Dict[str, Any], account_balance: float) -> int:
        """Calculate appropriate position size."""
        pass
    
    @abstractmethod
    def check_daily_limits(self) -> bool:
        """Check if daily limits are within bounds."""
        pass


class Strategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.enabled = config.enabled
    
    @abstractmethod
    def evaluate(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate market data and return trading signals."""
        pass
    
    @abstractmethod
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate entry signals based on market data."""
        pass
    
    @abstractmethod
    def get_exit_signals(self, positions: List[Position]) -> List[Dict[str, Any]]:
        """Generate exit signals for current positions."""
        pass