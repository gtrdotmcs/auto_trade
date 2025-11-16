"""
Portfolio management system for tracking positions, P&L, and performance metrics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import threading

from kite_auto_trading.models.base import (
    Order,
    Position as BasePosition,
    TransactionType,
    OrderStatus,
)


logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a completed trade."""
    instrument: str
    transaction_type: TransactionType
    quantity: int
    price: float
    timestamp: datetime
    order_id: str
    strategy_id: str = ""
    commission: float = 0.0
    tax: float = 0.0
    exchange_order_id: str = ""


@dataclass
class Position:
    """Enhanced position tracking with P&L calculation."""
    instrument: str
    quantity: int
    average_price: float
    current_price: float
    strategy_id: str
    entry_time: datetime
    last_update_time: datetime
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_commission: float = 0.0
    total_tax: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    
    def update_current_price(self, price: float) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = price
        self.last_update_time = datetime.now()
        self._calculate_unrealized_pnl()
    
    def _calculate_unrealized_pnl(self) -> None:
        """Calculate unrealized P&L based on current price."""
        if self.quantity == 0:
            self.unrealized_pnl = 0.0
            return
        
        # Calculate P&L: (current_price - average_price) * quantity
        # Positive quantity = long position, negative = short position
        self.unrealized_pnl = (self.current_price - self.average_price) * self.quantity
    
    def update_unrealized_pnl(self) -> None:
        """Public method to update unrealized P&L."""
        self._calculate_unrealized_pnl()
    
    def get_total_pnl(self) -> float:
        """Get total P&L including realized and unrealized."""
        return self.realized_pnl + self.unrealized_pnl
    
    def get_net_pnl(self) -> float:
        """Get net P&L after costs (commission and tax)."""
        return self.get_total_pnl() - self.total_commission - self.total_tax
    
    def get_position_value(self) -> float:
        """Get current position value."""
        return abs(self.quantity) * self.current_price
    
    def get_cost_basis(self) -> float:
        """Get cost basis of the position."""
        return abs(self.quantity) * self.average_price


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio state at a point in time."""
    timestamp: datetime
    total_value: float
    cash_balance: float
    positions_value: float
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_commission: float
    total_tax: float
    num_positions: int
    num_instruments: int


class PortfolioManager:
    """
    Manages portfolio positions, P&L tracking, and performance metrics.
    
    Features:
    - Real-time position tracking
    - P&L calculation including costs
    - Unrealized P&L monitoring
    - Trade history management
    - Portfolio snapshots and reporting
    """
    
    def __init__(
        self,
        initial_capital: float = 0.0,
        commission_rate: float = 0.0003,  # 0.03% default
        tax_rate: float = 0.0,  # STT/GST if applicable
    ):
        """
        Initialize PortfolioManager.
        
        Args:
            initial_capital: Starting capital
            commission_rate: Commission rate as decimal (e.g., 0.0003 for 0.03%)
            tax_rate: Tax rate as decimal
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        
        # Position tracking
        self._positions: Dict[str, Position] = {}
        self._closed_positions: List[Position] = []
        
        # Trade history
        self._trades: List[Trade] = []
        
        # P&L tracking
        self._realized_pnl = 0.0
        self._total_commission = 0.0
        self._total_tax = 0.0
        
        # Cash tracking
        self._cash_balance = initial_capital
        
        # Portfolio snapshots
        self._snapshots: List[PortfolioSnapshot] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_volume': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
        }
        
        logger.info(f"PortfolioManager initialized with capital: {initial_capital}")
    
    def update_position(self, trade: Dict[str, Any]) -> None:
        """
        Update position based on trade execution.
        
        Args:
            trade: Dictionary containing trade details
        """
        with self._lock:
            # Extract trade information
            instrument = trade['instrument']
            transaction_type = trade['transaction_type']
            quantity = trade['quantity']
            price = trade['price']
            timestamp = trade.get('timestamp', datetime.now())
            order_id = trade.get('order_id', '')
            strategy_id = trade.get('strategy_id', '')
            
            # Calculate costs
            trade_value = quantity * price
            commission = trade.get('commission', trade_value * self.commission_rate)
            tax = trade.get('tax', trade_value * self.tax_rate)
            
            # Create trade record
            trade_record = Trade(
                instrument=instrument,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                order_id=order_id,
                strategy_id=strategy_id,
                commission=commission,
                tax=tax,
                exchange_order_id=trade.get('exchange_order_id', '')
            )
            
            self._trades.append(trade_record)
            self._stats['total_trades'] += 1
            self._stats['total_volume'] += trade_value
            
            # Update cash balance
            if transaction_type == TransactionType.BUY:
                self._cash_balance -= (trade_value + commission + tax)
            else:  # SELL
                self._cash_balance += (trade_value - commission - tax)
            
            # Update position
            self._update_position_from_trade(trade_record)
            
            logger.info(
                f"Position updated: {instrument} - "
                f"{transaction_type.value} {quantity}@{price}"
            )
    
    def _update_position_from_trade(self, trade: Trade) -> None:
        """Update position tracking from trade."""
        instrument = trade.instrument
        
        # Get or create position
        if instrument not in self._positions:
            self._positions[instrument] = Position(
                instrument=instrument,
                quantity=0,
                average_price=0.0,
                current_price=trade.price,
                strategy_id=trade.strategy_id,
                entry_time=trade.timestamp,
                last_update_time=trade.timestamp
            )
        
        position = self._positions[instrument]
        
        # Calculate quantity change
        quantity_change = trade.quantity
        if trade.transaction_type == TransactionType.SELL:
            quantity_change = -quantity_change
        
        # Store previous state
        old_quantity = position.quantity
        old_avg_price = position.average_price
        
        # Calculate new position
        new_quantity = old_quantity + quantity_change
        
        # Update position based on transaction type
        if old_quantity == 0:
            # New position
            position.quantity = new_quantity
            position.average_price = trade.price
            position.entry_time = trade.timestamp
        elif (old_quantity > 0 and quantity_change > 0) or (old_quantity < 0 and quantity_change < 0):
            # Adding to existing position (same direction)
            position.quantity = new_quantity
            total_value = (abs(old_quantity) * old_avg_price) + (abs(quantity_change) * trade.price)
            position.average_price = total_value / abs(new_quantity)
        else:
            # Reducing or reversing position - calculate realized P&L
            reduction_quantity = min(abs(quantity_change), abs(old_quantity))
            
            if old_quantity > 0:  # Long position being reduced
                realized_pnl = reduction_quantity * (trade.price - old_avg_price)
            else:  # Short position being reduced
                realized_pnl = reduction_quantity * (old_avg_price - trade.price)
            
            position.realized_pnl += realized_pnl
            self._realized_pnl += realized_pnl
            
            # Track win/loss statistics only when position is fully or partially closed
            if abs(reduction_quantity) > 0:  # Only count when actually closing position
                if realized_pnl > 0:
                    self._stats['winning_trades'] += 1
                    if realized_pnl > self._stats['largest_win']:
                        self._stats['largest_win'] = realized_pnl
                elif realized_pnl < 0:
                    self._stats['losing_trades'] += 1
                    if realized_pnl < self._stats['largest_loss']:
                        self._stats['largest_loss'] = realized_pnl
            
            position.quantity = new_quantity
            
            # Update average price based on remaining position
            if new_quantity == 0:
                # Position fully closed - move to closed positions
                position.average_price = 0.0
                position.current_price = trade.price
                position.unrealized_pnl = 0.0
                self._closed_positions.append(position)
                del self._positions[instrument]
            elif (old_quantity > 0 and new_quantity > 0) or (old_quantity < 0 and new_quantity < 0):
                # Still have position in same direction, keep old average
                position.average_price = old_avg_price
            else:
                # Position reversed, use trade price for new position
                position.average_price = trade.price
                position.entry_time = trade.timestamp
        
        # Update costs
        position.total_commission += trade.commission
        position.total_tax += trade.tax
        self._total_commission += trade.commission
        self._total_tax += trade.tax
        
        # Update current price and unrealized P&L
        position.current_price = trade.price
        position.last_update_time = trade.timestamp
        position._calculate_unrealized_pnl()
        
        # Add trade to position history
        position.trades.append(trade)
    
    def update_market_price(self, instrument: str, price: float) -> None:
        """
        Update market price for an instrument and recalculate unrealized P&L.
        
        Args:
            instrument: Instrument symbol
            price: Current market price
        """
        with self._lock:
            if instrument in self._positions:
                self._positions[instrument].update_current_price(price)
                logger.debug(f"Market price updated: {instrument} = {price}")
    
    def get_positions(self) -> List[Position]:
        """
        Get all current positions.
        
        Returns:
            List of Position objects
        """
        with self._lock:
            return list(self._positions.values())
    
    def get_position(self, instrument: str) -> Optional[Position]:
        """
        Get position for specific instrument.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Position object if exists, None otherwise
        """
        with self._lock:
            return self._positions.get(instrument)
    
    def calculate_unrealized_pnl(self) -> float:
        """
        Calculate total unrealized P&L across all positions.
        
        Returns:
            Total unrealized P&L
        """
        with self._lock:
            return sum(pos.unrealized_pnl for pos in self._positions.values())
    
    def calculate_realized_pnl(self) -> float:
        """
        Calculate total realized P&L.
        
        Returns:
            Total realized P&L
        """
        with self._lock:
            return self._realized_pnl
    
    def calculate_total_pnl(self) -> float:
        """
        Calculate total P&L (realized + unrealized).
        
        Returns:
            Total P&L
        """
        return self.calculate_realized_pnl() + self.calculate_unrealized_pnl()
    
    def calculate_net_pnl(self) -> float:
        """
        Calculate net P&L after all costs.
        
        Returns:
            Net P&L after commission and tax
        """
        return self.calculate_total_pnl() - self._total_commission - self._total_tax
    
    def get_portfolio_value(self) -> float:
        """
        Calculate total portfolio value.
        
        Returns:
            Total portfolio value (cash + positions)
        """
        with self._lock:
            positions_value = sum(pos.get_position_value() for pos in self._positions.values())
            return self._cash_balance + positions_value
    
    def get_cash_balance(self) -> float:
        """
        Get current cash balance.
        
        Returns:
            Cash balance
        """
        with self._lock:
            return self._cash_balance
    
    def get_positions_value(self) -> float:
        """
        Get total value of all positions.
        
        Returns:
            Total positions value
        """
        with self._lock:
            return sum(pos.get_position_value() for pos in self._positions.values())
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive portfolio summary.
        
        Returns:
            Dictionary containing portfolio summary
        """
        with self._lock:
            positions_value = self.get_positions_value()
            total_value = self.get_portfolio_value()
            total_pnl = self.calculate_total_pnl()
            net_pnl = self.calculate_net_pnl()
            
            return {
                'timestamp': datetime.now(),
                'initial_capital': self.initial_capital,
                'cash_balance': self._cash_balance,
                'positions_value': positions_value,
                'total_value': total_value,
                'total_return': total_value - self.initial_capital,
                'total_return_pct': ((total_value - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0.0,
                'realized_pnl': self._realized_pnl,
                'unrealized_pnl': self.calculate_unrealized_pnl(),
                'total_pnl': total_pnl,
                'net_pnl': net_pnl,
                'total_commission': self._total_commission,
                'total_tax': self._total_tax,
                'total_costs': self._total_commission + self._total_tax,
                'num_positions': len(self._positions),
                'num_instruments': len(self._positions),
                'num_closed_positions': len(self._closed_positions),
                'total_trades': self._stats['total_trades'],
                'winning_trades': self._stats['winning_trades'],
                'losing_trades': self._stats['losing_trades'],
                'win_rate': (self._stats['winning_trades'] / (self._stats['winning_trades'] + self._stats['losing_trades']) * 100) if (self._stats['winning_trades'] + self._stats['losing_trades']) > 0 else 0.0,
                'total_volume': self._stats['total_volume'],
                'largest_win': self._stats['largest_win'],
                'largest_loss': self._stats['largest_loss'],
            }
    
    def get_position_details(self) -> List[Dict[str, Any]]:
        """
        Get detailed information for all positions.
        
        Returns:
            List of position detail dictionaries
        """
        with self._lock:
            details = []
            for pos in self._positions.values():
                details.append({
                    'instrument': pos.instrument,
                    'quantity': pos.quantity,
                    'average_price': pos.average_price,
                    'current_price': pos.current_price,
                    'position_value': pos.get_position_value(),
                    'cost_basis': pos.get_cost_basis(),
                    'realized_pnl': pos.realized_pnl,
                    'unrealized_pnl': pos.unrealized_pnl,
                    'total_pnl': pos.get_total_pnl(),
                    'net_pnl': pos.get_net_pnl(),
                    'total_commission': pos.total_commission,
                    'total_tax': pos.total_tax,
                    'strategy_id': pos.strategy_id,
                    'entry_time': pos.entry_time,
                    'last_update_time': pos.last_update_time,
                    'num_trades': len(pos.trades),
                    'pnl_pct': ((pos.current_price - pos.average_price) / pos.average_price * 100) if pos.average_price > 0 else 0.0,
                })
            return details
    
    def get_trades_history(
        self,
        instrument: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Get trade history with optional filters.
        
        Args:
            instrument: Optional instrument filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of Trade objects
        """
        with self._lock:
            trades = self._trades.copy()
            
            # Apply filters
            if instrument:
                trades = [t for t in trades if t.instrument == instrument]
            
            if start_time:
                trades = [t for t in trades if t.timestamp >= start_time]
            
            if end_time:
                trades = [t for t in trades if t.timestamp <= end_time]
            
            return trades
    
    def create_snapshot(self) -> PortfolioSnapshot:
        """
        Create a snapshot of current portfolio state.
        
        Returns:
            PortfolioSnapshot object
        """
        with self._lock:
            snapshot = PortfolioSnapshot(
                timestamp=datetime.now(),
                total_value=self.get_portfolio_value(),
                cash_balance=self._cash_balance,
                positions_value=self.get_positions_value(),
                total_pnl=self.calculate_total_pnl(),
                realized_pnl=self._realized_pnl,
                unrealized_pnl=self.calculate_unrealized_pnl(),
                total_commission=self._total_commission,
                total_tax=self._total_tax,
                num_positions=len(self._positions),
                num_instruments=len(self._positions)
            )
            
            self._snapshots.append(snapshot)
            return snapshot
    
    def get_snapshots(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[PortfolioSnapshot]:
        """
        Get portfolio snapshots with optional time filters.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of PortfolioSnapshot objects
        """
        with self._lock:
            snapshots = self._snapshots.copy()
            
            if start_time:
                snapshots = [s for s in snapshots if s.timestamp >= start_time]
            
            if end_time:
                snapshots = [s for s in snapshots if s.timestamp <= end_time]
            
            return snapshots
    
    def reset(self) -> None:
        """Reset portfolio to initial state."""
        with self._lock:
            self._positions.clear()
            self._closed_positions.clear()
            self._trades.clear()
            self._realized_pnl = 0.0
            self._total_commission = 0.0
            self._total_tax = 0.0
            self._cash_balance = self.initial_capital
            self._snapshots.clear()
            self._stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_volume': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
            }
            logger.info("Portfolio reset to initial state")
