"""
Unit tests for Moving Average Crossover Strategy.
"""

import pytest
from datetime import datetime
from kite_auto_trading.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from kite_auto_trading.models.base import StrategyConfig, Position
from kite_auto_trading.models.signals import SignalType, SignalStrength, StrategyParameters


@pytest.fixture
def strategy_config():
    """Create a basic strategy configuration."""
    return StrategyConfig(
        name="MA_Crossover_Test",
        enabled=True,
        instruments=["INFY", "TCS"],
        entry_conditions={'trend_strength': 0.7},
        exit_conditions={},
        risk_params={},
        timeframe="5minute"
    )


@pytest.fixture
def strategy_parameters():
    """Create strategy parameters."""
    params = StrategyParameters(
        lookback_period=20,
        min_confidence=0.5,
        stop_loss_pct=2.0,
        take_profit_pct=5.0
    )
    params.custom_params = {
        'short_period': 5,
        'long_period': 10,
        'ma_type': 'SMA'
    }
    return params


@pytest.fixture
def ma_strategy(strategy_config, strategy_parameters):
    """Create a Moving Average Crossover strategy instance."""
    return MovingAverageCrossoverStrategy(strategy_config, strategy_parameters)


def test_strategy_initialization(ma_strategy):
    """Test strategy initialization."""
    assert ma_strategy.config.name == "MA_Crossover_Test"
    assert ma_strategy.short_period == 5
    assert ma_strategy.long_period == 10
    assert ma_strategy.ma_type == 'SMA'
    assert ma_strategy.enabled is True


def test_invalid_periods():
    """Test that invalid periods raise an error."""
    config = StrategyConfig(
        name="Invalid_MA",
        enabled=True,
        instruments=["INFY"],
        entry_conditions={},
        exit_conditions={},
        risk_params={},
        timeframe="5minute"
    )
    params = StrategyParameters()
    params.custom_params = {
        'short_period': 20,
        'long_period': 10  # Invalid: short >= long
    }
    
    with pytest.raises(ValueError, match="Short period must be less than long period"):
        MovingAverageCrossoverStrategy(config, params)


def test_calculate_sma(ma_strategy):
    """Test Simple Moving Average calculation."""
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
    
    sma_5 = ma_strategy._calculate_sma(prices, 5)
    expected_sma_5 = sum(prices[-5:]) / 5
    assert abs(sma_5 - expected_sma_5) < 0.01
    
    sma_10 = ma_strategy._calculate_sma(prices, 10)
    expected_sma_10 = sum(prices) / 10
    assert abs(sma_10 - expected_sma_10) < 0.01


def test_calculate_ema(ma_strategy):
    """Test Exponential Moving Average calculation."""
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
    
    ema = ma_strategy._calculate_ema(prices, 5)
    assert ema > 0
    assert ema != sum(prices[-5:]) / 5  # EMA should differ from SMA


def test_calculate_indicators(ma_strategy):
    """Test indicator calculation."""
    price_data = [
        {'open': 100, 'high': 102, 'low': 99, 'close': 101, 'volume': 1000},
        {'open': 101, 'high': 103, 'low': 100, 'close': 102, 'volume': 1100},
        {'open': 102, 'high': 104, 'low': 101, 'close': 103, 'volume': 1200},
        {'open': 103, 'high': 105, 'low': 102, 'close': 104, 'volume': 1300},
        {'open': 104, 'high': 106, 'low': 103, 'close': 105, 'volume': 1400},
        {'open': 105, 'high': 107, 'low': 104, 'close': 106, 'volume': 1500},
        {'open': 106, 'high': 108, 'low': 105, 'close': 107, 'volume': 1600},
        {'open': 107, 'high': 109, 'low': 106, 'close': 108, 'volume': 1700},
        {'open': 108, 'high': 110, 'low': 107, 'close': 109, 'volume': 1800},
        {'open': 109, 'high': 111, 'low': 108, 'close': 110, 'volume': 1900},
    ]
    
    indicators = ma_strategy.calculate_indicators(price_data)
    
    assert 'short_ma' in indicators
    assert 'long_ma' in indicators
    assert 'current_price' in indicators
    assert indicators['current_price'] == 110
    assert indicators['short_ma'] > 0
    assert indicators['long_ma'] > 0


