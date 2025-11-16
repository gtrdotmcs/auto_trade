"""
RSI Mean Reversion Strategy Implementation.

This strategy generates buy signals when RSI indicates oversold conditions
and sell signals when RSI indicates overbought conditions.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from kite_auto_trading.strategies.base import MeanReversionStrategy
from kite_auto_trading.models.base import StrategyConfig, Position
from kite_auto_trading.models.signals import (
    TradingSignal,
    SignalType,
    SignalStrength,
    StrategyParameters,
)


class RSIMeanReversionStrategy(MeanReversionStrategy):
    """
    RSI-based Mean Reversion Strategy.
    
    Generates buy signals when RSI falls below oversold threshold (default: 30)
    and sell signals when RSI rises above overbought threshold (default: 70).
    
    Parameters:
        rsi_period: Period for RSI calculation (default: 14)
        oversold_threshold: RSI level considered oversold (default: 30)
        overbought_threshold: RSI level considered overbought (default: 70)
        exit_on_neutral: Exit when RSI returns to neutral zone (default: True)
    """
    
    def __init__(self, config: StrategyConfig, parameters: Optional[StrategyParameters] = None):
        super().__init__(config, parameters)
        
        # Get strategy-specific parameters
        self.rsi_period = self.parameters.custom_params.get('rsi_period', 14)
        self.oversold_threshold = config.entry_conditions.get('oversold_threshold', 30)
        self.overbought_threshold = config.entry_conditions.get('overbought_threshold', 70)
        self.exit_on_neutral = self.parameters.custom_params.get('exit_on_neutral', True)
        self.neutral_lower = 45
        self.neutral_upper = 55
        
        # Validate parameters
        if self.oversold_threshold >= self.overbought_threshold:
            raise ValueError("Oversold threshold must be less than overbought threshold")
        
        # Store RSI values for tracking
        self.current_rsi: Dict[str, float] = {}
        self.previous_rsi: Dict[str, float] = {}
    
    def calculate_indicators(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate RSI from price data.
        
        Args:
            price_data: List of OHLC data dictionaries
            
        Returns:
            Dictionary containing calculated RSI
        """
        if len(price_data) < self.rsi_period + 1:
            return {}
        
        # Extract closing prices
        closes = [candle['close'] for candle in price_data]
        
        # Calculate RSI
        rsi = self._calculate_rsi(closes, self.rsi_period)
        
        return {
            'rsi': rsi,
            'current_price': closes[-1],
        }
    
    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: List of closing prices
            period: RSI period
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI
        
        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        # Calculate average gain and loss
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        # Avoid division by zero
        if avg_loss == 0:
            return 100.0
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def get_entry_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Generate entry signals based on RSI levels.
        
        Args:
            market_data: Dictionary containing market data
            
        Returns:
            List of entry TradingSignal objects
        """
        signals = []
        
        for instrument in self.config.instruments:
            # Get price history for this instrument
            price_history = market_data.get('price_history', {}).get(instrument, [])
            
            if len(price_history) < self.rsi_period + 1:
                continue
            
            # Calculate indicators
            indicators = self.calculate_indicators(price_history)
            if not indicators:
                continue
            
            rsi = indicators['rsi']
            current_price = indicators['current_price']
            
            # Store RSI values
            self.previous_rsi[instrument] = self.current_rsi.get(instrument, rsi)
            self.current_rsi[instrument] = rsi
            
            # Check for oversold condition (buy signal)
            if self.is_oversold({'rsi': rsi}):
                # Calculate signal strength based on how oversold
                distance_from_threshold = self.oversold_threshold - rsi
                strength = self._determine_signal_strength(distance_from_threshold, is_oversold=True)
                confidence = min(0.5 + (distance_from_threshold / 30), 0.95)
                
                signal = self._create_signal(
                    signal_type=SignalType.ENTRY_LONG,
                    instrument=instrument,
                    price=current_price,
                    strength=strength,
                    reason=f"RSI oversold: {rsi:.2f} < {self.oversold_threshold}",
                    confidence=confidence,
                    metadata={
                        'rsi': rsi,
                        'oversold_threshold': self.oversold_threshold,
                    }
                )
                signals.append(signal)
            
            # Check for overbought condition (sell signal for short positions)
            elif self.is_overbought({'rsi': rsi}):
                distance_from_threshold = rsi - self.overbought_threshold
                strength = self._determine_signal_strength(distance_from_threshold, is_oversold=False)
                confidence = min(0.5 + (distance_from_threshold / 30), 0.95)
                
                signal = self._create_signal(
                    signal_type=SignalType.ENTRY_SHORT,
                    instrument=instrument,
                    price=current_price,
                    strength=strength,
                    reason=f"RSI overbought: {rsi:.2f} > {self.overbought_threshold}",
                    confidence=confidence,
                    metadata={
                        'rsi': rsi,
                        'overbought_threshold': self.overbought_threshold,
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
            rsi = self.current_rsi.get(instrument)
            
            if rsi is None:
                continue
            
            # Exit long position when RSI becomes overbought or returns to neutral
            if position.quantity > 0:
                should_exit = False
                reason = ""
                
                if rsi >= self.overbought_threshold:
                    should_exit = True
                    reason = f"Exit long: RSI overbought at {rsi:.2f}"
                elif self.exit_on_neutral and self.neutral_lower <= rsi <= self.neutral_upper:
                    should_exit = True
                    reason = f"Exit long: RSI returned to neutral zone at {rsi:.2f}"
                
                if should_exit:
                    signal = self._create_signal(
                        signal_type=SignalType.EXIT_LONG,
                        instrument=instrument,
                        price=position.current_price,
                        strength=SignalStrength.MODERATE,
                        reason=reason,
                        confidence=0.7,
                        metadata={
                            'rsi': rsi,
                            'entry_price': position.average_price,
                            'current_pnl': position.unrealized_pnl,
                        }
                    )
                    signals.append(signal)
            
            # Exit short position when RSI becomes oversold or returns to neutral
            elif position.quantity < 0:
                should_exit = False
                reason = ""
                
                if rsi <= self.oversold_threshold:
                    should_exit = True
                    reason = f"Exit short: RSI oversold at {rsi:.2f}"
                elif self.exit_on_neutral and self.neutral_lower <= rsi <= self.neutral_upper:
                    should_exit = True
                    reason = f"Exit short: RSI returned to neutral zone at {rsi:.2f}"
                
                if should_exit:
                    signal = self._create_signal(
                        signal_type=SignalType.EXIT_SHORT,
                        instrument=instrument,
                        price=position.current_price,
                        strength=SignalStrength.MODERATE,
                        reason=reason,
                        confidence=0.7,
                        metadata={
                            'rsi': rsi,
                            'entry_price': position.average_price,
                            'current_pnl': position.unrealized_pnl,
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    def is_oversold(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if instrument is oversold based on RSI.
        
        Args:
            market_data: Current market data with RSI
            
        Returns:
            True if oversold, False otherwise
        """
        rsi = market_data.get('rsi')
        if rsi is None:
            return False
        return rsi < self.oversold_threshold
    
    def is_overbought(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if instrument is overbought based on RSI.
        
        Args:
            market_data: Current market data with RSI
            
        Returns:
            True if overbought, False otherwise
        """
        rsi = market_data.get('rsi')
        if rsi is None:
            return False
        return rsi > self.overbought_threshold
    
    def _determine_signal_strength(self, distance: float, is_oversold: bool) -> SignalStrength:
        """
        Determine signal strength based on distance from threshold.
        
        Args:
            distance: Distance from threshold
            is_oversold: Whether checking oversold or overbought
            
        Returns:
            SignalStrength enum value
        """
        if distance >= 15:  # Very extreme
            return SignalStrength.STRONG
        elif distance >= 5:  # Moderately extreme
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
