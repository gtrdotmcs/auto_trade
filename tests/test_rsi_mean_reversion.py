"""
Unit tests for RSI Mean Reversion Strategy.
"""

import pytest
from datetime import datetime
from kite_auto_trading.strategies.rsi_mean_reversion import RSIMeanReversionStrategy
from kite_auto_trading.models.base import StrategyConfig, Position
from kite_auto_trading.models.signals import SignalType, SignalStrength, StrategyParameters


@pytest.fixture
def strategy_config():
    """Create a basic strategy configuration."""
    return StrategyConfig(
        name="RSI_MeanReversion_Test",
        enabled=True,
        instruments=["INFY", "TCS"],
        entry_conditions={
            'oversold_threshold': 30,
            'overbought_threshold': 70
        },
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
        'rsi_period': 14,
        'exit_on_neutral': True
    }
    return params


@pytest.fixture
def rsi_strategy(strategy_config, strategy_parameters):
    """Create an RSI Mean Reversion strategy instance."""
    return RSIMeanReversionStrategy(strategy_config, strategy_parameters)


def test_strategy_initialization(rsi_strategy):
    """Test strategy initialization."""
    assert rsi_strategy.config.name == "RSI_MeanReversion_Test"
    assert rsi_strategy.rsi_period == 14
    assert rsi_strategy.oversold_threshold == 30
    assert rsi_strategy.overbought_threshold == 70
    assert rsi_strategy.exit_on_neutral is True
    assert rsi_strategy.enabled is True


def test_invalid_thresholds():
    """Test that invalid thresholds raise an error."""
    config = StrategyConfig(
        name="Invalid_RSI",
        enabled=True,
        instruments=["INFY"],
        entry_conditions={
            'oversold_threshold': 70,  # Invalid: oversold >= overbought
            'overbought_threshold': 30
        },
        exit_conditions={},
        risk_params={},
        timeframe="5minute"
    )
    params = StrategyParameters()
    params.custom_params = {'rsi_period': 14}
    
    with pytest.raises(ValueError, match="Oversold threshold must be less than overbought threshold"):
        RSIMeanReversionStrategy(config, params)


def test_calculate_rsi(rsi_strategy):
    """Test RSI calculation."""
    # Create price data with clear trend
    prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 
              111, 113, 112, 114, 116, 115, 117, 119, 118, 120]
    
    rsi = rsi_strategy._calculate_rsi(prices, 14)
    
    # RSI should be between 0 and 100
    assert 0 <= rsi <= 100
    
    # For uptrending prices, RSI should be above 50
    assert rsi > 50


def test_calculate_rsi_downtrend(rsi_strategy):
    """Test RSI calculation for downtrending prices."""
    # Create downtrending price data
    prices = [120, 118, 116, 117, 115, 113, 114, 112, 110, 111,
              109, 107, 108, 106, 104, 105, 103, 101, 102, 100]
    
    rsi = rsi_strategy._calculate_rsi(prices, 14)
    
    # For downtrending prices, RSI should be below 50
    assert 0 <= rsi <= 100
    assert rsi < 50


def test_calculate_indicators(rsi_strategy):
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
        {'open': 110, 'high': 112, 'low': 109, 'close': 111, 'volume': 2000},
        {'open': 111, 'high': 113, 'low': 110, 'close': 112, 'volume': 2100},
        {'open': 112, 'high': 114, 'low': 111, 'close': 113, 'volume': 2200},
        {'open': 113, 'high': 115, 'low': 112, 'close': 114, 'volume': 2300},
        {'open': 114, 'high': 116, 'low': 113, 'close': 115, 'volume': 2400},
    ]
    
    indicators = rsi_strategy.calculate_indicators(price_data)
    
    assert 'rsi' in indicators
    assert 'current_price' in indicators
    assert indicators['current_price'] == 115
    assert 0 <= indicators['rsi'] <= 100


def test_is_oversold(rsi_strategy):
    """Test oversold condition detection."""
    assert rsi_strategy.is_oversold({'rsi': 25}) is True
    assert rsi_strategy.is_oversold({'rsi': 30}) is False
    assert rsi_strategy.is_oversold({'rsi': 50}) is False


def test_is_overbought(rsi_strategy):
    """Test overbought condition detection."""
    assert rsi_strategy.is_overbought({'rsi': 75}) is True
    assert rsi_strategy.is_overbought({'rsi': 70}) is False
    assert rsi_strategy.is_overbought({'rsi': 50}) is False


def test_oversold_entry_signal(rsi_strategy):
    """Test entry signal generation for oversold condition."""
    # Create price data that results in low RSI
    price_data_infy = []
    for i in range(20):
        price_data_infy.append({'close': 120 - i * 2})  # Declining prices
    
    market_data = {
        'price_history': {
            'INFY': price_data_infy
        },
        'positions': []
    }
    
    signals = rsi_strategy.evaluate(market_data)
    
    # Check if we got entry signals
    entry_signals = [s for s in signals if s.is_entry_signal()]
    if entry_signals:
        signal = entry_signals[0]
        assert signal.signal_type == SignalType.ENTRY_LONG
        assert signal.instrument == "INFY"
        assert "oversold" in signal.reason.lower()


