"""
Market data models and interfaces for the Kite Auto-Trading application.

This module contains data structures for ticks, OHLC data, and instrument information.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class InstrumentType(Enum):
    """Types of trading instruments."""
    EQUITY = "EQ"
    FUTURES = "FUT"
    OPTIONS = "OPT"
    CURRENCY = "CUR"
    COMMODITY = "COM"


@dataclass
class Tick:
    """
    Real-time tick data model representing a single market data update.
    
    Attributes:
        instrument_token: Unique identifier for the instrument
        timestamp: Time when the tick was received
        last_price: Last traded price
        volume: Total volume traded
        bid_price: Best bid price
        ask_price: Best ask price
        bid_quantity: Quantity at best bid
        ask_quantity: Quantity at best ask
        open: Opening price of the day
        high: Highest price of the day
        low: Lowest price of the day
        close: Previous day's closing price
        change: Price change from previous close
    """
    instrument_token: int
    timestamp: datetime
    last_price: float
    volume: int
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_quantity: Optional[int] = None
    ask_quantity: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    change: Optional[float] = None
    
    def __post_init__(self):
        """Validate tick data after initialization."""
        if self.last_price <= 0:
            raise ValueError(f"Invalid last_price: {self.last_price}. Must be positive.")
        if self.volume < 0:
            raise ValueError(f"Invalid volume: {self.volume}. Must be non-negative.")
        if self.bid_price is not None and self.bid_price < 0:
            raise ValueError(f"Invalid bid_price: {self.bid_price}. Must be non-negative.")
        if self.ask_price is not None and self.ask_price < 0:
            raise ValueError(f"Invalid ask_price: {self.ask_price}. Must be non-negative.")


@dataclass
class OHLC:
    """
    OHLC (Open, High, Low, Close) candlestick data model.
    
    Attributes:
        instrument_token: Unique identifier for the instrument
        timestamp: Start time of the candle
        open: Opening price
        high: Highest price in the period
        low: Lowest price in the period
        close: Closing price
        volume: Total volume traded in the period
        timeframe: Timeframe of the candle (e.g., '1minute', '5minute', 'day')
    """
    instrument_token: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str
    
    def __post_init__(self):
        """Validate OHLC data after initialization."""
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("All price values must be positive.")
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than Low ({self.low}).")
        if self.high < self.open or self.high < self.close:
            raise ValueError(f"High ({self.high}) must be >= Open ({self.open}) and Close ({self.close}).")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Low ({self.low}) must be <= Open ({self.open}) and Close ({self.close}).")
        if self.volume < 0:
            raise ValueError(f"Invalid volume: {self.volume}. Must be non-negative.")
    
    def is_bullish(self) -> bool:
        """Check if the candle is bullish (close > open)."""
        return self.close > self.open
    
    def is_bearish(self) -> bool:
        """Check if the candle is bearish (close < open)."""
        return self.close < self.open
    
    def body_size(self) -> float:
        """Calculate the size of the candle body."""
        return abs(self.close - self.open)
    
    def range_size(self) -> float:
        """Calculate the total range of the candle."""
        return self.high - self.low


@dataclass
class Instrument:
    """
    Instrument information model.
    
    Attributes:
        instrument_token: Unique identifier for the instrument
        exchange_token: Exchange-specific token
        tradingsymbol: Trading symbol (e.g., 'INFY', 'NIFTY24JANFUT')
        name: Full name of the instrument
        exchange: Exchange where the instrument is traded
        instrument_type: Type of instrument (EQUITY, FUTURES, etc.)
        segment: Market segment
        expiry: Expiry date for derivatives (None for equity)
        strike: Strike price for options (None for others)
        tick_size: Minimum price movement
        lot_size: Minimum trading quantity
        last_price: Last known price
    """
    instrument_token: int
    exchange_token: int
    tradingsymbol: str
    name: str
    exchange: str
    instrument_type: InstrumentType
    segment: str
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    tick_size: float = 0.05
    lot_size: int = 1
    last_price: Optional[float] = None
    
    def __post_init__(self):
        """Validate instrument data after initialization."""
        if not self.tradingsymbol:
            raise ValueError("Trading symbol cannot be empty.")
        if self.tick_size <= 0:
            raise ValueError(f"Invalid tick_size: {self.tick_size}. Must be positive.")
        if self.lot_size <= 0:
            raise ValueError(f"Invalid lot_size: {self.lot_size}. Must be positive.")
        if self.last_price is not None and self.last_price < 0:
            raise ValueError(f"Invalid last_price: {self.last_price}. Must be non-negative.")
    
    def is_derivative(self) -> bool:
        """Check if the instrument is a derivative."""
        return self.instrument_type in [InstrumentType.FUTURES, InstrumentType.OPTIONS]
    
    def is_expired(self) -> bool:
        """Check if the instrument has expired (for derivatives)."""
        if self.expiry is None:
            return False
        return datetime.now() > self.expiry


@dataclass
class MarketDepth:
    """
    Market depth (order book) data model.
    
    Attributes:
        instrument_token: Unique identifier for the instrument
        timestamp: Time when the depth was captured
        bids: List of bid levels (price, quantity, orders)
        asks: List of ask levels (price, quantity, orders)
    """
    instrument_token: int
    timestamp: datetime
    bids: List[Dict[str, Any]] = field(default_factory=list)
    asks: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_best_bid(self) -> Optional[Dict[str, Any]]:
        """Get the best bid (highest price)."""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[Dict[str, Any]]:
        """Get the best ask (lowest price)."""
        return self.asks[0] if self.asks else None
    
    def get_spread(self) -> Optional[float]:
        """Calculate the bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask['price'] - best_bid['price']
        return None