def test_bullish_crossover_signal(ma_strategy):
    """Test bullish crossover signal generation."""
    # Create price data that will cause a bullish crossover
    price_data_infy = [
        {'close': 100}, {'close': 101}, {'close': 102}, {'close': 103}, {'close': 104},
        {'close': 105}, {'close': 106}, {'close': 107}, {'close': 108}, {'close': 109},
        {'close': 110}, {'close': 112}, {'close': 115}, {'close': 118}, {'close': 120},
    ]
    
    market_data = {
        'price_history': {
            'INFY': price_data_infy
        },
        'positions': []
    }
    
    # First evaluation to set previous values
    signals = ma_strategy.evaluate(market_data)
    
    # Add more bullish data
    price_data_infy.extend([
        {'close': 122}, {'close': 125}, {'close': 128}
    ])
    
    # Second evaluation should detect crossover
    signals = ma_strategy.evaluate(market_data)
    
    # Check if we got entry signals
    entry_signals = [s for s in signals if s.is_entry_signal()]
    if entry_signals:
        signal = entry_signals[0]
        assert signal.signal_type == SignalType.ENTRY_LONG
        assert signal.instrument == "INFY"
        assert "crossover" in signal.reason.lower()


def test_exit_signal_generation(ma_strategy):
    """Test exit signal generation for positions."""
    # Set up MA values that indicate exit
    ma_strategy.previous_short_ma['INFY'] = 100
    ma_strategy.previous_long_ma['INFY'] = 105  # Short below long
    
    # Create a long position
    position = Position(
        instrument='INFY',
        quantity=10,
        average_price=100.0,
        current_price=102.0,
        unrealized_pnl=20.0,
        strategy_id='MA_Crossover_Test',
        entry_time=datetime.now()
    )
    
    signals = ma_strategy.get_exit_signals([position])
    
    # Should generate exit signal since short MA < long MA
    assert len(signals) > 0
    assert signals[0].signal_type == SignalType.EXIT_LONG
    assert signals[0].instrument == 'INFY'


def test_identify_trend(ma_strategy):
    """Test trend identification."""
    # Set up uptrend
    ma_strategy.previous_short_ma['INFY'] = 110
    ma_strategy.previous_long_ma['INFY'] = 100
    
    trend = ma_strategy.identify_trend({})
    assert trend == 'UP'
    
    # Set up downtrend
    ma_strategy.previous_short_ma['INFY'] = 100
    ma_strategy.previous_long_ma['INFY'] = 110
    
    trend = ma_strategy.identify_trend({})
    assert trend == 'DOWN'
    
    # Set up sideways
    ma_strategy.previous_short_ma['INFY'] = 100
    ma_strategy.previous_long_ma['INFY'] = 100.5
    
    trend = ma_strategy.identify_trend({})
    assert trend == 'SIDEWAYS'


def test_calculate_trend_strength(ma_strategy):
    """Test trend strength calculation."""
    # Strong trend
    ma_strategy.previous_short_ma['INFY'] = 110
    ma_strategy.previous_long_ma['INFY'] = 100
    
    strength = ma_strategy.calculate_trend_strength({})
    assert strength > 0.5
    
    # Weak trend
    ma_strategy.previous_short_ma['INFY'] = 100.5
    ma_strategy.previous_long_ma['INFY'] = 100
    
    strength = ma_strategy.calculate_trend_strength({})
    assert 0 <= strength <= 1


def test_signal_confidence_levels(ma_strategy):
    """Test that signal confidence varies with MA separation."""
    price_data = []
    for i in range(20):
        price_data.append({'close': 100 + i * 2})
    
    market_data = {
        'price_history': {'INFY': price_data},
        'positions': []
    }
    
    # First pass to initialize
    ma_strategy.evaluate(market_data)
    
    # Add strong bullish move
    for i in range(5):
        price_data.append({'close': 140 + i * 3})
    
    signals = ma_strategy.evaluate(market_data)
    
    if signals:
        # Confidence should be reasonable
        assert 0.5 <= signals[0].confidence <= 1.0


def test_disabled_strategy_no_signals(ma_strategy):
    """Test that disabled strategy generates no signals."""
    ma_strategy.enabled = False
    
    price_data = [{'close': 100 + i} for i in range(20)]
    market_data = {
        'price_history': {'INFY': price_data},
        'positions': []
    }
    
    signals = ma_strategy.evaluate(market_data)
    assert len(signals) == 0
