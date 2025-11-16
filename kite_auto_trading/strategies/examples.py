"""
Example usage of trading strategies and backtesting framework.

This module demonstrates how to create, configure, and backtest trading strategies.
"""

from datetime import datetime, timedelta
from typing import List, Dict
from kite_auto_trading.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from kite_auto_trading.strategies.rsi_mean_reversion import RSIMeanReversionStrategy
from kite_auto_trading.strategies.backtesting import Backtester
from kite_auto_trading.models.base import StrategyConfig
from kite_auto_trading.models.signals import StrategyParameters


def create_ma_crossover_strategy() -> MovingAverageCrossoverStrategy:
    """
    Create a Moving Average Crossover strategy.
    
    This strategy generates buy signals when the short-term MA crosses above
    the long-term MA, and sell signals when it crosses below.
    
    Returns:
        Configured MovingAverageCrossoverStrategy instance
    """
    config = StrategyConfig(
        name="MA_Crossover_10_20",
        enabled=True,
        instruments=["INFY", "TCS", "RELIANCE"],
        entry_conditions={'trend_strength': 0.7},
        exit_conditions={},
        risk_params={},
        timeframe="5minute"
    )
    
    parameters = StrategyParameters(
        lookback_period=20,
        min_confidence=0.6,
        stop_loss_pct=2.0,
        take_profit_pct=5.0
    )
    
    # Set strategy-specific parameters
    parameters.custom_params = {
        'short_period': 10,
        'long_period': 20,
        'ma_type': 'SMA'  # or 'EMA' for exponential moving average
    }
    
    return MovingAverageCrossoverStrategy(config, parameters)


def create_rsi_strategy() -> RSIMeanReversionStrategy:
    """
    Create an RSI Mean Reversion strategy.
    
    This strategy generates buy signals when RSI indicates oversold conditions
    and sell signals when RSI indicates overbought conditions.
    
    Returns:
        Configured RSIMeanReversionStrategy instance
    """
    config = StrategyConfig(
        name="RSI_MeanReversion_14",
        enabled=True,
        instruments=["INFY", "TCS", "RELIANCE"],
        entry_conditions={
            'oversold_threshold': 30,
            'overbought_threshold': 70
        },
        exit_conditions={},
        risk_params={},
        timeframe="5minute"
    )
    
    parameters = StrategyParameters(
        lookback_period=20,
        min_confidence=0.6,
        stop_loss_pct=2.0,
        take_profit_pct=5.0
    )
    
    # Set strategy-specific parameters
    parameters.custom_params = {
        'rsi_period': 14,
        'exit_on_neutral': True  # Exit when RSI returns to neutral zone
    }
    
    return RSIMeanReversionStrategy(config, parameters)


def generate_sample_historical_data(
    instrument: str,
    num_days: int = 60,
    start_price: float = 1000.0
) -> List[Dict]:
    """
    Generate sample historical data for testing.
    
    Args:
        instrument: Trading symbol
        num_days: Number of days of data to generate
        start_price: Starting price
        
    Returns:
        List of OHLC candles
    """
    data = []
    base_date = datetime.now() - timedelta(days=num_days)
    price = start_price
    
    for i in range(num_days):
        # Simulate price movement
        change = ((i % 5) - 2) * 2.0  # Creates some volatility
        price += change
        
        candle = {
            'timestamp': base_date + timedelta(days=i),
            'open': price - 1.0,
            'high': price + 2.0,
            'low': price - 2.0,
            'close': price,
            'volume': 100000 + (i * 1000)
        }
        data.append(candle)
    
    return data


def run_backtest_example():
    """
    Example of running a backtest on a strategy.
    
    This demonstrates how to:
    1. Create a strategy
    2. Prepare historical data
    3. Run a backtest
    4. Analyze results
    """
    # Create strategy
    strategy = create_ma_crossover_strategy()
    
    # Prepare historical data
    historical_data = {
        'INFY': generate_sample_historical_data('INFY', 60, 1500.0),
        'TCS': generate_sample_historical_data('TCS', 60, 3500.0),
        'RELIANCE': generate_sample_historical_data('RELIANCE', 60, 2500.0)
    }
    
    # Create backtester
    backtester = Backtester(
        initial_capital=100000.0,
        commission_pct=0.1,  # 0.1% commission
        slippage_pct=0.05    # 0.05% slippage
    )
    
    # Run backtest
    results = backtester.run_backtest(strategy, historical_data)
    
    # Print results
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    
    summary = results.summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key:20s}: {value:,.2f}")
        else:
            print(f"{key:20s}: {value}")
    
    print("\n" + "="*60)
    print(f"TRADE DETAILS ({len(results.trades)} trades)")
    print("="*60)
    
    for i, trade in enumerate(results.trades[:10], 1):  # Show first 10 trades
        print(f"\nTrade {i}:")
        print(f"  Instrument: {trade.instrument}")
        print(f"  Entry: {trade.entry_price:.2f} @ {trade.entry_time.date()}")
        print(f"  Exit: {trade.exit_price:.2f} @ {trade.exit_time.date()}")
        print(f"  P&L: {trade.pnl:.2f} ({trade.pnl_pct:.2f}%)")
        print(f"  Result: {'WIN' if trade.is_winning_trade() else 'LOSS'}")
    
    if len(results.trades) > 10:
        print(f"\n... and {len(results.trades) - 10} more trades")
    
    return results


def compare_strategies_example():
    """
    Example of comparing multiple strategies.
    
    This demonstrates how to backtest multiple strategies on the same data
    and compare their performance.
    """
    # Create strategies
    ma_strategy = create_ma_crossover_strategy()
    rsi_strategy = create_rsi_strategy()
    
    # Prepare historical data
    historical_data = {
        'INFY': generate_sample_historical_data('INFY', 90, 1500.0),
    }
    
    # Create backtester
    backtester = Backtester(initial_capital=100000.0)
    
    # Run backtests
    ma_results = backtester.run_backtest(ma_strategy, historical_data)
    
    # Reset backtester for second strategy
    backtester = Backtester(initial_capital=100000.0)
    rsi_results = backtester.run_backtest(rsi_strategy, historical_data)
    
    # Compare results
    print("\n" + "="*60)
    print("STRATEGY COMPARISON")
    print("="*60)
    
    print(f"\n{'Metric':<25} {'MA Crossover':<20} {'RSI Mean Rev':<20}")
    print("-" * 60)
    
    metrics = [
        ('Total Trades', 'total_trades'),
        ('Win Rate (%)', 'win_rate'),
        ('Total P&L', 'total_pnl'),
        ('Total P&L (%)', 'total_pnl_pct'),
        ('Profit Factor', 'profit_factor'),
        ('Max Drawdown (%)', 'max_drawdown'),
        ('Sharpe Ratio', 'sharpe_ratio'),
    ]
    
    for label, key in metrics:
        ma_val = getattr(ma_results, key)
        rsi_val = getattr(rsi_results, key)
        
        if isinstance(ma_val, float):
            print(f"{label:<25} {ma_val:<20.2f} {rsi_val:<20.2f}")
        else:
            print(f"{label:<25} {ma_val:<20} {rsi_val:<20}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    # Run examples
    print("Running backtest example...")
    run_backtest_example()
    
    print("\n\nComparing strategies...")
    compare_strategies_example()
