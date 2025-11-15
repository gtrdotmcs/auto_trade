"""
Unit tests for strategy evaluation engine and condition evaluation.
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
    StrategyManager,
    Condition,
    CompositeCondition,
    ConditionOperator,
    ConditionEvaluator,
    create_price_condition,
    create_indicator_condition,
    create_volume_condition,
)


class TestCondition:
    """Test Condition class."""
    
    def test_condition_creation(self):
        """Test creating a condition."""
        condition = Condition(
            field='price',
            operator=ConditionOperator.GREATER_THAN,
            value=1500.0,
            description="Price above 1500"
        )
        
        assert condition.field == 'price'
        assert condition.operator == ConditionOperator.GREATER_THAN
        assert condition.value == 1500.0
    
    def test_greater_than_condition(self):
        """Test greater than condition evaluation."""
        condition = Condition(
            field='price',
            operator=ConditionOperator.GREATER_THAN,
            value=1500.0
        )
        
        assert condition.evaluate({'price': 1600.0}) is True
        assert condition.evaluate({'price': 1400.0}) is False
        assert condition.evaluate({'price': 1500.0}) is False
    
    def test_less_than_condition(self):
        """Test less than condition evaluation."""
        condition = Condition(
            field='rsi',
            operator=ConditionOperator.LESS_THAN,
            value=30.0
        )
        
        assert condition.evaluate({'rsi': 25.0}) is True
        assert condition.evaluate({'rsi': 35.0}) is False
    
    def test_equal_condition(self):
        """Test equal condition evaluation."""
        condition = Condition(
            field='signal',
            operator=ConditionOperator.EQUAL,
            value='BUY'
        )
        
        assert condition.evaluate({'signal': 'BUY'}) is True
        assert condition.evaluate({'signal': 'SELL'}) is False
    
    def test_crosses_above_condition(self):
        """Test crosses above condition evaluation."""
        condition = Condition(
            field='price',
            operator=ConditionOperator.CROSSES_ABOVE,
            value=1500.0
        )
        
        # Price crosses above threshold
        assert condition.evaluate(
            {'price': 1510.0},
            {'price': 1490.0}
        ) is True
        
        # Price already above threshold
        assert condition.evaluate(
            {'price': 1510.0},
            {'price': 1505.0}
        ) is False
        
        # Price below threshold
        assert condition.evaluate(
            {'price': 1490.0},
            {'price': 1480.0}
        ) is False
    
    def test_crosses_below_condition(self):
        """Test crosses below condition evaluation."""
        condition = Condition(
            field='rsi',
            operator=ConditionOperator.CROSSES_BELOW,
            value=70.0
        )
        
        # RSI crosses below threshold
        assert condition.evaluate(
            {'rsi': 65.0},
            {'rsi': 75.0}
        ) is True
        
        # RSI already below threshold
        assert condition.evaluate(
            {'rsi': 65.0},
            {'rsi': 68.0}
        ) is False
    
    def test_missing_field(self):
        """Test condition with missing field."""
        condition = Condition(
            field='volume',
            operator=ConditionOperator.GREATER_THAN,
            value=1000000
        )
        
        assert condition.evaluate({'price': 1500.0}) is False


class TestCompositeCondition:
    """Test CompositeCondition class."""
    
    def test_and_condition(self):
        """Test AND composite condition."""
        conditions = [
            Condition('price', ConditionOperator.GREATER_THAN, 1500.0),
            Condition('volume', ConditionOperator.GREATER_THAN, 1000000),
        ]
        
        composite = CompositeCondition(
            conditions=conditions,
            operator=ConditionOperator.AND,
            description="Price and volume conditions"
        )
        
        # Both conditions met
        assert composite.evaluate({
            'price': 1600.0,
            'volume': 1500000
        }) is True
        
        # Only one condition met
        assert composite.evaluate({
            'price': 1600.0,
            'volume': 500000
        }) is False
        
        # No conditions met
        assert composite.evaluate({
            'price': 1400.0,
            'volume': 500000
        }) is False
    
    def test_or_condition(self):
        """Test OR composite condition."""
        conditions = [
            Condition('rsi', ConditionOperator.LESS_THAN, 30.0),
            Condition('rsi', ConditionOperator.GREATER_THAN, 70.0),
        ]
        
        composite = CompositeCondition(
            conditions=conditions,
            operator=ConditionOperator.OR,
            description="RSI oversold or overbought"
        )
        
        # First condition met
        assert composite.evaluate({'rsi': 25.0}) is True
        
        # Second condition met
        assert composite.evaluate({'rsi': 75.0}) is True
        
        # No conditions met
        assert composite.evaluate({'rsi': 50.0}) is False
    
    def test_invalid_operator(self):
        """Test composite condition with invalid operator."""
        conditions = [
            Condition('price', ConditionOperator.GREATER_THAN, 1500.0),
        ]
        
        with pytest.raises(ValueError):
            CompositeCondition(
                conditions=conditions,
                operator=ConditionOperator.GREATER_THAN,  # Invalid for composite
                description="Invalid"
            )


class TestConditionEvaluator:
    """Test ConditionEvaluator class."""
    
    def test_evaluator_initialization(self):
        """Test condition evaluator initialization."""
        evaluator = ConditionEvaluator()
        assert len(evaluator.custom_evaluators) == 0
    
    def test_evaluate_single_condition(self):
        """Test evaluating a single condition."""
        evaluator = ConditionEvaluator()
        condition = Condition('price', ConditionOperator.GREATER_THAN, 1500.0)
        
        result = evaluator.evaluate_condition(condition, {'price': 1600.0})
        assert result is True
    
    def test_evaluate_composite_condition(self):
        """Test evaluating a composite condition."""
        evaluator = ConditionEvaluator()
        
        conditions = [
            Condition('price', ConditionOperator.GREATER_THAN, 1500.0),
            Condition('volume', ConditionOperator.GREATER_THAN, 1000000),
        ]
        composite = CompositeCondition(conditions, ConditionOperator.AND)
        
        result = evaluator.evaluate_composite_condition(
            composite,
            {'price': 1600.0, 'volume': 1500000}
        )
        assert result is True
    
    def test_evaluate_entry_conditions_all(self):
        """Test evaluating entry conditions with AND logic."""
        evaluator = ConditionEvaluator()
        
        conditions = [
            Condition('price', ConditionOperator.GREATER_THAN, 1500.0),
            Condition('rsi', ConditionOperator.LESS_THAN, 30.0),
        ]
        
        # All conditions met
        result = evaluator.evaluate_entry_conditions(
            conditions,
            {'price': 1600.0, 'rsi': 25.0},
            require_all=True
        )
        assert result is True
        
        # Not all conditions met
        result = evaluator.evaluate_entry_conditions(
            conditions,
            {'price': 1600.0, 'rsi': 50.0},
            require_all=True
        )
        assert result is False
    
    def test_evaluate_entry_conditions_any(self):
        """Test evaluating entry conditions with OR logic."""
        evaluator = ConditionEvaluator()
        
        conditions = [
            Condition('rsi', ConditionOperator.LESS_THAN, 30.0),
            Condition('rsi', ConditionOperator.GREATER_THAN, 70.0),
        ]
        
        # One condition met
        result = evaluator.evaluate_entry_conditions(
            conditions,
            {'rsi': 25.0},
            require_all=False
        )
        assert result is True
        
        # No conditions met
        result = evaluator.evaluate_entry_conditions(
            conditions,
            {'rsi': 50.0},
            require_all=False
        )
        assert result is False
    
    def test_evaluate_exit_conditions_stop_loss(self):
        """Test exit condition evaluation with stop loss."""
        evaluator = ConditionEvaluator()
        
        # Stop loss triggered
        should_exit, reason = evaluator.evaluate_exit_conditions(
            conditions=[],
            data={},
            entry_price=1500.0,
            current_price=1470.0,  # 2% loss
            stop_loss_pct=2.0
        )
        assert should_exit is True
        assert "Stop loss" in reason
        
        # Stop loss not triggered
        should_exit, reason = evaluator.evaluate_exit_conditions(
            conditions=[],
            data={},
            entry_price=1500.0,
            current_price=1485.0,  # 1% loss
            stop_loss_pct=2.0
        )
        assert should_exit is False
    
    def test_evaluate_exit_conditions_take_profit(self):
        """Test exit condition evaluation with take profit."""
        evaluator = ConditionEvaluator()
        
        # Take profit triggered
        should_exit, reason = evaluator.evaluate_exit_conditions(
            conditions=[],
            data={},
            entry_price=1500.0,
            current_price=1575.0,  # 5% profit
            take_profit_pct=5.0
        )
        assert should_exit is True
        assert "Take profit" in reason
        
        # Take profit not triggered
        should_exit, reason = evaluator.evaluate_exit_conditions(
            conditions=[],
            data={},
            entry_price=1500.0,
            current_price=1545.0,  # 3% profit
            take_profit_pct=5.0
        )
        assert should_exit is False
    
    def test_evaluate_exit_conditions_custom(self):
        """Test exit condition evaluation with custom conditions."""
        evaluator = ConditionEvaluator()
        
        exit_condition = Condition(
            'rsi',
            ConditionOperator.GREATER_THAN,
            70.0,
            description="RSI overbought"
        )
        
        should_exit, reason = evaluator.evaluate_exit_conditions(
            conditions=[exit_condition],
            data={'rsi': 75.0},
            entry_price=1500.0,
            current_price=1550.0
        )
        assert should_exit is True
        assert "RSI overbought" in reason
    
    def test_custom_evaluator_registration(self):
        """Test registering and using custom evaluators."""
        evaluator = ConditionEvaluator()
        
        def custom_condition(data, previous_data):
            return data.get('custom_signal') == 'BUY'
        
        evaluator.register_custom_evaluator('custom_buy', custom_condition)
        
        result = evaluator.evaluate_custom_condition(
            'custom_buy',
            {'custom_signal': 'BUY'}
        )
        assert result is True
        
        result = evaluator.evaluate_custom_condition(
            'custom_buy',
            {'custom_signal': 'SELL'}
        )
        assert result is False
    
    def test_custom_evaluator_not_found(self):
        """Test using unregistered custom evaluator."""
        evaluator = ConditionEvaluator()
        
        with pytest.raises(ValueError):
            evaluator.evaluate_custom_condition('nonexistent', {})


class TestConditionHelpers:
    """Test condition helper functions."""
    
    def test_create_price_condition(self):
        """Test creating price condition."""
        condition = create_price_condition(
            ConditionOperator.GREATER_THAN,
            1500.0,
            "Price above 1500"
        )
        
        assert condition.field == 'price'
        assert condition.operator == ConditionOperator.GREATER_THAN
        assert condition.value == 1500.0
        assert condition.description == "Price above 1500"
    
    def test_create_indicator_condition(self):
        """Test creating indicator condition."""
        condition = create_indicator_condition(
            'rsi',
            ConditionOperator.LESS_THAN,
            30.0,
            "RSI oversold"
        )
        
        assert condition.field == 'rsi'
        assert condition.operator == ConditionOperator.LESS_THAN
        assert condition.value == 30.0
    
    def test_create_volume_condition(self):
        """Test creating volume condition."""
        condition = create_volume_condition(
            ConditionOperator.GREATER_THAN,
            1000000
        )
        
        assert condition.field == 'volume'
        assert condition.value == 1000000


class TestStrategyWithConditions:
    """Test strategy integration with condition evaluation."""
    
    def test_strategy_with_condition_evaluator(self):
        """Test using condition evaluator in a strategy."""
        
        class ConditionalStrategy(StrategyBase):
            """Strategy that uses condition evaluator."""
            
            def __init__(self, config, parameters=None):
                super().__init__(config, parameters)
                self.evaluator = ConditionEvaluator()
                self.entry_conditions = [
                    Condition('price', ConditionOperator.GREATER_THAN, 1500.0),
                    Condition('volume', ConditionOperator.GREATER_THAN, 1000000),
                ]
            
            def get_entry_signals(self, market_data):
                signals = []
                
                for instrument in self.config.instruments:
                    data = {
                        'price': market_data.get('prices', {}).get(instrument, 0),
                        'volume': market_data.get('volumes', {}).get(instrument, 0),
                    }
                    
                    if self.evaluator.evaluate_entry_conditions(self.entry_conditions, data):
                        signal = TradingSignal(
                            signal_type=SignalType.ENTRY_LONG,
                            instrument=instrument,
                            timestamp=datetime.now(),
                            price=data['price'],
                            strength=SignalStrength.STRONG,
                            strategy_name=self.config.name,
                            reason="Entry conditions met",
                            confidence=0.8
                        )
                        signals.append(signal)
                
                return signals
            
            def get_exit_signals(self, positions):
                return []
        
        # Create strategy
        risk_params = RiskParameters(
            max_position_size=10000.0,
            stop_loss_percentage=2.0,
            target_profit_percentage=5.0,
            daily_loss_limit=5000.0,
            max_positions_per_instrument=2
        )
        
        config = StrategyConfig(
            name="ConditionalStrategy",
            enabled=True,
            instruments=["INFY"],
            entry_conditions={},
            exit_conditions={},
            risk_params=risk_params,
            timeframe="5minute"
        )
        
        strategy = ConditionalStrategy(config)
        
        # Test with conditions met
        market_data = {
            'prices': {'INFY': 1600.0},
            'volumes': {'INFY': 1500000},
            'positions': []
        }
        
        signals = strategy.evaluate(market_data)
        assert len(signals) == 1
        assert signals[0].instrument == "INFY"
        
        # Test with conditions not met
        market_data = {
            'prices': {'INFY': 1400.0},
            'volumes': {'INFY': 500000},
            'positions': []
        }
        
        signals = strategy.evaluate(market_data)
        assert len(signals) == 0


class TestStrategyManagerWithConditions:
    """Test StrategyManager with condition-based strategies."""
    
    def test_manager_evaluates_multiple_conditional_strategies(self):
        """Test manager evaluating multiple strategies with conditions."""
        
        class SimpleConditionalStrategy(StrategyBase):
            """Simple strategy with price condition."""
            
            def __init__(self, config, threshold):
                super().__init__(config)
                self.threshold = threshold
            
            def get_entry_signals(self, market_data):
                signals = []
                for instrument in self.config.instruments:
                    price = market_data.get('prices', {}).get(instrument, 0)
                    if price > self.threshold:
                        signal = TradingSignal(
                            signal_type=SignalType.ENTRY_LONG,
                            instrument=instrument,
                            timestamp=datetime.now(),
                            price=price,
                            strength=SignalStrength.MODERATE,
                            strategy_name=self.config.name,
                            reason=f"Price above {self.threshold}",
                            confidence=0.7
                        )
                        signals.append(signal)
                return signals
            
            def get_exit_signals(self, positions):
                return []
        
        # Create manager and strategies
        manager = StrategyManager()
        
        risk_params = RiskParameters(
            max_position_size=10000.0,
            stop_loss_percentage=2.0,
            target_profit_percentage=5.0,
            daily_loss_limit=5000.0,
            max_positions_per_instrument=2
        )
        
        config1 = StrategyConfig(
            name="Strategy1",
            enabled=True,
            instruments=["INFY"],
            entry_conditions={},
            exit_conditions={},
            risk_params=risk_params,
            timeframe="5minute"
        )
        
        config2 = StrategyConfig(
            name="Strategy2",
            enabled=True,
            instruments=["TCS"],
            entry_conditions={},
            exit_conditions={},
            risk_params=risk_params,
            timeframe="5minute"
        )
        
        strategy1 = SimpleConditionalStrategy(config1, 1500.0)
        strategy2 = SimpleConditionalStrategy(config2, 3000.0)
        
        manager.register_strategy(strategy1)
        manager.register_strategy(strategy2)
        
        # Evaluate all strategies
        market_data = {
            'prices': {'INFY': 1600.0, 'TCS': 3500.0},
            'positions': []
        }
        
        signals = manager.evaluate_all_strategies(market_data)
        
        assert len(signals) == 2
        assert any(s.instrument == "INFY" for s in signals)
        assert any(s.instrument == "TCS" for s in signals)
