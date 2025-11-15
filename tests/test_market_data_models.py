"""
Unit tests for market data models and validation utilities.
"""

import pytest
from datetime import datetime
from kite_auto_trading.models.market_data import (
    Tick,
    OHLC,
    Instrument,
    InstrumentType,
    MarketDepth,
    validate_tick_data,
    validate_ohlc_data,
    clean_tick_data,
    clean_ohlc_data,
)


class TestTick:
    """Test cases for Tick data model."""
    
    def test_valid_tick_creation(self):
        """Test creating a valid tick."""
        tick = Tick(
            instrument_token=12345,
            timestamp=datetime.now(),
            last_price=100.50,
            volume=1000,
            bid_price=100.25,
            ask_price=100.75,
            bid_quantity=500,
            ask_quantity=300
        )
        assert tick.instrument_token == 12345
        assert tick.last_price == 100.50
        assert tick.volume == 1000
    
    def test_tick_with_invalid_price(self):
        """Test that tick with invalid price raises error."""
        with pytest.raises(ValueError, match="Invalid last_price"):
            Tick(
                instrument_token=12345,
                timestamp=datetime.now(),
                last_price=-10.0,
                volume=1000
            )
    
    def test_tick_with_negative_volume(self):
        """Test that tick with negative volume raises error."""
        with pytest.raises(ValueError, match="Invalid volume"):
            Tick(
                instrument_token=12345,
                timestamp=datetime.now(),
                last_price=100.0,
                volume=-100
            )


class TestOHLC:
    """Test cases for OHLC data model."""
    
    def test_valid_ohlc_creation(self):
        """Test creating a valid OHLC candle."""
        ohlc = OHLC(
            instrument_token=12345,
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=5000,
            timeframe='5minute'
        )
        assert ohlc.open == 100.0
        assert ohlc.high == 105.0
        assert ohlc.low == 99.0
        assert ohlc.close == 103.0
    
    def test_ohlc_high_less_than_low(self):
        """Test that OHLC with high < low raises error."""
        with pytest.raises(ValueError, match="High.*cannot be less than Low"):
            OHLC(
                instrument_token=12345,
                timestamp=datetime.now(),
                open=100.0,
                high=95.0,
                low=99.0,
                close=98.0,
                volume=1000,
                timeframe='1minute'
            )
    
    def test_ohlc_is_bullish(self):
        """Test bullish candle detection."""
        ohlc = OHLC(
            instrument_token=12345,
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000,
            timeframe='5minute'
        )
        assert ohlc.is_bullish() is True
        assert ohlc.is_bearish() is False
    
    def test_ohlc_is_bearish(self):
        """Test bearish candle detection."""
        ohlc = OHLC(
            instrument_token=12345,
            timestamp=datetime.now(),
            open=103.0,
            high=105.0,
            low=99.0,
            close=100.0,
            volume=1000,
            timeframe='5minute'
        )
        assert ohlc.is_bearish() is True
        assert ohlc.is_bullish() is False
    
    def test_ohlc_body_size(self):
        """Test candle body size calculation."""
        ohlc = OHLC(
            instrument_token=12345,
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000,
            timeframe='5minute'
        )
        assert ohlc.body_size() == 3.0
    
    def test_ohlc_range_size(self):
        """Test candle range size calculation."""
        ohlc = OHLC(
            instrument_token=12345,
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000,
            timeframe='5minute'
        )
        assert ohlc.range_size() == 6.0


class TestInstrument:
    """Test cases for Instrument data model."""
    
    def test_valid_instrument_creation(self):
        """Test creating a valid instrument."""
        instrument = Instrument(
            instrument_token=12345,
            exchange_token=67890,
            tradingsymbol='INFY',
            name='Infosys Limited',
            exchange='NSE',
            instrument_type=InstrumentType.EQUITY,
            segment='NSE',
            tick_size=0.05,
            lot_size=1
        )
        assert instrument.tradingsymbol == 'INFY'
        assert instrument.instrument_type == InstrumentType.EQUITY
    
    def test_instrument_with_empty_symbol(self):
        """Test that instrument with empty symbol raises error."""
        with pytest.raises(ValueError, match="Trading symbol cannot be empty"):
            Instrument(
                instrument_token=12345,
                exchange_token=67890,
                tradingsymbol='',
                name='Test',
                exchange='NSE',
                instrument_type=InstrumentType.EQUITY,
                segment='NSE'
            )
    
    def test_instrument_is_derivative(self):
        """Test derivative detection."""
        futures = Instrument(
            instrument_token=12345,
            exchange_token=67890,
            tradingsymbol='NIFTY24JANFUT',
            name='Nifty Futures',
            exchange='NFO',
            instrument_type=InstrumentType.FUTURES,
            segment='NFO-FUT',
            expiry=datetime(2024, 1, 25)
        )
        assert futures.is_derivative() is True
        
        equity = Instrument(
            instrument_token=12345,
            exchange_token=67890,
            tradingsymbol='INFY',
            name='Infosys',
            exchange='NSE',
            instrument_type=InstrumentType.EQUITY,
            segment='NSE'
        )
        assert equity.is_derivative() is False


