"""
Unit tests for strategy base classes and signal generation.
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List

from kite_auto_trading.models import (
    StrategyConfig,
    RiskParameters,
    Position,
    TradingSignal,
    SignalType,
    SignalStrength,
    StrategyParameters,
)
from kite_auto_trading.strategies import (
    StrategyBase,
    TechnicalStrategy,
    StrategyManager,
)


class MockStrategy(StrategyBase):
    """Mock strategy for testing."""
    
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """Generate mock entry signals."""
        signals = []
        for instrument in self.config.instruments:
            price = market_data.get('prices', {}).get(instrument, 100.0)
            signal = TradingSignal(
                signal_type=SignalType.ENTRY_LONG,
                instrument=instrument,
                timestamp=datetime.now(),
                price=price,
                strength=SignalStrength.MODERATE,
                strategy_name=self.config.name,
                reason="Mock entry signal",
                confidence=0.7
            )
            signals.append(signal)
        return signals
    
    def get_exit_signals(self, positions: List[Position]) -> List[TradingSignal]:
        """Generate mock exit signals."""
        signals = []
        for position in positions:
            signal = TradingSignal(
                signal_type=SignalType.EXIT_LONG,
                instrument=position.instrument,
                timestamp=datetime.now(),
                price=position.current_price,
                strength=SignalStrength.WEAK,
                strategy_name=self.config.name,
                reason="Mock exit signal",
                confidence=0.6
            )
            signals.append(signal)
        return signals


class MockTechnicalStrategy(TechnicalStrategy):
    """Mock technical strategy for testing."""
    
    def calculate_indicators(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate mock indicators."""
        return {'sma': 100.0, 'rsi': 50.0}
    
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """Generate mock entry signals."""
        return []
    
    def get_exit_signals(self, positions: List[Position]) -> List[TradingSignal]:
        """Generate mock exit signals."""
        return []


@pytest.fixture
def strategy_config():
    """Create a test strategy configuration."""
    risk_params = RiskParameters(
        max_position_size=10000.0,
        stop_loss_percentage=2.0,
        target_profit_percentage=5.0,
        daily_loss_limit=5000.0,
        max_positions_per_instrument=2
    )
    
    return StrategyConfig(
        name="TestStrategy",
        enabled=True,
        instruments=["INFY", "TCS"],
        entry_conditions={'threshold': 0.5},
        exit_conditions={'stop_loss': 2.0},
        risk_params=risk_params,
        timeframe="5minute"
    )


@pytest.fixture
def strategy_parameters():
    """Create test strategy parameters."""
    return StrategyParameters(
        lookback_period=20,
        entry_threshold=0.5,
        exit_threshold=0.3,
        stop_loss_pct=2.0,
        take_profit_pct=5.0,
        min_confidence=0.5
    )


class TestStrategyParameters:
    """Test StrategyParameters class."""
    
    def test_parameters_creation(self):
        """Test creating strategy parameters."""
        params = StrategyParameters(
            lookback_period=30,
            entry_threshold=0.7,
            min_confidence=0.6
        )
        
        assert params.lookback_period == 30
        assert params.entry_threshold == 0.7
        assert params.min_confidence == 0.6
    
    def test_parameters_validation(self):
        """Test parameter validation."""
        with pytest.raises(ValueError):
            StrategyParameters(lookback_period=0)
        
        with pytest.raises(ValueError):
            StrategyParameters(stop_loss_pct=-1.0)
        
        with pytest.raises(ValueError):
            StrategyParameters(min_confidence=1.5)
    
    def test_custom_parameters(self):
        """Test custom parameter management."""
        params = StrategyParameters()
        params.set_param('custom_value', 42)
        
        assert params.get_param('custom_value') == 42
        assert params.get_param('nonexistent', 'default') == 'default'
    
    def test_parameters_to_dict(self):
        """Test converting parameters to dictionary."""
        params = StrategyParameters(lookback_period=25)
        params_dict = params.to_dict()
        
        assert params_dict['lookback_period'] == 25
        assert 'entry_threshold' in params_dict


