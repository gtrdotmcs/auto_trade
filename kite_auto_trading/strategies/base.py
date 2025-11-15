"""
Base strategy classes for the Kite Auto-Trading application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from kite_auto_trading.models.base import Strategy, StrategyConfig, Position
from kite_auto_trading.models.signals import (
    TradingSignal,
    SignalType,
    SignalStrength,
    StrategyParameters,
)


class StrategyBase(Strategy):
    """
    Enhanced base class for all trading strategies.
    
    Provides common functionality for signal generation, parameter management,
    and strategy lifecycle management.
    """
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config)
        self.parameters = parameters or StrategyParameters()
        self.indicators: Dict[str, Any] = {}
        self.last_evaluation_time: Optional[datetime] = None
        self.signal_history: List[TradingSignal] = []
        self.max_signal_history = 100
    
    def evaluate(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate market data and return trading signals.
        
        Args:
            market_data: Dictionary containing market data and positions
            
        Returns:
            List of TradingSignal objects
        """
        if not self.enabled:
            return []
        
        self.last_evaluation_time = datetime.now()
        signals = []
        
        try:
            # Get entry signals
            entry_signals = self.get_entry_signals(market_data)
            signals.extend(entry_signals)
            
            # Get exit signals for current positions
            current_positions = market_data.get('positions', [])
            exit_signals = self.get_exit_signals(current_positions)
            signals.extend(exit_signals)
            
            # Filter signals by minimum confidence
            signals = [s for s in signals if s.confidence >= self.parameters.min_confidence]
            
            # Store signals in history
            self._update_signal_history(signals)
            
        except Exception as e:
            print(f"Error evaluating strategy {self.config.name}: {e}")
            return []
        
        return signals
    
    @abstractmethod
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Generate entry signals based on market data.
        
        Args:
            market_data: Dictionary containing current market data
            
        Returns:
            List of entry TradingSignal objects
        """
        pass
    
    @abstractmethod
    def get_exit_signals(self, positions: List[Position]) -> List[TradingSignal]:
        """
        Generate exit signals for current positions.
        
        Args:
            positions: List of current Position objects
            
        Returns:
            List of exit TradingSignal objects
        """
        pass
    
    def _update_signal_history(self, signals: List[TradingSignal]) -> None:
        """Update signal history with new signals."""
        self.signal_history.extend(signals)
        # Keep only recent signals
        if len(self.signal_history) > self.max_signal_history:
            self.signal_history = self.signal_history[-self.max_signal_history:]
    
    def get_recent_signals(self, count: int = 10) -> List[TradingSignal]:
        """Get the most recent signals."""
        return self.signal_history[-count:]
    
    def reset_signal_history(self) -> None:
        """Clear signal history."""
        self.signal_history = []
    
    def update_parameters(self, parameters: StrategyParameters) -> None:
        """Update strategy parameters."""
        self.parameters = parameters
    
    def get_parameters(self) -> StrategyParameters:
        """Get current strategy parameters."""
        return self.parameters


class TechnicalStrategy(StrategyBase):
    """Base class for technical analysis-based strategies."""
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config, parameters)
        self.lookback_period = parameters.lookback_period if parameters else 20
    
    @abstractmethod
    def calculate_indicators(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate technical indicators from price data.
        
        Args:
            price_data: List of price data dictionaries (OHLC)
            
        Returns:
            Dictionary of calculated indicators
        """
        pass
    
    def _create_signal(
        self,
        signal_type: SignalType,
        instrument: str,
        price: float,
        strength: SignalStrength,
        reason: str,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TradingSignal:
        """
        Helper method to create a trading signal.
        
        Args:
            signal_type: Type of signal
            instrument: Trading symbol
            price: Current price
            strength: Signal strength
            reason: Reason for the signal
            confidence: Confidence level (0-1)
            metadata: Additional signal data
            
        Returns:
            TradingSignal object
        """
        return TradingSignal(
            signal_type=signal_type,
            instrument=instrument,
            timestamp=datetime.now(),
            price=price,
            strength=strength,
            strategy_name=self.config.name,
            reason=reason,
            confidence=confidence,
            metadata=metadata or {}
        )


class MeanReversionStrategy(TechnicalStrategy):
    """Base class for mean reversion strategies."""
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config, parameters)
        self.oversold_threshold = config.entry_conditions.get('oversold_threshold', 30)
        self.overbought_threshold = config.entry_conditions.get('overbought_threshold', 70)
    
    @abstractmethod
    def is_oversold(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if instrument is oversold.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if oversold, False otherwise
        """
        pass
    
    @abstractmethod
    def is_overbought(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if instrument is overbought.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if overbought, False otherwise
        """
        pass


class TrendFollowingStrategy(TechnicalStrategy):
    """Base class for trend following strategies."""
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config, parameters)
        self.trend_strength_threshold = config.entry_conditions.get('trend_strength', 0.7)
    
    @abstractmethod
    def identify_trend(self, market_data: Dict[str, Any]) -> str:
        """
        Identify current trend direction.
        
        Args:
            market_data: Current market data
            
        Returns:
            Trend direction: 'UP', 'DOWN', or 'SIDEWAYS'
        """
        pass
    
    @abstractmethod
    def calculate_trend_strength(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate trend strength.
        
        Args:
            market_data: Current market data
            
        Returns:
            Trend strength value between 0 and 1
        """
        pass


class StrategyManager:
    """
    Manages multiple trading strategies with runtime control.
    
    Orchestrates strategy evaluation, signal aggregation, and strategy lifecycle management.
    """
    
    def __init__(self):
        self.strategies: Dict[str, StrategyBase] = {}
        self.enabled_strategies: List[str] = []
        self.evaluation_count: Dict[str, int] = {}
        self.error_count: Dict[str, int] = {}
        self.max_errors_before_disable = 10
    
    def register_strategy(self, strategy: StrategyBase) -> None:
        """
        Register a new strategy.
        
        Args:
            strategy: Strategy instance to register
        """
        strategy_name = strategy.config.name
        self.strategies[strategy_name] = strategy
        self.evaluation_count[strategy_name] = 0
        self.error_count[strategy_name] = 0
        
        if strategy.enabled:
            self.enabled_strategies.append(strategy_name)
    
    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            strategy_name: Name of the strategy to unregister
            
        Returns:
            True if successful, False if strategy not found
        """
        if strategy_name not in self.strategies:
            return False
        
        self.disable_strategy(strategy_name)
        del self.strategies[strategy_name]
        del self.evaluation_count[strategy_name]
        del self.error_count[strategy_name]
        return True
    
    def enable_strategy(self, strategy_name: str) -> bool:
        """
        Enable a strategy for evaluation.
        
        Args:
            strategy_name: Name of the strategy to enable
            
        Returns:
            True if successful, False if strategy not found
        """
        if strategy_name not in self.strategies:
            return False
        
        self.strategies[strategy_name].enabled = True
        if strategy_name not in self.enabled_strategies:
            self.enabled_strategies.append(strategy_name)
        return True
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """
        Disable a strategy from evaluation.
        
        Args:
            strategy_name: Name of the strategy to disable
            
        Returns:
            True if successful, False if strategy not found
        """
        if strategy_name not in self.strategies:
            return False
        
        self.strategies[strategy_name].enabled = False
        if strategy_name in self.enabled_strategies:
            self.enabled_strategies.remove(strategy_name)
        return True
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """
        Check if a strategy is enabled.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            True if enabled, False otherwise
        """
        return strategy_name in self.enabled_strategies
    
    def evaluate_all_strategies(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate all enabled strategies and aggregate signals.
        
        Args:
            market_data: Dictionary containing market data and positions
            
        Returns:
            List of TradingSignal objects from all strategies
        """
        all_signals = []
        
        for strategy_name in self.enabled_strategies[:]:  # Copy list to allow modification
            strategy = self.strategies[strategy_name]
            
            try:
                signals = strategy.evaluate(market_data)
                all_signals.extend(signals)
                self.evaluation_count[strategy_name] += 1
                
            except Exception as e:
                # Track errors and auto-disable if too many
                self.error_count[strategy_name] += 1
                print(f"Error evaluating strategy {strategy_name}: {e}")
                
                if self.error_count[strategy_name] >= self.max_errors_before_disable:
                    print(f"Disabling strategy {strategy_name} due to repeated errors")
                    self.disable_strategy(strategy_name)
        
        return all_signals
    
    def evaluate_strategy(self, strategy_name: str, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate a specific strategy.
        
        Args:
            strategy_name: Name of the strategy to evaluate
            market_data: Dictionary containing market data and positions
            
        Returns:
            List of TradingSignal objects
        """
        if strategy_name not in self.strategies:
            return []
        
        if not self.strategies[strategy_name].enabled:
            return []
        
        try:
            signals = self.strategies[strategy_name].evaluate(market_data)
            self.evaluation_count[strategy_name] += 1
            return signals
        except Exception as e:
            self.error_count[strategy_name] += 1
            print(f"Error evaluating strategy {strategy_name}: {e}")
            return []
    
    def get_strategy(self, strategy_name: str) -> Optional[StrategyBase]:
        """
        Get a strategy by name.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Strategy instance or None if not found
        """
        return self.strategies.get(strategy_name)
    
    def get_all_strategies(self) -> List[StrategyBase]:
        """Get all registered strategies."""
        return list(self.strategies.values())
    
    def get_enabled_strategies(self) -> List[StrategyBase]:
        """Get all enabled strategies."""
        return [self.strategies[name] for name in self.enabled_strategies]
    
    def get_strategy_configs(self) -> List[StrategyConfig]:
        """Get configurations for all registered strategies."""
        return [strategy.config for strategy in self.strategies.values()]
    
    def get_strategy_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for all strategies.
        
        Returns:
            Dictionary mapping strategy names to their stats
        """
        return {
            name: {
                'evaluations': self.evaluation_count[name],
                'errors': self.error_count[name],
                'enabled': name in self.enabled_strategies,
            }
            for name in self.strategies.keys()
        }
    
    def reset_error_counts(self) -> None:
        """Reset error counts for all strategies."""
        for strategy_name in self.strategies.keys():
            self.error_count[strategy_name] = 0