class TestMarketDepth:
    """Test cases for MarketDepth data model."""
    
    def test_market_depth_best_bid_ask(self):
        """Test getting best bid and ask from market depth."""
        depth = MarketDepth(
            instrument_token=12345,
            timestamp=datetime.now(),
            bids=[
                {'price': 100.25, 'quantity': 500, 'orders': 5},
                {'price': 100.20, 'quantity': 300, 'orders': 3}
            ],
            asks=[
                {'price': 100.30, 'quantity': 400, 'orders': 4},
                {'price': 100.35, 'quantity': 200, 'orders': 2}
            ]
        )
        
        best_bid = depth.get_best_bid()
        assert best_bid['price'] == 100.25
        
        best_ask = depth.get_best_ask()
        assert best_ask['price'] == 100.30
    
    def test_market_depth_spread(self):
        """Test spread calculation."""
        depth = MarketDepth(
            instrument_token=12345,
            timestamp=datetime.now(),
            bids=[{'price': 100.25, 'quantity': 500, 'orders': 5}],
            asks=[{'price': 100.30, 'quantity': 400, 'orders': 4}]
        )
        
        spread = depth.get_spread()
        assert abs(spread - 0.05) < 0.001


class TestValidationFunctions:
    """Test cases for validation utility functions."""
    
    def test_validate_tick_data_valid(self):
        """Test validation of valid tick data."""
        tick_data = {
            'instrument_token': 12345,
            'last_price': 100.50,
            'volume': 1000
        }
        assert validate_tick_data(tick_data) is True
    
    def test_validate_tick_data_missing_field(self):
        """Test validation fails with missing required field."""
        tick_data = {
            'instrument_token': 12345
        }
        assert validate_tick_data(tick_data) is False
    
    def test_validate_tick_data_invalid_price(self):
        """Test validation fails with invalid price."""
        tick_data = {
            'instrument_token': 12345,
            'last_price': -10.0
        }
        assert validate_tick_data(tick_data) is False
    
    def test_validate_ohlc_data_valid(self):
        """Test validation of valid OHLC data."""
        ohlc_data = {
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0,
            'volume': 5000
        }
        assert validate_ohlc_data(ohlc_data) is True
    
    def test_validate_ohlc_data_invalid_high_low(self):
        """Test validation fails when high < low."""
        ohlc_data = {
            'open': 100.0,
            'high': 95.0,
            'low': 99.0,
            'close': 98.0,
            'volume': 1000
        }
        assert validate_ohlc_data(ohlc_data) is False


class TestCleaningFunctions:
    """Test cases for data cleaning utility functions."""
    
    def test_clean_tick_data(self):
        """Test cleaning of tick data."""
        raw_data = {
            'instrument_token': '12345',
            'last_price': '100.50',
            'volume': '1000',
            'bid_price': '100.25',
            'ask_price': '100.75'
        }
        
        cleaned = clean_tick_data(raw_data)
        
        assert cleaned['instrument_token'] == 12345
        assert cleaned['last_price'] == 100.50
        assert cleaned['volume'] == 1000
        assert cleaned['bid_price'] == 100.25
        assert cleaned['ask_price'] == 100.75
    
    def test_clean_ohlc_data(self):
        """Test cleaning of OHLC data."""
        raw_data = {
            'open': '100.0',
            'high': '105.0',
            'low': '99.0',
            'close': '103.0',
            'volume': '5000'
        }
        
        cleaned = clean_ohlc_data(raw_data)
        
        assert cleaned['open'] == 100.0
        assert cleaned['high'] == 105.0
        assert cleaned['low'] == 99.0
        assert cleaned['close'] == 103.0
        assert cleaned['volume'] == 5000
