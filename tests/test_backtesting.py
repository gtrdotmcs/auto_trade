"""
Integration tests for backtesting framework.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict
from kite_auto_trading.strategies.backtesting import Backtester, BacktestTrade, BacktestResults
from kite_auto_trading.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from kite_auto_trading.strategies.rsi_mean_reversion import RSIMeanReversionStrategy
from kite_auto_trading.models.base import StrategyConfig
from kite_auto_trading.models.signals import StrategyParameters


@pytest.fixture
def backtester():
    """Create a backtester instance."""
    return Backtester(
        initial_capital=100000.0,
        commission_pct=0.1,
        slippage_pct=0.05
    )


@pytest.fixture
def ma_strategy():
    """Create a Moving Average strategy for testing."""
    config = StrategyConfig(
        name="MA_Backtest",
        enabled=True,
        instruments=["TEST"],
        entry_conditions={},
        exit_conditions={},
        risk_params={},
        timeframe="day"
    )
    params = StrategyParameters()
    params.custom_params = {
        'short_period': 5,
        'long_period': 10,
        'ma_type': 'SMA'
    }
    return MovingAverageCrossoverStrategy(config, params)


@pytest.fixture
def rsi_strategy():
    """Create an RSI strategy for testing."""
    config = StrategyConfig(
        name="RSI_Backtest",
        enabled=True,
        instruments=["TEST"],
        entry_conditions={
            'oversold_threshold': 30,
            'overbought_threshold': 70
        },
        exit_conditions={},
        risk_params={},
        timeframe="day"
    )
    params = StrategyParameters()
    params.custom_params = {
        'rsi_period': 14,
        'exit_on_neutral': True
    }
    return RSIMeanReversionStrategy(config, params)


def generate_trending_data(start_price: float, num_days: int, trend: str = 'up') -> List[Dict]:
    """Generate trending price data for testing."""
    data = []
    base_date = datetime(2024, 1, 1)
    price = start_price
    
    for i in range(num_days):
        if trend == 'up':
            change = (i % 3) * 0.5 + 0.5  # Upward trend with noise
        elif trend == 'down':
            change = -((i % 3) * 0.5 + 0.5)  # Downward trend with noise
        else:
            change = ((i % 4) - 2) * 0.3  # Sideways with noise
        
        price += change
        
        candle = {
            'timestamp': base_date + timedelta(days=i),
            'open': price - 0.2,
            'high': price + 0.5,
            'low': price - 0.5,
            'close': price,
            'volume': 10000 + (i * 100)
        }
        data.append(candle)
    
    return data


def test_backtester_initialization(backtester):
    """Test backtester initialization."""
    assert backtester.initial_capital == 100000.0
    assert backtester.commission_pct == 0.1
    assert backtester.slippage_pct == 0.05
    assert backtester.current_capital == 100000.0
    assert len(backtester.positions) == 0
    assert len(backtester.completed_trades) == 0


def test_backtest_trade_creation():
    """Test BacktestTrade creation and methods."""
    trade = BacktestTrade(
        instrument="TEST",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 2),
        entry_price=100.0,
        exit_price=105.0,
        quantity=10,
        pnl=50.0,
        pnl_pct=5.0,
        strategy_name="TestStrategy"
    )
    
    assert trade.is_winning_trade() is True
    assert trade.is_losing_trade() is False
    assert trade.holding_period_hours() == 24.0


def test_backtest_results_summary():
    """Test BacktestResults summary generation."""
    results = BacktestResults(
        strategy_name="TestStrategy",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=100000.0,
        final_capital=110000.0,
        total_trades=10,
        winning_trades=6,
        losing_trades=4,
        total_pnl=10000.0,
        total_pnl_pct=10.0,
        win_rate=60.0
    )
    
    summary = results.summary()
    
    assert summary['strategy_name'] == "TestStrategy"
    assert summary['total_trades'] == 10
    assert summary['win_rate'] == 60.0
    assert summary['total_pnl'] == 10000.0


def test_run_backtest_with_ma_strategy(backtester, ma_strategy):
    """Test running a backtest with MA crossover strategy."""
    # Generate uptrending data
    historical_data = {
        'TEST': generate_trending_data(100.0, 30, 'up')
    }
    
    results = backtester.run_backtest(ma_strategy, historical_data)
    
    # Verify results structure
    assert isinstance(results, BacktestResults)
    assert results.strategy_name == "MA_Backtest"
    assert results.initial_capital == 100000.0
    assert results.total_trades >= 0
    
    # If trades were made, verify metrics
    if results.total_trades > 0:
        assert results.winning_trades + results.losing_trades == results.total_trades
        assert 0 <= results.win_rate <= 100


def test_run_backtest_with_rsi_strategy(backtester, rsi_strategy):
    """Test running a backtest with RSI strategy."""
    # Generate oscillating data (good for mean reversion)
    data = []
    base_date = datetime(2024, 1, 1)
    price = 100.0
    
    for i in range(40):
        # Create oscillating pattern
        if i % 8 < 4:
            price -= 1.5  # Decline
        else:
            price += 1.5  # Rise
        
        candle = {
            'timestamp': base_date + timedelta(days=i),
            'open': price - 0.2,
            'high': price + 0.5,
            'low': price - 0.5,
            'close': price,
            'volume': 10000
        }
        data.append(candle)
    
    historical_data = {'TEST': data}
    
    results = backtester.run_backtest(rsi_strategy, historical_data)
    
    assert isinstance(results, BacktestResults)
    assert results.strategy_name == "RSI_Backtest"
    assert results.total_trades >= 0


def test_backtest_with_date_range(backtester, ma_strategy):
    """Test backtesting with specific date range."""
    historical_data = {
        'TEST': generate_trending_data(100.0, 60, 'up')
    }
    
    start_date = datetime(2024, 1, 15)
    end_date = datetime(2024, 2, 15)
    
    results = backtester.run_backtest(
        ma_strategy,
        historical_data,
        start_date=start_date,
        end_date=end_date
    )
    
    assert results.start_date >= start_date
    assert results.end_date <= end_date


def test_backtest_calculates_metrics(backtester, ma_strategy):
    """Test that backtest calculates all required metrics."""
    historical_data = {
        'TEST': generate_trending_data(100.0, 50, 'up')
    }
    
    results = backtester.run_backtest(ma_strategy, historical_data)
    
    # Check that all metrics are present
    assert hasattr(results, 'total_trades')
    assert hasattr(results, 'winning_trades')
    assert hasattr(results, 'losing_trades')
    assert hasattr(results, 'win_rate')
    assert hasattr(results, 'total_pnl')
    assert hasattr(results, 'total_pnl_pct')
    assert hasattr(results, 'max_drawdown')
    assert hasattr(results, 'sharpe_ratio')
    assert hasattr(results, 'profit_factor')


def test_backtest_with_no_signals(backtester, ma_strategy):
    """Test backtest when strategy generates no signals."""
    # Generate very short data that won't trigger signals
    historical_data = {
        'TEST': generate_trending_data(100.0, 5, 'sideways')
    }
    
    results = backtester.run_backtest(ma_strategy, historical_data)
    
    assert results.total_trades == 0
    assert results.total_pnl == 0.0
    assert len(results.trades) == 0


def test_backtest_commission_and_slippage(backtester, ma_strategy):
    """Test that commission and slippage are applied."""
    historical_data = {
        'TEST': generate_trending_data(100.0, 30, 'up')
    }
    
    # Run backtest with commission and slippage
    results_with_costs = backtester.run_backtest(ma_strategy, historical_data)
    
    # Run backtest without costs
    backtester_no_costs = Backtester(
        initial_capital=100000.0,
        commission_pct=0.0,
        slippage_pct=0.0
    )
    results_no_costs = backtester_no_costs.run_backtest(ma_strategy, historical_data)
    
    # Results with costs should have lower P&L (if trades were made)
    if results_with_costs.total_trades > 0 and results_no_costs.total_trades > 0:
        assert results_with_costs.total_pnl <= results_no_costs.total_pnl


def test_equity_curve_generation(backtester, ma_strategy):
    """Test that equity curve is generated during backtest."""
    historical_data = {
        'TEST': generate_trending_data(100.0, 30, 'up')
    }
    
    results = backtester.run_backtest(ma_strategy, historical_data)
    
    # Equity curve should have entries
    assert len(backtester.equity_curve) > 0
    
    # First entry should be initial capital
    assert backtester.equity_curve[0][1] == backtester.initial_capital


def test_max_drawdown_calculation(backtester, ma_strategy):
    """Test maximum drawdown calculation."""
    # Generate data with a clear drawdown
    data = []
    base_date = datetime(2024, 1, 1)
    prices = [100, 105, 110, 115, 120, 115, 110, 105, 100, 95, 100, 105, 110]
    
    for i, price in enumerate(prices):
        candle = {
            'timestamp': base_date + timedelta(days=i),
            'open': price - 0.5,
            'high': price + 1,
            'low': price - 1,
            'close': price,
            'volume': 10000
        }
        data.append(candle)
    
    historical_data = {'TEST': data}
    
    results = backtester.run_backtest(ma_strategy, historical_data)
    
    # Max drawdown should be non-negative
    assert results.max_drawdown >= 0


def test_multiple_instruments_backtest(backtester):
    """Test backtesting with multiple instruments."""
    config = StrategyConfig(
        name="Multi_Instrument",
        enabled=True,
        instruments=["TEST1", "TEST2"],
        entry_conditions={},
        exit_conditions={},
        risk_params={},
        timeframe="day"
    )
    params = StrategyParameters()
    params.custom_params = {
        'short_period': 5,
        'long_period': 10,
        'ma_type': 'SMA'
    }
    strategy = MovingAverageCrossoverStrategy(config, params)
    
    historical_data = {
        'TEST1': generate_trending_data(100.0, 30, 'up'),
        'TEST2': generate_trending_data(200.0, 30, 'down')
    }
    
    results = backtester.run_backtest(strategy, historical_data)
    
    assert isinstance(results, BacktestResults)
    # Trades could be from either instrument
    if results.total_trades > 0:
        instruments = set(trade.instrument for trade in results.trades)
        assert len(instruments) <= 2
