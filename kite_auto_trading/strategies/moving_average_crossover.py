"""
Moving Average Crossover Strategy Implementation.

This strategy generates buy signals when a short-term moving average crosses above
a long-term moving average, and sell signals when it crosses below.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from kite_auto_trading.strategies.base import TrendFollowingStrategy
from kite_auto_trading.models.base import StrategyConfig, Position
from kite_auto_trading.models.signals import (
    TradingSignal,
    SignalType,
    SignalStrength,
    StrategyParameters,
)


class MovingAverageCrossoverStrategy(TrendFollowingStrategy):
    """
    Moving Average Crossover Strategy.
    
    Generates entry signals when short MA crosses above long MA (bullish crossover)
    and exit signals when short MA crosses below long MA (bearish crossover).
    
    Parameters:
        short_period: Period for short-term moving average (default: 10)
        long_period: Period for long-term moving average (default: 20)
        ma_type: Type of moving average - 'SMA' or 'EMA' (default: 'SMA')
    """
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config, parameters)
        
        # Get strategy-specific parameters
        self.short_period = self.parameters.custom_params.get('short_period', 10)
        self.long_period = self.parameters.custom_params.get('long_period', 20)
        self.ma_type = self.parameters.custom_params.get('ma_type', 'SMA')
        
        # Validate parameters
        if self.short_period >= self.long_period:
            raise ValueError("Short period must be less than long period")
        
        # Store previous MA values for crossover detection
        self.previous_short_ma: Dict[str, float] = {}
        self.previous_long_ma: Dict[str, float] = {}
    
    def calculate_indicators(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate moving averages from price data.
        
        Args:
            price_data: List of OHLC data dictionaries
            
        Returns:
            Dictionary containing calculated moving averages
        """
        if len(price_data) < self.long_period:
            return {}
        
        # Extract closing prices
        closes = [candle['close'] for candle in price_data]
        
        # Calculate moving averages
        if self.ma_type == 'SMA':
            short_ma = self._calculate_sma(closes, self.short_period)
            long_ma = self._calculate_sma(closes, self.long_period)
        elif self.ma_type == 'EMA':
            short_ma = self._calculate_ema(closes, self.short_period)
            long_ma = self._calculate_ema(closes, self.long_period)
        else:
            raise ValueError(f"Unsupported MA type: {self.ma_type}")
        
        return {
            'short_ma': short_ma,
            'long_ma': long_ma,
            'current_price': closes[-1],
        }
    
    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA
        
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Generate entry signals based on MA crossover.
        
        Args:
            market_data: Dictionary containing market data
            
        Returns:
            List of entry TradingSignal objects
        """
        signals = []
        
        for instrument in self.config.instruments:
            # Get price history for this instrument
            price_history = market_data.get('price_history', {}).get(instrument, [])
            
            if len(price_history) < self.long_period:
                continue
            
            # Calculate indicators
            indicators = self.calculate_indicators(price_history)
            if not indicators:
                continue
            
            short_ma = indicators['short_ma']
            long_ma = indicators['long_ma']
            current_price = indicators['current_price']
            
            # Get previous MA values
            prev_short_ma = self.previous_short_ma.get(instrument)
            prev_long_ma = self.previous_long_ma.get(instrument)
            
            # Store current values for next iteration
            self.previous_short_ma[instrument] = short_ma
            self.previous_long_ma[instrument] = long_ma
            
            # Check for crossover (need previous values)
            if prev_short_ma is None or prev_long_ma is None:
                continue
            
            # Bullish crossover: short MA crosses above long MA
            if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                # Calculate signal strength based on MA separation
                separation_pct = ((short_ma - long_ma) / long_ma) * 100
                strength = self._determine_signal_strength(separation_pct)
                confidence = min(0.5 + (separation_pct / 10), 0.95)
                
                signal = self._create_signal(
                    signal_type=SignalType.ENTRY_LONG,
                    instrument=instrument,
                    price=current_price,
                    strength=strength,
                    reason=f"Bullish MA crossover: {self.ma_type}({self.short_period}) crossed above {self.ma_type}({self.long_period})",
                    confidence=confidence,
                    metadata={
                        'short_ma': short_ma,
                        'long_ma': long_ma,
                        'separation_pct': separation_pct,
                    }
                )
                signals.append(signal)
            
            # Bearish crossover: short MA crosses below long MA (for short positions)
            elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                separation_pct = ((long_ma - short_ma) / long_ma) * 100
                strength = self._determine_signal_strength(separation_pct)
                confidence = min(0.5 + (separation_pct / 10), 0.95)
                
                signal = self._create_signal(
                    signal_type=SignalType.ENTRY_SHORT,
                    instrument=instrument,
                    price=current_price,
                    strength=strength,
                    reason=f"Bearish MA crossover: {self.ma_type}({self.short_period}) crossed below {self.ma_type}({self.long_period})",
                    confidence=confidence,
                    metadata={
                        'short_ma': short_ma,
                        'long_ma': long_ma,
                        'separation_pct': separation_pct,
                    }
                )
                signals.append(signal)
        
        return signals
    
    def get_exit_signals(self, positions: List[Position]) -> List[TradingSignal]:
        """
        Generate exit signals for current positions.
        
        Args:
            positions: List of current Position objects
            
        Returns:
            List of exit TradingSignal objects
        """
        signals = []
        
        for position in positions:
            # Only handle positions from this strategy
            if position.strategy_id != self.config.name:
                continue
            
            instrument = position.instrument
            
            # Get current MA values
            short_ma = self.previous_short_ma.get(instrument)
            long_ma = self.previous_long_ma.get(instrument)
            
            if short_ma is None or long_ma is None:
                continue
            
            # Exit long position when short MA crosses below long MA
            if position.quantity > 0 and short_ma < long_ma:
                signal = self._create_signal(
                    signal_type=SignalType.EXIT_LONG,
                    instrument=instrument,
                    price=position.current_price,
                    strength=SignalStrength.MODERATE,
                    reason=f"Exit long: {self.ma_type}({self.short_period}) crossed below {self.ma_type}({self.long_period})",
                    confidence=0.7,
                    metadata={
                        'entry_price': position.average_price,
                        'current_pnl': position.unrealized_pnl,
                    }
                )
                signals.append(signal)
            
            # Exit short position when short MA crosses above long MA
            elif position.quantity < 0 and short_ma > long_ma:
                signal = self._create_signal(
                    signal_type=SignalType.EXIT_SHORT,
                    instrument=instrument,
                    price=position.current_price,
                    strength=SignalStrength.MODERATE,
                    reason=f"Exit short: {self.ma_type}({self.short_period}) crossed above {self.ma_type}({self.long_period})",
                    confidence=0.7,
                    metadata={
                        'entry_price': position.average_price,
                        'current_pnl': position.unrealized_pnl,
                    }
                )
                signals.append(signal)
        
        return signals
    
    def identify_trend(self, market_data: Dict[str, Any]) -> str:
        """
        Identify current trend direction based on MA relationship.
        
        Args:
            market_data: Current market data
            
        Returns:
            Trend direction: 'UP', 'DOWN', or 'SIDEWAYS'
        """
        instrument = self.config.instruments[0] if self.config.instruments else None
        if not instrument:
            return 'SIDEWAYS'
        
        short_ma = self.previous_short_ma.get(instrument)
        long_ma = self.previous_long_ma.get(instrument)
        
        if short_ma is None or long_ma is None:
            return 'SIDEWAYS'
        
        if short_ma > long_ma * 1.01:  # 1% threshold
            return 'UP'
        elif short_ma < long_ma * 0.99:
            return 'DOWN'
        else:
            return 'SIDEWAYS'
    
    def calculate_trend_strength(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate trend strength based on MA separation.
        
        Args:
            market_data: Current market data
            
        Returns:
            Trend strength value between 0 and 1
        """
        instrument = self.config.instruments[0] if self.config.instruments else None
        if not instrument:
            return 0.0
        
        short_ma = self.previous_short_ma.get(instrument)
        long_ma = self.previous_long_ma.get(instrument)
        
        if short_ma is None or long_ma is None:
            return 0.0
        
        # Calculate separation percentage
        separation_pct = abs((short_ma - long_ma) / long_ma) * 100
        
        # Normalize to 0-1 range (assume 5% separation = strong trend)
        strength = min(separation_pct / 5.0, 1.0)
        
        return strength
    
    def _determine_signal_strength(self, separation_pct: float) -> SignalStrength:
        """Determine signal strength based on MA separation."""
        if separation_pct >= 2.0:
            return SignalStrength.STRONG
        elif separation_pct >= 0.5:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