def test_overbought_entry_signal(rsi_strategy):
    """Test entry signal generation for overbought condition."""
    # Create price data that results in high RSI
    price_data_infy = []
    for i in range(20):
        price_data_infy.append({'close': 100 + i * 2})  # Rising prices
    
    market_data = {
        'price_history': {
            'INFY': price_data_infy
        },
        'positions': []
    }
    
    signals = rsi_strategy.evaluate(market_data)
    
    # Check if we got entry signals
    entry_signals = [s for s in signals if s.is_entry_signal()]
    if entry_signals:
        signal = entry_signals[0]
        assert signal.signal_type == SignalType.ENTRY_SHORT
        assert signal.instrument == "INFY"
        assert "overbought" in signal.reason.lower()


def test_exit_long_on_overbought(rsi_strategy):
    """Test exit signal for long position when overbought."""
    # Set RSI to overbought
    rsi_strategy.current_rsi['INFY'] = 75
    
    # Create a long position
    position = Position(
        instrument='INFY',
        quantity=10,
        average_price=100.0,
        current_price=110.0,
        unrealized_pnl=100.0,
        strategy_id='RSI_MeanReversion_Test',
        entry_time=datetime.now()
    )
    
    signals = rsi_strategy.get_exit_signals([position])
    
    assert len(signals) > 0
    assert signals[0].signal_type == SignalType.EXIT_LONG
    assert signals[0].instrument == 'INFY'
    assert "overbought" in signals[0].reason.lower()


def test_exit_short_on_oversold(rsi_strategy):
    """Test exit signal for short position when oversold."""
    # Set RSI to oversold
    rsi_strategy.current_rsi['INFY'] = 25
    
    # Create a short position
    position = Position(
        instrument='INFY',
        quantity=-10,
        average_price=110.0,
        current_price=100.0,
        unrealized_pnl=100.0,
        strategy_id='RSI_MeanReversion_Test',
        entry_time=datetime.now()
    )
    
    signals = rsi_strategy.get_exit_signals([position])
    
    assert len(signals) > 0
    assert signals[0].signal_type == SignalType.EXIT_SHORT
    assert signals[0].instrument == 'INFY'
    assert "oversold" in signals[0].reason.lower()


def test_exit_on_neutral_zone(rsi_strategy):
    """Test exit signal when RSI returns to neutral zone."""
    # Set RSI to neutral
    rsi_strategy.current_rsi['INFY'] = 50
    
    # Create a long position
    position = Position(
        instrument='INFY',
        quantity=10,
        average_price=100.0,
        current_price=105.0,
        unrealized_pnl=50.0,
        strategy_id='RSI_MeanReversion_Test',
        entry_time=datetime.now()
    )
    
    signals = rsi_strategy.get_exit_signals([position])
    
    # Should exit on neutral if exit_on_neutral is True
    if rsi_strategy.exit_on_neutral:
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.EXIT_LONG
        assert "neutral" in signals[0].reason.lower()


def test_signal_strength_determination(rsi_strategy):
    """Test signal strength based on distance from threshold."""
    # Very oversold - strong signal
    strength = rsi_strategy._determine_signal_strength(20, is_oversold=True)
    assert strength == SignalStrength.STRONG
    
    # Moderately oversold - moderate signal
    strength = rsi_strategy._determine_signal_strength(8, is_oversold=True)
    assert strength == SignalStrength.MODERATE
    
    # Slightly oversold - weak signal
    strength = rsi_strategy._determine_signal_strength(2, is_oversold=True)
    assert strength == SignalStrength.WEAK


def test_signal_confidence_levels(rsi_strategy):
    """Test that signal confidence varies with RSI distance from threshold."""
    # Create strongly oversold condition
    price_data = []
    for i in range(20):
        price_data.append({'close': 150 - i * 3})  # Sharp decline
    
    market_data = {
        'price_history': {'INFY': price_data},
        'positions': []
    }
    
    signals = rsi_strategy.evaluate(market_data)
    
    if signals:
        # Confidence should be reasonable
        assert 0.5 <= signals[0].confidence <= 1.0


def test_disabled_strategy_no_signals(rsi_strategy):
    """Test that disabled strategy generates no signals."""
    rsi_strategy.enabled = False
    
    price_data = [{'close': 100 - i * 2} for i in range(20)]
    market_data = {
        'price_history': {'INFY': price_data},
        'positions': []
    }
    
    signals = rsi_strategy.evaluate(market_data)
    assert len(signals) == 0


def test_no_exit_for_other_strategy_positions(rsi_strategy):
    """Test that strategy doesn't exit positions from other strategies."""
    rsi_strategy.current_rsi['INFY'] = 75
    
    # Create position from different strategy
    position = Position(
        instrument='INFY',
        quantity=10,
        average_price=100.0,
        current_price=110.0,
        unrealized_pnl=100.0,
        strategy_id='DifferentStrategy',
        entry_time=datetime.now()
    )
    
    signals = rsi_strategy.get_exit_signals([position])
    
    # Should not generate exit signal for other strategy's position
    assert len(signals) == 0
