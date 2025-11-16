"""
Backtesting framework for trading strategies.

This module provides functionality to test strategies against historical data
and evaluate their performance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from kite_auto_trading.strategies.base import StrategyBase
from kite_auto_trading.models.base import Position
from kite_auto_trading.models.signals import TradingSignal, SignalType


@dataclass
class BacktestTrade:
    """
    Represents a completed trade in backtesting.
    
    Attributes:
        instrument: Trading symbol
        entry_time: When the position was entered
        exit_time: When the position was exited
        entry_price: Entry price
        exit_price: Exit price
        quantity: Position size
        pnl: Profit/Loss for the trade
        pnl_pct: Profit/Loss percentage
        strategy_name: Name of the strategy
        entry_reason: Reason for entry
        exit_reason: Reason for exit
    """
    instrument: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    strategy_name: str
    entry_reason: str = ""
    exit_reason: str = ""
    
    def is_winning_trade(self) -> bool:
        """Check if this was a winning trade."""
        return self.pnl > 0
    
    def is_losing_trade(self) -> bool:
        """Check if this was a losing trade."""
        return self.pnl < 0
    
    def holding_period_hours(self) -> float:
        """Calculate holding period in hours."""
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 3600


@dataclass
class BacktestResults:
    """
    Results from a backtest run.
    
    Attributes:
        strategy_name: Name of the strategy tested
        start_date: Start date of backtest
        end_date: End date of backtest
        initial_capital: Starting capital
        final_capital: Ending capital
        total_trades: Total number of trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        total_pnl: Total profit/loss
        total_pnl_pct: Total profit/loss percentage
        win_rate: Percentage of winning trades
        avg_win: Average profit per winning trade
        avg_loss: Average loss per losing trade
        profit_factor: Ratio of gross profit to gross loss
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Risk-adjusted return metric
        trades: List of all trades
    """
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of backtest results."""
        return {
            'strategy_name': self.strategy_name,
            'period': f"{self.start_date.date()} to {self.end_date.date()}",
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
        }


