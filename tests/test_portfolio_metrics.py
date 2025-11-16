"""
Unit tests for portfolio metrics and reporting.
"""

import pytest
import math
from datetime import datetime, timedelta
from kite_auto_trading.services.portfolio_manager import PortfolioManager
from kite_auto_trading.services.portfolio_metrics import (
    PortfolioMetricsCalculator,
    PerformanceMetrics,
    RiskMetrics,
    DailyReport,
)
from kite_auto_trading.models.base import TransactionType


class TestPortfolioMetricsCalculator:
    """Test suite for PortfolioMetricsCalculator."""
    
    def test_initialization(self):
        """Test metrics calculator initialization."""
        portfolio = PortfolioManager(initial_capital=100000.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        assert calculator.portfolio == portfolio
        assert calculator.risk_free_rate == 0.05
        assert calculator.trading_days_per_year == 252
    
    def test_performance_metrics_no_trades(self):
        """Test performance metrics with no trades."""
        portfolio = PortfolioManager(initial_capital=100000.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        metrics = calculator.calculate_performance_metrics()
        
        assert metrics.total_return == 0.0
        assert metrics.total_return_pct == 0.0
        assert metrics.win_rate == 0.0
        assert metrics.total_trades == 0
    
    def test_performance_metrics_with_trades(self):
        """Test performance metrics with completed trades."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Execute winning trade
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        portfolio.create_snapshot()
        
        sell_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 100,
            'price': 550.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade)
        portfolio.create_snapshot()
        
        metrics = calculator.calculate_performance_metrics()
        
        assert metrics.total_return == 5000.0
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 100.0
        assert metrics.largest_win == 5000.0
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create multiple snapshots with varying returns
        for i in range(10):
            portfolio.create_snapshot()
            
            # Simulate some trades
            if i % 2 == 0:
                trade = {
                    'instrument': f'STOCK{i}',
                    'transaction_type': TransactionType.BUY,
                    'quantity': 10,
                    'price': 100.0 + i * 5,
                    'timestamp': datetime.now() + timedelta(days=i),
                    'order_id': f'ORDER{i}',
                    'commission': 0.0,
                    'tax': 0.0,
                }
                portfolio.update_position(trade)
        
        portfolio.create_snapshot()
        
        metrics = calculator.calculate_performance_metrics()
        
        # Sharpe ratio should be calculated (exact value depends on returns)
        assert isinstance(metrics.sharpe_ratio, float)
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create initial snapshot at peak
        portfolio.create_snapshot()
        
        # Execute losing trade to create drawdown
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Update market price to create unrealized loss
        portfolio.update_market_price('RELIANCE', 450.0)
        portfolio.create_snapshot()
        
        metrics = calculator.calculate_performance_metrics()
        
        # Should have drawdown due to unrealized loss
        assert metrics.current_drawdown > 0
        assert metrics.current_drawdown_pct > 0
        assert metrics.max_drawdown >= metrics.current_drawdown
    
    def test_risk_metrics_calculation(self):
        """Test risk metrics calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create long position
        buy_trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade1)
        
        # Create another long position
        buy_trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.BUY,
            'quantity': 50,
            'price': 1000.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade2)
        
        risk_metrics = calculator.calculate_risk_metrics()
        
        assert risk_metrics.long_exposure == 100000.0  # 100*500 + 50*1000
        assert risk_metrics.short_exposure == 0.0
        assert risk_metrics.net_exposure == 100000.0
        assert risk_metrics.gross_exposure == 100000.0
        assert 'RELIANCE' in risk_metrics.concentration_risk
        assert 'TCS' in risk_metrics.concentration_risk
    
    def test_concentration_risk(self):
        """Test concentration risk calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create position that's 50% of portfolio
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        risk_metrics = calculator.calculate_risk_metrics()
        
        # Position value is 50000, portfolio value is 100000
        # Concentration should be 50%
        assert abs(risk_metrics.concentration_risk['RELIANCE'] - 50.0) < 0.1
    
    def test_leverage_calculation(self):
        """Test leverage calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create position equal to portfolio value (1x leverage)
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 200,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        risk_metrics = calculator.calculate_risk_metrics()
        
        # Gross exposure = 100000, portfolio value = 100000
        # Leverage should be 1.0
        assert abs(risk_metrics.leverage - 1.0) < 0.1
    
    def test_daily_report_generation(self):
        """Test daily report generation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Execute some trades
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        portfolio.create_snapshot()
        
        # Update market price
        portfolio.update_market_price('RELIANCE', 550.0)
        portfolio.create_snapshot()
        
        # Generate daily report
        report = calculator.generate_daily_report()
        
        assert isinstance(report, DailyReport)
        assert report.num_trades >= 0
        assert report.num_positions >= 0
        assert isinstance(report.cash_balance, float)
    
    def test_period_report_generation(self):
        """Test period report generation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        # Execute some trades
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        portfolio.create_snapshot()
        
        # Generate period report
        report = calculator.generate_period_report(start_date, end_date)
        
        assert 'period' in report
        assert 'performance' in report
        assert 'trading' in report
        assert 'risk' in report
        assert 'portfolio' in report
    
    def test_risk_alerts_drawdown(self):
        """Test risk alerts for drawdown breach."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create initial snapshot
        portfolio.create_snapshot()
        
        # Create large loss to trigger drawdown alert
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 200,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Update to create 15% loss
        portfolio.update_market_price('RELIANCE', 425.0)
        portfolio.create_snapshot()
        
        # Check alerts with 10% max drawdown
        alerts = calculator.check_risk_alerts(max_drawdown_pct=10.0)
        
        # Should have drawdown alert
        drawdown_alerts = [a for a in alerts if a['type'] == 'DRAWDOWN_BREACH']
        assert len(drawdown_alerts) > 0
    
    def test_risk_alerts_leverage(self):
        """Test risk alerts for leverage breach."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create position with 2.5x leverage
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 500,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Check alerts with 2.0x max leverage
        alerts = calculator.check_risk_alerts(max_leverage=2.0)
        
        # Should have leverage alert
        leverage_alerts = [a for a in alerts if a['type'] == 'LEVERAGE_BREACH']
        assert len(leverage_alerts) > 0
    
    def test_risk_alerts_concentration(self):
        """Test risk alerts for concentration breach."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create position that's 60% of portfolio
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 120,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Check alerts with 50% max concentration
        alerts = calculator.check_risk_alerts(max_concentration_pct=50.0)
        
        # Should have concentration alert
        concentration_alerts = [a for a in alerts if a['type'] == 'CONCENTRATION_BREACH']
        assert len(concentration_alerts) > 0
    
    def test_volatility_calculation(self):
        """Test volatility calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Create snapshots with varying values
        for i in range(20):
            portfolio.create_snapshot()
            
            # Simulate price changes
            if i % 2 == 0:
                trade = {
                    'instrument': f'STOCK{i}',
                    'transaction_type': TransactionType.BUY,
                    'quantity': 10,
                    'price': 100.0 + (i % 5) * 10,
                    'timestamp': datetime.now() + timedelta(days=i),
                    'order_id': f'ORDER{i}',
                    'commission': 0.0,
                    'tax': 0.0,
                }
                portfolio.update_position(trade)
        
        portfolio.create_snapshot()
        
        metrics = calculator.calculate_performance_metrics()
        
        # Volatility should be calculated
        assert metrics.volatility >= 0.0
    
    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        calculator = PortfolioMetricsCalculator(portfolio)
        
        # Winning trade
        buy_trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade1)
        
        sell_trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 100,
            'price': 600.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade1)
        
        # Losing trade
        buy_trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.BUY,
            'quantity': 50,
            'price': 1000.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER3',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade2)
        
        sell_trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.SELL,
            'quantity': 50,
            'price': 900.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER4',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade2)
        
        metrics = calculator.calculate_performance_metrics()
        
        # Profit factor = total wins / total losses
        # Win = 10000, Loss = 5000, PF = 2.0
        assert metrics.profit_factor > 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
