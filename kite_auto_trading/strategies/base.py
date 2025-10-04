"""
Base strategy classes for the Kite Auto-Trading application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from kite_auto_trading.models.base import Strategy, StrategyConfig, Position


class TechnicalStrategy(Strategy):
    """Base class for technical analysis-based strategies."""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.indicators = {}
        self.lookback_period = config.entry_conditions.get('lookback_period', 20)
    
    @abstractmethod
    def calculate_indicators(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate technical indicators from price data."""
        pass
    
    def evaluate(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate market data and return trading signals."""
        if not self.enabled:
            return []
        
        signals = []
        
        # Get entry signals
        entry_signals = self.get_entry_signals(market_data)
        signals.extend(entry_signals)
        
        # Get exit signals for current positions
        current_positions = market_data.get('positions', [])
        exit_signals = self.get_exit_signals(current_positions)
        signals.extend(exit_signals)
        
        return signals


class MeanReversionStrategy(TechnicalStrategy):
    """Base class for mean reversion strategies."""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.oversold_threshold = config.entry_conditions.get('oversold_threshold', 30)
        self.overbought_threshold = config.entry_conditions.get('overbought_threshold', 70)
    
    @abstractmethod
    def is_oversold(self, market_data: Dict[str, Any]) -> bool:
        """Check if instrument is oversold."""
        pass
    
    @abstractmethod
    def is_overbought(self, market_data: Dict[str, Any]) -> bool:
        """Check if instrument is overbought."""
        pass


class TrendFollowingStrategy(TechnicalStrategy):
    """Base class for trend following strategies."""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.trend_strength_threshold = config.entry_conditions.get('trend_strength', 0.7)
    
    @abstractmethod
    def identify_trend(self, market_data: Dict[str, Any]) -> str:
        """Identify current trend direction (UP/DOWN/SIDEWAYS)."""
        pass
    
    @abstractmethod
    def calculate_trend_strength(self, market_data: Dict[str, Any]) -> float:
        """Calculate trend strength (0-1)."""
        pass


class StrategyManager:
    """Manages multiple trading strategies."""
    
    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
        self.enabled_strategies: List[str] = []
    
    def register_strategy(self, strategy: Strategy) -> None:
        """Register a new strategy."""
        self.strategies[strategy.config.name] = strategy
        if strategy.enabled:
            self.enabled_strategies.append(strategy.config.name)
    
    def enable_strategy(self, strategy_name: str) -> None:
        """Enable a strategy."""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = True
            if strategy_name not in self.enabled_strategies:
                self.enabled_strategies.append(strategy_name)
    
    def disable_strategy(self, strategy_name: str) -> None:
        """Disable a strategy."""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = False
            if strategy_name in self.enabled_strategies:
                self.enabled_strategies.remove(strategy_name)
    
    def evaluate_all_strategies(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate all enabled strategies."""
        all_signals = []
        
        for strategy_name in self.enabled_strategies:
            strategy = self.strategies[strategy_name]
            try:
                signals = strategy.evaluate(market_data)
                # Add strategy name to each signal
                for signal in signals:
                    signal['strategy_name'] = strategy_name
                all_signals.extend(signals)
            except Exception as e:
                # Log error but continue with other strategies
                print(f"Error evaluating strategy {strategy_name}: {e}")
        
        return all_signals
    
    def get_strategy_configs(self) -> List[StrategyConfig]:
        """Get configurations for all registered strategies."""
        return [strategy.config for strategy in self.strategies.values()]