class TestTradingSignal:
    """Test TradingSignal class."""
    
    def test_signal_creation(self):
        """Test creating a trading signal."""
        signal = TradingSignal(
            signal_type=SignalType.ENTRY_LONG,
            instrument="INFY",
            timestamp=datetime.now(),
            price=1500.0,
            strength=SignalStrength.STRONG,
            strategy_name="TestStrategy",
            reason="Price breakout",
            confidence=0.8
        )
        
        assert signal.instrument == "INFY"
        assert signal.price == 1500.0
        assert signal.confidence == 0.8
    
    def test_signal_validation(self):
        """Test signal validation."""
        with pytest.raises(ValueError):
            TradingSignal(
                signal_type=SignalType.ENTRY_LONG,
                instrument="INFY",
                timestamp=datetime.now(),
                price=-100.0,  # Invalid price
                strength=SignalStrength.STRONG,
                strategy_name="TestStrategy"
            )
        
        with pytest.raises(ValueError):
            TradingSignal(
                signal_type=SignalType.ENTRY_LONG,
                instrument="",  # Empty instrument
                timestamp=datetime.now(),
                price=100.0,
                strength=SignalStrength.STRONG,
                strategy_name="TestStrategy"
            )
    
    def test_signal_type_checks(self):
        """Test signal type checking methods."""
        entry_signal = TradingSignal(
            signal_type=SignalType.ENTRY_LONG,
            instrument="INFY",
            timestamp=datetime.now(),
            price=1500.0,
            strength=SignalStrength.STRONG,
            strategy_name="TestStrategy"
        )
        
        assert entry_signal.is_entry_signal()
        assert not entry_signal.is_exit_signal()
        assert entry_signal.is_long_signal()
        
        exit_signal = TradingSignal(
            signal_type=SignalType.EXIT_LONG,
            instrument="INFY",
            timestamp=datetime.now(),
            price=1550.0,
            strength=SignalStrength.MODERATE,
            strategy_name="TestStrategy"
        )
        
        assert exit_signal.is_exit_signal()
        assert not exit_signal.is_entry_signal()
    
    def test_signal_to_dict(self):
        """Test converting signal to dictionary."""
        signal = TradingSignal(
            signal_type=SignalType.ENTRY_LONG,
            instrument="INFY",
            timestamp=datetime.now(),
            price=1500.0,
            strength=SignalStrength.STRONG,
            strategy_name="TestStrategy"
        )
        
        signal_dict = signal.to_dict()
        assert signal_dict['instrument'] == "INFY"
        assert signal_dict['price'] == 1500.0
        assert signal_dict['signal_type'] == SignalType.ENTRY_LONG.value


class TestStrategyBase:
    """Test StrategyBase class."""
    
    def test_strategy_initialization(self, strategy_config, strategy_parameters):
        """Test strategy initialization."""
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        assert strategy.config.name == "TestStrategy"
        assert strategy.enabled is True
        assert strategy.parameters.lookback_period == 20
    
    def test_strategy_evaluation(self, strategy_config, strategy_parameters):
        """Test strategy evaluation."""
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        market_data = {
            'prices': {'INFY': 1500.0, 'TCS': 3500.0},
            'positions': []
        }
        
        signals = strategy.evaluate(market_data)
        
        assert len(signals) == 2
        assert all(isinstance(s, TradingSignal) for s in signals)
        assert signals[0].instrument in ['INFY', 'TCS']
    
    def test_strategy_disabled(self, strategy_config, strategy_parameters):
        """Test that disabled strategy returns no signals."""
        strategy_config.enabled = False
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        market_data = {'prices': {'INFY': 1500.0}, 'positions': []}
        signals = strategy.evaluate(market_data)
        
        assert len(signals) == 0
    
    def test_signal_confidence_filtering(self, strategy_config):
        """Test that signals below minimum confidence are filtered."""
        params = StrategyParameters(min_confidence=0.8)
        strategy = MockStrategy(strategy_config, params)
        
        market_data = {'prices': {'INFY': 1500.0}, 'positions': []}
        signals = strategy.evaluate(market_data)
        
        # Mock strategy generates signals with 0.7 confidence
        # Should be filtered out with min_confidence=0.8
        assert len(signals) == 0
    
    def test_signal_history(self, strategy_config, strategy_parameters):
        """Test signal history tracking."""
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        market_data = {'prices': {'INFY': 1500.0}, 'positions': []}
        strategy.evaluate(market_data)
        
        history = strategy.get_recent_signals(10)
        assert len(history) > 0
        
        strategy.reset_signal_history()
        history = strategy.get_recent_signals(10)
        assert len(history) == 0
    
    def test_parameter_update(self, strategy_config, strategy_parameters):
        """Test updating strategy parameters."""
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        new_params = StrategyParameters(lookback_period=50)
        strategy.update_parameters(new_params)
        
        assert strategy.get_parameters().lookback_period == 50


