"""
Risk Management Service for Kite Auto-Trading application.

This module implements comprehensive risk management including position sizing,
fund validation, margin checks, and position limits enforcement.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from ..models.base import Order, Position, RiskParameters, OrderType, TransactionType
from ..config.models import RiskManagementConfig, PortfolioConfig


class EmergencyStopReason(Enum):
    """Reasons for emergency stop activation."""
    DAILY_LOSS_LIMIT = "Daily loss limit exceeded"
    MAX_DRAWDOWN = "Maximum drawdown exceeded"
    MANUAL_TRIGGER = "Manual emergency stop triggered"
    SYSTEM_ERROR = "Critical system error"


@dataclass
class RiskValidationResult:
    """Result of risk validation check."""
    is_valid: bool
    reason: str
    suggested_quantity: Optional[int] = None


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""
    quantity: int
    risk_amount: float
    position_value: float
    reason: str


@dataclass
class DrawdownMetrics:
    """Drawdown tracking metrics."""
    peak_value: float
    current_value: float
    current_drawdown_percent: float
    max_drawdown_percent: float
    peak_date: date


class RiskManagerService:
    """
    Risk management service that handles position sizing, validation,
    and limit enforcement for trading operations.
    """
    
    def __init__(self, risk_config: RiskManagementConfig, portfolio_config: PortfolioConfig):
        """
        Initialize risk manager with configuration.
        
        Args:
            risk_config: Risk management configuration
            portfolio_config: Portfolio configuration
        """
        self.risk_config = risk_config
        self.portfolio_config = portfolio_config
        self.logger = logging.getLogger(__name__)
        
        # Track daily metrics
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._current_date = date.today()
        
        # Track positions by instrument
        self._positions: Dict[str, List[Position]] = {}
        self._total_portfolio_value: float = portfolio_config.initial_capital
        
        # Emergency stop state
        self._emergency_stop_active: bool = False
        self._emergency_stop_reason: Optional[EmergencyStopReason] = None
        self._emergency_stop_timestamp: Optional[datetime] = None
        
        # Drawdown tracking
        self._peak_portfolio_value: float = portfolio_config.initial_capital
        self._peak_date: date = date.today()
        self._max_drawdown_percent: float = 0.0
        
        # Emergency stop callbacks
        self._emergency_stop_callbacks: List[Callable[[EmergencyStopReason], None]] = []
        
        self.logger.info("RiskManager initialized with daily loss limit: %.2f", 
                        risk_config.max_daily_loss)
    
    def validate_order(self, order: Order, current_price: float, 
                      available_funds: float) -> RiskValidationResult:
        """
        Validate if order meets all risk criteria.
        
        Args:
            order: Order to validate
            current_price: Current market price of the instrument
            available_funds: Available funds in account
            
        Returns:
            RiskValidationResult with validation outcome
        """
        # Check emergency stop
        if self._emergency_stop_active:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Emergency stop active: {self._emergency_stop_reason.value if self._emergency_stop_reason else 'Unknown'}"
            )
        
        # Check daily loss limits
        if not self._check_daily_limits():
            return RiskValidationResult(
                is_valid=False,
                reason="Daily loss limit exceeded"
            )
        
        # Check position limits per instrument
        current_positions = len(self._positions.get(order.instrument, []))
        if current_positions >= self.risk_config.max_positions_per_instrument:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Maximum positions per instrument ({self.risk_config.max_positions_per_instrument}) reached"
            )
        
        # Calculate position value
        position_value = order.quantity * current_price
        
        # Check fund availability
        required_margin = self._calculate_margin_requirement(order, current_price)
        if required_margin > available_funds:
            # Calculate maximum affordable quantity
            max_quantity = int(available_funds / current_price)
            return RiskValidationResult(
                is_valid=False,
                reason="Insufficient funds",
                suggested_quantity=max_quantity
            )
        
        # Check position size limits
        max_position_value = (self._total_portfolio_value * 
                            self.risk_config.max_position_size_percent / 100)
        
        if position_value > max_position_value:
            max_quantity = int(max_position_value / current_price)
            return RiskValidationResult(
                is_valid=False,
                reason=f"Position size exceeds limit ({self.risk_config.max_position_size_percent}% of portfolio)",
                suggested_quantity=max_quantity
            )
        
        return RiskValidationResult(
            is_valid=True,
            reason="Order passes all risk checks"
        )
    
    def calculate_position_size(self, signal: Dict[str, any], current_price: float,
                              account_balance: float) -> PositionSizeResult:
        """
        Calculate appropriate position size based on risk parameters.
        
        Args:
            signal: Trading signal with strategy information
            current_price: Current market price
            account_balance: Available account balance
            
        Returns:
            PositionSizeResult with calculated position size
        """
        # Get risk percentage from signal or use default
        risk_percent = signal.get('risk_percent', self.risk_config.max_position_size_percent)
        
        # Calculate maximum risk amount
        max_risk_amount = account_balance * (risk_percent / 100)
        
        # Get stop loss percentage
        stop_loss_percent = signal.get('stop_loss_percent', self.risk_config.stop_loss_percent)
        
        # Calculate position size based on stop loss
        if stop_loss_percent > 0:
            # Risk per share = current_price * (stop_loss_percent / 100)
            risk_per_share = current_price * (stop_loss_percent / 100)
            
            # Quantity = max_risk_amount / risk_per_share
            calculated_quantity = int(max_risk_amount / risk_per_share)
        else:
            # If no stop loss, use maximum position size limit
            max_position_value = account_balance * (risk_percent / 100)
            calculated_quantity = int(max_position_value / current_price)
        
        # Ensure minimum quantity of 1
        quantity = max(1, calculated_quantity)
        
        # Calculate actual risk and position value
        actual_risk = quantity * current_price * (stop_loss_percent / 100)
        position_value = quantity * current_price
        
        # Validate against available funds
        if position_value > account_balance:
            quantity = int(account_balance / current_price)
            position_value = quantity * current_price
            actual_risk = quantity * current_price * (stop_loss_percent / 100)
        
        return PositionSizeResult(
            quantity=quantity,
            risk_amount=actual_risk,
            position_value=position_value,
            reason=f"Calculated based on {risk_percent}% risk and {stop_loss_percent}% stop loss"
        )
    
    def check_daily_limits(self) -> bool:
        """
        Check if daily trading limits are within bounds.
        
        Returns:
            True if within limits, False otherwise
        """
        return self._check_daily_limits()
    
    def update_daily_pnl(self, pnl_change: float) -> None:
        """
        Update daily P&L tracking.
        
        Args:
            pnl_change: Change in P&L (positive for profit, negative for loss)
        """
        # Reset daily tracking if new day
        current_date = date.today()
        if current_date != self._current_date:
            self._daily_pnl = 0.0
            self._daily_trades = 0
            self._current_date = current_date
            self.logger.info("Daily P&L tracking reset for new day: %s", current_date)
        
        self._daily_pnl += pnl_change
        self._daily_trades += 1
        
        self.logger.debug("Daily P&L updated: %.2f (change: %.2f)", 
                         self._daily_pnl, pnl_change)
    
    def add_position(self, position: Position) -> None:
        """
        Add a new position to tracking.
        
        Args:
            position: Position to add
        """
        if position.instrument not in self._positions:
            self._positions[position.instrument] = []
        
        self._positions[position.instrument].append(position)
        self.logger.info("Position added: %s %d shares at %.2f", 
                        position.instrument, position.quantity, position.average_price)
    
    def remove_position(self, instrument: str, position_id: Optional[str] = None) -> bool:
        """
        Remove a position from tracking.
        
        Args:
            instrument: Instrument symbol
            position_id: Optional position identifier (uses first position if None)
            
        Returns:
            True if position was removed, False otherwise
        """
        if instrument not in self._positions or not self._positions[instrument]:
            return False
        
        # Remove first position if no specific ID provided
        removed_position = self._positions[instrument].pop(0)
        
        # Clean up empty instrument list
        if not self._positions[instrument]:
            del self._positions[instrument]
        
        self.logger.info("Position removed: %s %d shares", 
                        removed_position.instrument, removed_position.quantity)
        return True
    
    def get_positions(self, instrument: Optional[str] = None) -> List[Position]:
        """
        Get current positions.
        
        Args:
            instrument: Optional instrument filter
            
        Returns:
            List of positions
        """
        if instrument:
            return self._positions.get(instrument, [])
        
        # Return all positions
        all_positions = []
        for positions in self._positions.values():
            all_positions.extend(positions)
        return all_positions
    
    def get_position_count(self, instrument: str) -> int:
        """
        Get number of positions for an instrument.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Number of positions
        """
        return len(self._positions.get(instrument, []))
    
    def get_daily_metrics(self) -> Dict[str, any]:
        """
        Get current daily trading metrics.
        
        Returns:
            Dictionary with daily metrics
        """
        return {
            'date': self._current_date.isoformat(),
            'daily_pnl': self._daily_pnl,
            'daily_trades': self._daily_trades,
            'daily_loss_limit': self.risk_config.max_daily_loss,
            'remaining_loss_capacity': self.risk_config.max_daily_loss + self._daily_pnl,
            'within_limits': self._check_daily_limits()
        }
    
    def update_portfolio_value(self, new_value: float) -> None:
        """
        Update total portfolio value for position sizing calculations.
        
        Args:
            new_value: New portfolio value
        """
        self._total_portfolio_value = new_value
        self.logger.debug("Portfolio value updated to: %.2f", new_value)
    
    def _check_daily_limits(self) -> bool:
        """
        Internal method to check daily loss limits.
        
        Returns:
            True if within limits, False otherwise
        """
        # Reset if new day
        current_date = date.today()
        if current_date != self._current_date:
            self._daily_pnl = 0.0
            self._daily_trades = 0
            self._current_date = current_date
        
        # Check if daily loss exceeds limit (daily_pnl is negative for losses)
        return self._daily_pnl > -self.risk_config.max_daily_loss
    
    def _calculate_margin_requirement(self, order: Order, current_price: float) -> float:
        """
        Calculate margin requirement for an order.
        
        Args:
            order: Order to calculate margin for
            current_price: Current market price
            
        Returns:
            Required margin amount
        """
        # For equity trading, typically 100% margin is required
        # This is a simplified calculation - in practice, margin requirements
        # vary by instrument type, volatility, etc.
        
        position_value = order.quantity * current_price
        
        if order.order_type in [OrderType.MARKET, OrderType.LIMIT]:
            # Full margin for market and limit orders
            return position_value
        else:
            # Reduced margin for stop loss orders (typically 20-30%)
            return position_value * 0.25
    
    # Emergency Stop and Protective Mechanisms
    
    def trigger_emergency_stop(self, reason: EmergencyStopReason) -> None:
        """
        Trigger emergency stop to halt all trading activities.
        
        Args:
            reason: Reason for emergency stop
        """
        if not self._emergency_stop_active:
            self._emergency_stop_active = True
            self._emergency_stop_reason = reason
            self._emergency_stop_timestamp = datetime.now()
            
            self.logger.critical("EMERGENCY STOP ACTIVATED: %s at %s", 
                               reason.value, self._emergency_stop_timestamp)
            
            # Execute callbacks
            for callback in self._emergency_stop_callbacks:
                try:
                    callback(reason)
                except Exception as e:
                    self.logger.error("Error executing emergency stop callback: %s", str(e))
    
    def clear_emergency_stop(self) -> bool:
        """
        Clear emergency stop and resume trading.
        
        Returns:
            True if emergency stop was cleared, False if it wasn't active
        """
        if self._emergency_stop_active:
            self._emergency_stop_active = False
            previous_reason = self._emergency_stop_reason
            self._emergency_stop_reason = None
            self._emergency_stop_timestamp = None
            
            self.logger.warning("Emergency stop cleared (was: %s)", 
                              previous_reason.value if previous_reason else "Unknown")
            return True
        return False
    
    def is_emergency_stop_active(self) -> bool:
        """
        Check if emergency stop is currently active.
        
        Returns:
            True if emergency stop is active, False otherwise
        """
        return self._emergency_stop_active
    
    def get_emergency_stop_info(self) -> Optional[Dict[str, any]]:
        """
        Get information about current emergency stop.
        
        Returns:
            Dictionary with emergency stop details or None if not active
        """
        if not self._emergency_stop_active:
            return None
        
        return {
            'active': True,
            'reason': self._emergency_stop_reason.value if self._emergency_stop_reason else "Unknown",
            'timestamp': self._emergency_stop_timestamp.isoformat() if self._emergency_stop_timestamp else None
        }
    
    def register_emergency_stop_callback(self, callback: Callable[[EmergencyStopReason], None]) -> None:
        """
        Register a callback to be executed when emergency stop is triggered.
        
        Args:
            callback: Function to call when emergency stop is triggered
        """
        self._emergency_stop_callbacks.append(callback)
        self.logger.debug("Emergency stop callback registered")
    
    def check_and_enforce_limits(self) -> bool:
        """
        Check all risk limits and trigger emergency stop if necessary.
        
        Returns:
            True if all limits are within bounds, False if emergency stop was triggered
        """
        # Check if already in emergency stop
        if self._emergency_stop_active:
            return False
        
        # Check daily loss limit
        if not self._check_daily_limits():
            self.logger.error("Daily loss limit exceeded: %.2f / %.2f", 
                            abs(self._daily_pnl), self.risk_config.max_daily_loss)
            if self.risk_config.emergency_stop_enabled:
                self.trigger_emergency_stop(EmergencyStopReason.DAILY_LOSS_LIMIT)
                return False
        
        # Check drawdown limit
        drawdown_metrics = self.get_drawdown_metrics()
        if drawdown_metrics.current_drawdown_percent > 20.0:  # 20% max drawdown threshold
            self.logger.error("Maximum drawdown exceeded: %.2f%%", 
                            drawdown_metrics.current_drawdown_percent)
            if self.risk_config.emergency_stop_enabled:
                self.trigger_emergency_stop(EmergencyStopReason.MAX_DRAWDOWN)
                return False
        
        return True
    
    def update_drawdown_tracking(self, current_portfolio_value: float) -> None:
        """
        Update drawdown tracking with current portfolio value.
        
        Args:
            current_portfolio_value: Current total portfolio value
        """
        # Update portfolio value
        self._total_portfolio_value = current_portfolio_value
        
        # Update peak if current value is higher
        if current_portfolio_value > self._peak_portfolio_value:
            self._peak_portfolio_value = current_portfolio_value
            self._peak_date = date.today()
            self.logger.debug("New portfolio peak: %.2f", self._peak_portfolio_value)
        
        # Calculate current drawdown
        if self._peak_portfolio_value > 0:
            current_drawdown = ((self._peak_portfolio_value - current_portfolio_value) / 
                              self._peak_portfolio_value * 100)
            
            # Update max drawdown if current is larger
            if current_drawdown > self._max_drawdown_percent:
                self._max_drawdown_percent = current_drawdown
                self.logger.info("New maximum drawdown: %.2f%%", self._max_drawdown_percent)
    
    def get_drawdown_metrics(self) -> DrawdownMetrics:
        """
        Get current drawdown metrics.
        
        Returns:
            DrawdownMetrics with current drawdown information
        """
        current_drawdown = 0.0
        if self._peak_portfolio_value > 0:
            current_drawdown = ((self._peak_portfolio_value - self._total_portfolio_value) / 
                              self._peak_portfolio_value * 100)
        
        return DrawdownMetrics(
            peak_value=self._peak_portfolio_value,
            current_value=self._total_portfolio_value,
            current_drawdown_percent=current_drawdown,
            max_drawdown_percent=self._max_drawdown_percent,
            peak_date=self._peak_date
        )
    
    def reset_daily_metrics(self) -> None:
        """
        Manually reset daily metrics (useful for testing or day rollover).
        """
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._current_date = date.today()
        self.logger.info("Daily metrics manually reset for date: %s", self._current_date)
    
    def get_risk_status(self) -> Dict[str, any]:
        """
        Get comprehensive risk status report.
        
        Returns:
            Dictionary with complete risk status information
        """
        daily_metrics = self.get_daily_metrics()
        drawdown_metrics = self.get_drawdown_metrics()
        emergency_info = self.get_emergency_stop_info()
        
        return {
            'emergency_stop': emergency_info,
            'daily_metrics': daily_metrics,
            'drawdown': {
                'peak_value': drawdown_metrics.peak_value,
                'current_value': drawdown_metrics.current_value,
                'current_drawdown_percent': drawdown_metrics.current_drawdown_percent,
                'max_drawdown_percent': drawdown_metrics.max_drawdown_percent,
                'peak_date': drawdown_metrics.peak_date.isoformat()
            },
            'position_count': sum(len(positions) for positions in self._positions.values()),
            'instruments_traded': len(self._positions)
        }