def validate_tick_data(tick_data: Dict[str, Any]) -> bool:
    """
    Validate raw tick data from API.
    
    Args:
        tick_data: Raw tick data dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['instrument_token', 'last_price']
    
    for field in required_fields:
        if field not in tick_data:
            return False
    
    if not isinstance(tick_data['instrument_token'], int):
        return False
    
    if not isinstance(tick_data['last_price'], (int, float)) or tick_data['last_price'] <= 0:
        return False
    
    return True


def validate_ohlc_data(ohlc_data: Dict[str, Any]) -> bool:
    """
    Validate raw OHLC data from API.
    
    Args:
        ohlc_data: Raw OHLC data dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['open', 'high', 'low', 'close', 'volume']
    
    for field in required_fields:
        if field not in ohlc_data:
            return False
    
    try:
        open_price = float(ohlc_data['open'])
        high_price = float(ohlc_data['high'])
        low_price = float(ohlc_data['low'])
        close_price = float(ohlc_data['close'])
        volume = int(ohlc_data['volume'])
        
        if any(p <= 0 for p in [open_price, high_price, low_price, close_price]):
            return False
        
        if high_price < low_price:
            return False
        
        if volume < 0:
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def clean_tick_data(tick_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and normalize tick data.
    
    Args:
        tick_data: Raw tick data dictionary
        
    Returns:
        Cleaned tick data dictionary
    """
    cleaned = {
        'instrument_token': int(tick_data['instrument_token']),
        'last_price': float(tick_data['last_price']),
        'volume': int(tick_data.get('volume', 0)),
        'timestamp': tick_data.get('timestamp', datetime.now()),
    }
    
    # Optional fields
    if 'bid_price' in tick_data and tick_data['bid_price'] is not None:
        cleaned['bid_price'] = float(tick_data['bid_price'])
    
    if 'ask_price' in tick_data and tick_data['ask_price'] is not None:
        cleaned['ask_price'] = float(tick_data['ask_price'])
    
    if 'bid_quantity' in tick_data and tick_data['bid_quantity'] is not None:
        cleaned['bid_quantity'] = int(tick_data['bid_quantity'])
    
    if 'ask_quantity' in tick_data and tick_data['ask_quantity'] is not None:
        cleaned['ask_quantity'] = int(tick_data['ask_quantity'])
    
    for field in ['open', 'high', 'low', 'close', 'change']:
        if field in tick_data and tick_data[field] is not None:
            cleaned[field] = float(tick_data[field])
    
    return cleaned


def clean_ohlc_data(ohlc_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and normalize OHLC data.
    
    Args:
        ohlc_data: Raw OHLC data dictionary
        
    Returns:
        Cleaned OHLC data dictionary
    """
    cleaned = {
        'open': float(ohlc_data['open']),
        'high': float(ohlc_data['high']),
        'low': float(ohlc_data['low']),
        'close': float(ohlc_data['close']),
        'volume': int(ohlc_data['volume']),
        'timestamp': ohlc_data.get('timestamp', datetime.now()),
    }
    
    if 'instrument_token' in ohlc_data:
        cleaned['instrument_token'] = int(ohlc_data['instrument_token'])
    
    if 'timeframe' in ohlc_data:
        cleaned['timeframe'] = str(ohlc_data['timeframe'])
    
    return cleaned