class Backtester:
    """
    Backtesting engine for trading strategies.
    
    Tests strategies against historical data and generates performance metrics.
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_pct: float = 0.1,
        slippage_pct: float = 0.05
    ):
        """
        Initialize the backtester.
        
        Args:
            initial_capital: Starting capital for backtest
            commission_pct: Commission percentage per trade
            slippage_pct: Slippage percentage per trade
        """
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.completed_trades: List[BacktestTrade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
    
    def run_backtest(
        self,
        strategy: StrategyBase,
        historical_data: Dict[str, List[Dict[str, Any]]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> BacktestResults:
        """
        Run a backtest for a strategy.
        
        Args:
            strategy: Strategy to test
            historical_data: Historical price data by instrument
            start_date: Start date for backtest (optional)
            end_date: End date for backtest (optional)
            
        Returns:
            BacktestResults object with performance metrics
        """
        # Reset state
        self.current_capital = self.initial_capital
        self.positions = {}
        self.completed_trades = []
        self.equity_curve = [(datetime.now(), self.initial_capital)]
        
        # Filter data by date range if specified
        filtered_data = self._filter_data_by_date(historical_data, start_date, end_date)
        
        # Get all timestamps across all instruments
        all_timestamps = self._get_all_timestamps(filtered_data)
        
        if not all_timestamps:
            raise ValueError("No historical data available for backtesting")
        
        actual_start = all_timestamps[0]
        actual_end = all_timestamps[-1]
        
        # Simulate trading for each timestamp
        for timestamp in all_timestamps:
            # Build market data snapshot for this timestamp
            market_data = self._build_market_snapshot(filtered_data, timestamp)
            
            # Get current positions
            current_positions = list(self.positions.values())
            market_data['positions'] = current_positions
            
            # Evaluate strategy
            signals = strategy.evaluate(market_data)
            
            # Process signals
            for signal in signals:
                self._process_signal(signal, timestamp)
            
            # Update equity curve
            equity = self._calculate_current_equity(market_data)
            self.equity_curve.append((timestamp, equity))
        
        # Close any remaining positions at end
        self._close_all_positions(all_timestamps[-1], filtered_data)
        
        # Calculate performance metrics
        results = self._calculate_results(strategy.config.name, actual_start, actual_end)
        
        return results
    
    def _filter_data_by_date(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Filter historical data by date range."""
        if start_date is None and end_date is None:
            return data
        
        filtered = {}
        for instrument, candles in data.items():
            filtered_candles = []
            for candle in candles:
                timestamp = candle.get('timestamp', datetime.now())
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered_candles.append(candle)
            filtered[instrument] = filtered_candles
        
        return filtered
    
    def _get_all_timestamps(self, data: Dict[str, List[Dict[str, Any]]]) -> List[datetime]:
        """Get all unique timestamps from historical data."""
        timestamps = set()
        for candles in data.values():
            for candle in candles:
                if 'timestamp' in candle:
                    timestamps.add(candle['timestamp'])
        return sorted(list(timestamps))
    
    def _build_market_snapshot(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        timestamp: datetime
    ) -> Dict[str, Any]:
        """Build market data snapshot for a specific timestamp."""
        snapshot = {'price_history': {}}
        
        for instrument, candles in data.items():
            # Get all candles up to this timestamp
            history = [c for c in candles if c.get('timestamp', datetime.now()) <= timestamp]
            snapshot['price_history'][instrument] = history
        
        return snapshot
    
    def _process_signal(self, signal: TradingSignal, timestamp: datetime) -> None:
        """Process a trading signal."""
        instrument = signal.instrument
        
        if signal.is_entry_signal():
            # Only enter if we don't have a position
            if instrument not in self.positions:
                self._enter_position(signal, timestamp)
        
        elif signal.is_exit_signal():
            # Only exit if we have a position
            if instrument in self.positions:
                self._exit_position(signal, timestamp)
    
    def _enter_position(self, signal: TradingSignal, timestamp: datetime) -> None:
        """Enter a new position."""
        instrument = signal.instrument
        
        # Calculate position size (simple: use 10% of capital per trade)
        position_value = self.current_capital * 0.1
        
        # Apply slippage
        entry_price = signal.price * (1 + self.slippage_pct / 100)
        
        # Calculate quantity
        quantity = int(position_value / entry_price)
        if quantity <= 0:
            return
        
        # Calculate costs
        trade_value = quantity * entry_price
        commission = trade_value * (self.commission_pct / 100)
        total_cost = trade_value + commission
        
        # Check if we have enough capital
        if total_cost > self.current_capital:
            return
        
        # Adjust for short positions
        if signal.signal_type == SignalType.ENTRY_SHORT:
            quantity = -quantity
        
        # Create position
        position = Position(
            instrument=instrument,
            quantity=quantity,
            average_price=entry_price,
            current_price=entry_price,
            unrealized_pnl=0.0,
            strategy_id=signal.strategy_name,
            entry_time=timestamp
        )
        
        self.positions[instrument] = position
        self.current_capital -= total_cost
    
    def _exit_position(self, signal: TradingSignal, timestamp: datetime) -> None:
        """Exit an existing position."""
        instrument = signal.instrument
        position = self.positions.get(instrument)
        
        if not position:
            return
        
        # Apply slippage
        exit_price = signal.price * (1 - self.slippage_pct / 100)
        
        # Calculate P&L
        if position.quantity > 0:  # Long position
            pnl = (exit_price - position.average_price) * position.quantity
        else:  # Short position
            pnl = (position.average_price - exit_price) * abs(position.quantity)
        
        # Calculate commission
        trade_value = abs(position.quantity) * exit_price
        commission = trade_value * (self.commission_pct / 100)
        
        # Net P&L
        net_pnl = pnl - commission
        pnl_pct = (net_pnl / (abs(position.quantity) * position.average_price)) * 100
        
        # Create trade record
        trade = BacktestTrade(
            instrument=instrument,
            entry_time=position.entry_time,
            exit_time=timestamp,
            entry_price=position.average_price,
            exit_price=exit_price,
            quantity=position.quantity,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            strategy_name=signal.strategy_name,
            entry_reason="",
            exit_reason=signal.reason
        )
        
        self.completed_trades.append(trade)
        
        # Update capital
        self.current_capital += trade_value + net_pnl
        
        # Remove position
        del self.positions[instrument]
    
    def _close_all_positions(
        self,
        timestamp: datetime,
        data: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Close all open positions at end of backtest."""
        for instrument, position in list(self.positions.items()):
            # Get last price
            candles = data.get(instrument, [])
            if not candles:
                continue
            
            last_price = candles[-1]['close']
            
            # Create exit signal
            signal = TradingSignal(
                signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                instrument=instrument,
                timestamp=timestamp,
                price=last_price,
                strength=None,
                strategy_name=position.strategy_id,
                reason="End of backtest"
            )
            
            self._exit_position(signal, timestamp)
    
    def _calculate_current_equity(self, market_data: Dict[str, Any]) -> float:
        """Calculate current equity including open positions."""
        equity = self.current_capital
        
        for instrument, position in self.positions.items():
            # Get current price
            history = market_data.get('price_history', {}).get(instrument, [])
            if history:
                current_price = history[-1]['close']
                
                # Calculate unrealized P&L
                if position.quantity > 0:
                    unrealized_pnl = (current_price - position.average_price) * position.quantity
                else:
                    unrealized_pnl = (position.average_price - current_price) * abs(position.quantity)
                
                equity += unrealized_pnl
        
        return equity
    
    def _calculate_results(
        self,
        strategy_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResults:
        """Calculate performance metrics from completed trades."""
        results = BacktestResults(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.current_capital,
            trades=self.completed_trades
        )
        
        if not self.completed_trades:
            return results
        
        # Basic metrics
        results.total_trades = len(self.completed_trades)
        results.total_pnl = sum(t.pnl for t in self.completed_trades)
        results.total_pnl_pct = (results.total_pnl / self.initial_capital) * 100
        
        # Win/loss metrics
        winning_trades = [t for t in self.completed_trades if t.is_winning_trade()]
        losing_trades = [t for t in self.completed_trades if t.is_losing_trade()]
        
        results.winning_trades = len(winning_trades)
        results.losing_trades = len(losing_trades)
        results.win_rate = (results.winning_trades / results.total_trades) * 100 if results.total_trades > 0 else 0
        
        # Average win/loss
        if winning_trades:
            results.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
        if losing_trades:
            results.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        results.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Max drawdown
        results.max_drawdown = self._calculate_max_drawdown()
        
        # Sharpe ratio
        results.sharpe_ratio = self._calculate_sharpe_ratio()
        
        return results
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        peak = self.equity_curve[0][1]
        max_dd = 0.0
        
        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from returns."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1][1]
            curr_equity = self.equity_curve[i][1]
            ret = (curr_equity - prev_equity) / prev_equity
            returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Calculate mean and std
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = variance ** 0.5
        
        # Sharpe ratio (assuming risk-free rate = 0)
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming daily data)
        sharpe = (mean_return / std_return) * (252 ** 0.5)
        
        return sharpe
