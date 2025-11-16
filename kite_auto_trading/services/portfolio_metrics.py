"""
Portfolio performance metrics and reporting functionality.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from kite_auto_trading.services.portfolio_manager import (
    PortfolioManager,
    PortfolioSnapshot,
    Position,
    Trade,
)


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for portfolio analysis."""
    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    current_drawdown: float
    current_drawdown_pct: float
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    average_trade_duration: float
    volatility: float
    calmar_ratio: float


@dataclass
class RiskMetrics:
    """Risk exposure metrics."""
    total_exposure: float
    long_exposure: float
    short_exposure: float
    net_exposure: float
    gross_exposure: float
    leverage: float
    concentration_risk: Dict[str, float]
    var_95: float  # Value at Risk at 95% confidence
    var_99: float  # Value at Risk at 99% confidence


@dataclass
class DailyReport:
    """End-of-day portfolio report."""
    date: datetime
    starting_value: float
    ending_value: float
    daily_return: float
    daily_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    num_trades: int
    num_positions: int
    cash_balance: float
    positions_value: float
    total_commission: float
    total_tax: float
    top_gainers: List[Dict[str, Any]]
    top_losers: List[Dict[str, Any]]


class PortfolioMetricsCalculator:
    """
    Calculate portfolio performance metrics and generate reports.
    
    Features:
    - Performance metrics (Sharpe, Sortino, drawdown)
    - Risk exposure monitoring
    - Daily and period reports
    - Alert generation for risk thresholds
    """
    
    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        risk_free_rate: float = 0.05,  # 5% annual risk-free rate
        trading_days_per_year: int = 252,
    ):
        """
        Initialize PortfolioMetricsCalculator.
        
        Args:
            portfolio_manager: PortfolioManager instance
            risk_free_rate: Annual risk-free rate for Sharpe ratio
            trading_days_per_year: Number of trading days per year
        """
        self.portfolio = portfolio_manager
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
        
        # Daily tracking
        self._daily_returns: List[float] = []
        self._daily_values: List[Tuple[datetime, float]] = []
        self._peak_value = portfolio_manager.initial_capital
        self._daily_reports: List[DailyReport] = []
        
        logger.info("PortfolioMetricsCalculator initialized")
    
    def calculate_performance_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            start_date: Optional start date for calculation period
            end_date: Optional end date for calculation period
            
        Returns:
            PerformanceMetrics object
        """
        summary = self.portfolio.get_portfolio_summary()
        
        # Get snapshots for the period
        snapshots = self.portfolio.get_snapshots(start_date, end_date)
        
        # Calculate returns
        total_return = summary['total_return']
        total_return_pct = summary['total_return_pct']
        
        # Calculate annualized return
        if snapshots and len(snapshots) > 1:
            days = (snapshots[-1].timestamp - snapshots[0].timestamp).days
            if days > 0:
                annualized_return = ((1 + total_return_pct / 100) ** (365 / days) - 1) * 100
            else:
                annualized_return = 0.0
        else:
            annualized_return = 0.0
        
        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(snapshots)
        
        # Calculate Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(snapshots)
        
        # Calculate drawdown metrics
        max_dd, max_dd_pct, current_dd, current_dd_pct = self._calculate_drawdown_metrics(snapshots)
        
        # Calculate Calmar ratio
        calmar_ratio = (annualized_return / abs(max_dd_pct)) if max_dd_pct != 0 else 0.0
        
        # Calculate volatility
        volatility = self._calculate_volatility(snapshots)
        
        # Win/loss metrics
        winning_trades = summary['winning_trades']
        losing_trades = summary['losing_trades']
        total_trades = winning_trades + losing_trades
        win_rate = summary['win_rate']
        
        # Calculate profit factor
        total_wins = sum(
            t.quantity * (t.price - pos.average_price)
            for pos in self.portfolio._closed_positions
            for t in pos.trades
            if pos.realized_pnl > 0
        ) if hasattr(self.portfolio, '_closed_positions') else 0.0
        
        total_losses = abs(sum(
            t.quantity * (t.price - pos.average_price)
            for pos in self.portfolio._closed_positions
            for t in pos.trades
            if pos.realized_pnl < 0
        )) if hasattr(self.portfolio, '_closed_positions') else 0.0
        
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
        
        # Average win/loss
        average_win = (total_wins / winning_trades) if winning_trades > 0 else 0.0
        average_loss = (total_losses / losing_trades) if losing_trades > 0 else 0.0
        
        # Average trade duration
        average_duration = self._calculate_average_trade_duration()
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            current_drawdown=current_dd,
            current_drawdown_pct=current_dd_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=average_win,
            average_loss=average_loss,
            largest_win=summary['largest_win'],
            largest_loss=summary['largest_loss'],
            total_trades=summary['total_trades'],
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            average_trade_duration=average_duration,
            volatility=volatility,
            calmar_ratio=calmar_ratio
        )
    
    def _calculate_sharpe_ratio(self, snapshots: List[PortfolioSnapshot]) -> float:
        """Calculate Sharpe ratio from portfolio snapshots."""
        if len(snapshots) < 2:
            return 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(snapshots)):
            if snapshots[i-1].total_value > 0:
                ret = (snapshots[i].total_value - snapshots[i-1].total_value) / snapshots[i-1].total_value
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Calculate average return and standard deviation
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Annualize
        daily_rf_rate = self.risk_free_rate / self.trading_days_per_year
        sharpe = (avg_return - daily_rf_rate) / std_dev
        
        # Annualize Sharpe ratio
        return sharpe * math.sqrt(self.trading_days_per_year)
    
    def _calculate_sortino_ratio(self, snapshots: List[PortfolioSnapshot]) -> float:
        """Calculate Sortino ratio (uses downside deviation instead of total volatility)."""
        if len(snapshots) < 2:
            return 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(snapshots)):
            if snapshots[i-1].total_value > 0:
                ret = (snapshots[i].total_value - snapshots[i-1].total_value) / snapshots[i-1].total_value
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Calculate average return
        avg_return = sum(returns) / len(returns)
        
        # Calculate downside deviation (only negative returns)
        daily_rf_rate = self.risk_free_rate / self.trading_days_per_year
        downside_returns = [r - daily_rf_rate for r in returns if r < daily_rf_rate]
        
        if not downside_returns:
            return 0.0
        
        downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        
        if downside_dev == 0:
            return 0.0
        
        sortino = (avg_return - daily_rf_rate) / downside_dev
        
        # Annualize Sortino ratio
        return sortino * math.sqrt(self.trading_days_per_year)
    
    def _calculate_drawdown_metrics(
        self,
        snapshots: List[PortfolioSnapshot]
    ) -> Tuple[float, float, float, float]:
        """
        Calculate drawdown metrics.
        
        Returns:
            Tuple of (max_drawdown, max_drawdown_pct, current_drawdown, current_drawdown_pct)
        """
        if not snapshots:
            return 0.0, 0.0, 0.0, 0.0
        
        peak_value = snapshots[0].total_value
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        
        for snapshot in snapshots:
            if snapshot.total_value > peak_value:
                peak_value = snapshot.total_value
            
            drawdown = peak_value - snapshot.total_value
            drawdown_pct = (drawdown / peak_value * 100) if peak_value > 0 else 0.0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        # Current drawdown
        current_value = snapshots[-1].total_value
        current_drawdown = peak_value - current_value
        current_drawdown_pct = (current_drawdown / peak_value * 100) if peak_value > 0 else 0.0
        
        return max_drawdown, max_drawdown_pct, current_drawdown, current_drawdown_pct
    
    def _calculate_volatility(self, snapshots: List[PortfolioSnapshot]) -> float:
        """Calculate annualized volatility."""
        if len(snapshots) < 2:
            return 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(snapshots)):
            if snapshots[i-1].total_value > 0:
                ret = (snapshots[i].total_value - snapshots[i-1].total_value) / snapshots[i-1].total_value
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Calculate standard deviation
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        # Annualize
        return std_dev * math.sqrt(self.trading_days_per_year) * 100
    
    def _calculate_average_trade_duration(self) -> float:
        """Calculate average trade duration in hours."""
        if not hasattr(self.portfolio, '_closed_positions'):
            return 0.0
        
        durations = []
        for pos in self.portfolio._closed_positions:
            if pos.trades:
                entry_time = pos.entry_time
                exit_time = pos.trades[-1].timestamp
                duration = (exit_time - entry_time).total_seconds() / 3600  # Convert to hours
                durations.append(duration)
        
        return sum(durations) / len(durations) if durations else 0.0
    
    def calculate_risk_metrics(self) -> RiskMetrics:
        """
        Calculate risk exposure metrics.
        
        Returns:
            RiskMetrics object
        """
        positions = self.portfolio.get_positions()
        portfolio_value = self.portfolio.get_portfolio_value()
        
        # Calculate exposures
        long_exposure = 0.0
        short_exposure = 0.0
        instrument_exposure = defaultdict(float)
        
        for pos in positions:
            position_value = pos.get_position_value()
            
            if pos.quantity > 0:
                long_exposure += position_value
            else:
                short_exposure += position_value
            
            instrument_exposure[pos.instrument] = position_value
        
        total_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure
        gross_exposure = long_exposure + short_exposure
        
        # Calculate leverage
        leverage = (gross_exposure / portfolio_value) if portfolio_value > 0 else 0.0
        
        # Calculate concentration risk (% of portfolio in each instrument)
        concentration_risk = {}
        for instrument, exposure in instrument_exposure.items():
            concentration_risk[instrument] = (exposure / portfolio_value * 100) if portfolio_value > 0 else 0.0
        
        # Calculate VaR (simplified historical method)
        var_95, var_99 = self._calculate_var()
        
        return RiskMetrics(
            total_exposure=total_exposure,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            net_exposure=net_exposure,
            gross_exposure=gross_exposure,
            leverage=leverage,
            concentration_risk=concentration_risk,
            var_95=var_95,
            var_99=var_99
        )
    
    def _calculate_var(self) -> Tuple[float, float]:
        """Calculate Value at Risk at 95% and 99% confidence levels."""
        snapshots = self.portfolio.get_snapshots()
        
        if len(snapshots) < 2:
            return 0.0, 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(snapshots)):
            if snapshots[i-1].total_value > 0:
                ret = (snapshots[i].total_value - snapshots[i-1].total_value) / snapshots[i-1].total_value
                returns.append(ret)
        
        if not returns:
            return 0.0, 0.0
        
        # Sort returns
        sorted_returns = sorted(returns)
        
        # Get VaR at 95% and 99% confidence
        portfolio_value = self.portfolio.get_portfolio_value()
        
        idx_95 = int(len(sorted_returns) * 0.05)
        idx_99 = int(len(sorted_returns) * 0.01)
        
        var_95 = abs(sorted_returns[idx_95] * portfolio_value) if idx_95 < len(sorted_returns) else 0.0
        var_99 = abs(sorted_returns[idx_99] * portfolio_value) if idx_99 < len(sorted_returns) else 0.0
        
        return var_95, var_99
    
    def generate_daily_report(self, date: Optional[datetime] = None) -> DailyReport:
        """
        Generate end-of-day report.
        
        Args:
            date: Date for the report (defaults to today)
            
        Returns:
            DailyReport object
        """
        if date is None:
            date = datetime.now()
        
        # Get snapshots for the day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        snapshots = self.portfolio.get_snapshots(start_of_day, end_of_day)
        
        # Get starting and ending values
        if snapshots:
            starting_value = snapshots[0].total_value
            ending_value = snapshots[-1].total_value
        else:
            starting_value = self.portfolio.get_portfolio_value()
            ending_value = starting_value
        
        # Calculate daily return
        daily_return = ending_value - starting_value
        daily_return_pct = (daily_return / starting_value * 100) if starting_value > 0 else 0.0
        
        # Get trades for the day
        trades = self.portfolio.get_trades_history(start_time=start_of_day, end_time=end_of_day)
        
        # Get current portfolio state
        summary = self.portfolio.get_portfolio_summary()
        positions = self.portfolio.get_position_details()
        
        # Find top gainers and losers
        sorted_positions = sorted(positions, key=lambda x: x['pnl_pct'], reverse=True)
        top_gainers = sorted_positions[:5] if len(sorted_positions) > 0 else []
        top_losers = sorted_positions[-5:] if len(sorted_positions) > 5 else []
        
        report = DailyReport(
            date=date,
            starting_value=starting_value,
            ending_value=ending_value,
            daily_return=daily_return,
            daily_return_pct=daily_return_pct,
            realized_pnl=summary['realized_pnl'],
            unrealized_pnl=summary['unrealized_pnl'],
            total_pnl=summary['total_pnl'],
            num_trades=len(trades),
            num_positions=summary['num_positions'],
            cash_balance=summary['cash_balance'],
            positions_value=summary['positions_value'],
            total_commission=summary['total_commission'],
            total_tax=summary['total_tax'],
            top_gainers=top_gainers,
            top_losers=top_losers
        )
        
        self._daily_reports.append(report)
        return report
    
    def generate_period_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate report for a specific period.
        
        Args:
            start_date: Start date of period
            end_date: End date of period
            
        Returns:
            Dictionary containing period report
        """
        # Get performance metrics for period
        metrics = self.calculate_performance_metrics(start_date, end_date)
        
        # Get risk metrics
        risk_metrics = self.calculate_risk_metrics()
        
        # Get trades for period
        trades = self.portfolio.get_trades_history(start_time=start_date, end_time=end_date)
        
        # Get snapshots for period
        snapshots = self.portfolio.get_snapshots(start_date, end_date)
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'performance': {
                'total_return': metrics.total_return,
                'total_return_pct': metrics.total_return_pct,
                'annualized_return': metrics.annualized_return,
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'volatility': metrics.volatility,
                'max_drawdown': metrics.max_drawdown,
                'max_drawdown_pct': metrics.max_drawdown_pct,
                'calmar_ratio': metrics.calmar_ratio,
            },
            'trading': {
                'total_trades': len(trades),
                'winning_trades': metrics.winning_trades,
                'losing_trades': metrics.losing_trades,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'average_win': metrics.average_win,
                'average_loss': metrics.average_loss,
                'largest_win': metrics.largest_win,
                'largest_loss': metrics.largest_loss,
                'average_trade_duration': metrics.average_trade_duration,
            },
            'risk': {
                'total_exposure': risk_metrics.total_exposure,
                'long_exposure': risk_metrics.long_exposure,
                'short_exposure': risk_metrics.short_exposure,
                'net_exposure': risk_metrics.net_exposure,
                'leverage': risk_metrics.leverage,
                'var_95': risk_metrics.var_95,
                'var_99': risk_metrics.var_99,
                'concentration_risk': risk_metrics.concentration_risk,
            },
            'portfolio': self.portfolio.get_portfolio_summary(),
        }
    
    def check_risk_alerts(
        self,
        max_drawdown_pct: float = 10.0,
        max_leverage: float = 2.0,
        max_concentration_pct: float = 20.0,
        max_daily_loss_pct: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Check for risk threshold breaches and generate alerts.
        
        Args:
            max_drawdown_pct: Maximum allowed drawdown percentage
            max_leverage: Maximum allowed leverage
            max_concentration_pct: Maximum concentration in single instrument
            max_daily_loss_pct: Maximum daily loss percentage
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Check drawdown
        snapshots = self.portfolio.get_snapshots()
        if snapshots:
            _, _, _, current_dd_pct = self._calculate_drawdown_metrics(snapshots)
            if current_dd_pct > max_drawdown_pct:
                alerts.append({
                    'type': 'DRAWDOWN_BREACH',
                    'severity': 'HIGH',
                    'message': f'Current drawdown {current_dd_pct:.2f}% exceeds limit {max_drawdown_pct:.2f}%',
                    'value': current_dd_pct,
                    'threshold': max_drawdown_pct,
                    'timestamp': datetime.now()
                })
        
        # Check leverage
        risk_metrics = self.calculate_risk_metrics()
        if risk_metrics.leverage > max_leverage:
            alerts.append({
                'type': 'LEVERAGE_BREACH',
                'severity': 'MEDIUM',
                'message': f'Leverage {risk_metrics.leverage:.2f}x exceeds limit {max_leverage:.2f}x',
                'value': risk_metrics.leverage,
                'threshold': max_leverage,
                'timestamp': datetime.now()
            })
        
        # Check concentration risk
        for instrument, concentration in risk_metrics.concentration_risk.items():
            if concentration > max_concentration_pct:
                alerts.append({
                    'type': 'CONCENTRATION_BREACH',
                    'severity': 'MEDIUM',
                    'message': f'Concentration in {instrument} ({concentration:.2f}%) exceeds limit {max_concentration_pct:.2f}%',
                    'instrument': instrument,
                    'value': concentration,
                    'threshold': max_concentration_pct,
                    'timestamp': datetime.now()
                })
        
        # Check daily loss
        if self._daily_reports:
            latest_report = self._daily_reports[-1]
            if latest_report.daily_return_pct < -max_daily_loss_pct:
                alerts.append({
                    'type': 'DAILY_LOSS_BREACH',
                    'severity': 'HIGH',
                    'message': f'Daily loss {abs(latest_report.daily_return_pct):.2f}% exceeds limit {max_daily_loss_pct:.2f}%',
                    'value': abs(latest_report.daily_return_pct),
                    'threshold': max_daily_loss_pct,
                    'timestamp': datetime.now()
                })
        
        return alerts
    
    def get_daily_reports(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[DailyReport]:
        """
        Get daily reports with optional date filters.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of DailyReport objects
        """
        reports = self._daily_reports.copy()
        
        if start_date:
            reports = [r for r in reports if r.date >= start_date]
        
        if end_date:
            reports = [r for r in reports if r.date <= end_date]
        
        return reports