class TestTechnicalStrategy:
    """Test TechnicalStrategy class."""
    
    def test_technical_strategy_initialization(self, strategy_config, strategy_parameters):
        """Test technical strategy initialization."""
        strategy = MockTechnicalStrategy(strategy_config, strategy_parameters)
        
        assert strategy.lookback_period == 20
        assert hasattr(strategy, 'calculate_indicators')
    
    def test_create_signal_helper(self, strategy_config, strategy_parameters):
        """Test signal creation helper method."""
        strategy = MockTechnicalStrategy(strategy_config, strategy_parameters)
        
        signal = strategy._create_signal(
            signal_type=SignalType.ENTRY_LONG,
            instrument="INFY",
            price=1500.0,
            strength=SignalStrength.STRONG,
            reason="Test signal",
            confidence=0.9
        )
        
        assert signal.instrument == "INFY"
        assert signal.price == 1500.0
        assert signal.strategy_name == "TestStrategy"
        assert signal.confidence == 0.9


class TestStrategyManager:
    """Test StrategyManager class."""
    
    def test_manager_initialization(self):
        """Test strategy manager initialization."""
        manager = StrategyManager()
        
        assert len(manager.strategies) == 0
        assert len(manager.enabled_strategies) == 0
    
    def test_register_strategy(self, strategy_config, strategy_parameters):
        """Test registering a strategy."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        
        manager.register_strategy(strategy)
        
        assert "TestStrategy" in manager.strategies
        assert "TestStrategy" in manager.enabled_strategies
    
    def test_enable_disable_strategy(self, strategy_config, strategy_parameters):
        """Test enabling and disabling strategies."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy)
        
        # Disable strategy
        result = manager.disable_strategy("TestStrategy")
        assert result is True
        assert not manager.is_strategy_enabled("TestStrategy")
        
        # Enable strategy
        result = manager.enable_strategy("TestStrategy")
        assert result is True
        assert manager.is_strategy_enabled("TestStrategy")
    
    def test_unregister_strategy(self, strategy_config, strategy_parameters):
        """Test unregistering a strategy."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy)
        
        result = manager.unregister_strategy("TestStrategy")
        assert result is True
        assert "TestStrategy" not in manager.strategies
    
    def test_evaluate_all_strategies(self, strategy_config, strategy_parameters):
        """Test evaluating all strategies."""
        manager = StrategyManager()
        
        # Register multiple strategies
        strategy1 = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy1)
        
        config2 = StrategyConfig(
            name="TestStrategy2",
            enabled=True,
            instruments=["RELIANCE"],
            entry_conditions={},
            exit_conditions={},
            risk_params=strategy_config.risk_params,
            timeframe="5minute"
        )
        strategy2 = MockStrategy(config2, strategy_parameters)
        manager.register_strategy(strategy2)
        
        market_data = {
            'prices': {'INFY': 1500.0, 'TCS': 3500.0, 'RELIANCE': 2500.0},
            'positions': []
        }
        
        signals = manager.evaluate_all_strategies(market_data)
        
        # Should get signals from both strategies
        assert len(signals) > 0
        assert any(s.instrument == "RELIANCE" for s in signals)
    
    def test_evaluate_specific_strategy(self, strategy_config, strategy_parameters):
        """Test evaluating a specific strategy."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy)
        
        market_data = {'prices': {'INFY': 1500.0}, 'positions': []}
        signals = manager.evaluate_strategy("TestStrategy", market_data)
        
        assert len(signals) > 0
    
    def test_get_strategy_stats(self, strategy_config, strategy_parameters):
        """Test getting strategy statistics."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy)
        
        market_data = {'prices': {'INFY': 1500.0}, 'positions': []}
        manager.evaluate_all_strategies(market_data)
        
        stats = manager.get_strategy_stats()
        
        assert "TestStrategy" in stats
        assert stats["TestStrategy"]["evaluations"] == 1
        assert stats["TestStrategy"]["errors"] == 0
        assert stats["TestStrategy"]["enabled"] is True
    
    def test_get_strategies(self, strategy_config, strategy_parameters):
        """Test getting strategies."""
        manager = StrategyManager()
        strategy = MockStrategy(strategy_config, strategy_parameters)
        manager.register_strategy(strategy)
        
        # Get specific strategy
        retrieved = manager.get_strategy("TestStrategy")
        assert retrieved is not None
        assert retrieved.config.name == "TestStrategy"
        
        # Get all strategies
        all_strategies = manager.get_all_strategies()
        assert len(all_strategies) == 1
        
        # Get enabled strategies
        enabled = manager.get_enabled_strategies()
        assert len(enabled) == 1
