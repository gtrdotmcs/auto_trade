"""
Integration tests for market data feed handler.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock
from kite_auto_trading.services.market_data_feed import (
    MarketDataFeed,
    ConnectionState,
)


class MockAPIClient:
    """Mock API client for testing."""
    
    def __init__(self):
        self.connected = False
        self.subscribed_tokens = []
    
    def connect_websocket(self):
        self.connected = True
    
    def disconnect_websocket(self):
        self.connected = False
    
    def subscribe(self, tokens):
        self.subscribed_tokens.extend(tokens)
    
    def unsubscribe(self, tokens):
        for token in tokens:
            if token in self.subscribed_tokens:
                self.subscribed_tokens.remove(token)


class TestMarketDataFeed:
    """Test cases for MarketDataFeed."""
    
    def test_initialization(self):
        """Test feed initialization."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client, buffer_size=500)
        
        assert feed.buffer_size == 500
        assert feed.state == ConnectionState.DISCONNECTED
        assert len(feed.subscribed_instruments) == 0
    
    def test_connect(self):
        """Test connecting to market data feed."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        result = feed.connect()
        
        assert result is True
        assert feed.is_connected() is True
        assert feed.state == ConnectionState.CONNECTED
        assert feed.last_connection_time is not None
    
    def test_disconnect(self):
        """Test disconnecting from market data feed."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        feed.connect()
        feed.disconnect()
        
        assert feed.state == ConnectionState.DISCONNECTED
        assert len(feed.subscribed_instruments) == 0
    
    def test_subscribe_instruments(self):
        """Test subscribing to instruments."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        feed.connect()
        tokens = [12345, 67890, 11111]
        result = feed.subscribe_instruments(tokens)
        
        assert result is True
        assert len(feed.get_subscribed_instruments()) == 3
        assert 12345 in feed.get_subscribed_instruments()
    
    def test_subscribe_without_connection(self):
        """Test that subscription fails without connection."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        result = feed.subscribe_instruments([12345])
        
        assert result is False
    
    def test_unsubscribe_instruments(self):
        """Test unsubscribing from instruments."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        feed.connect()
        feed.subscribe_instruments([12345, 67890])
        feed.unsubscribe_instruments([12345])
        
        subscribed = feed.get_subscribed_instruments()
        assert 12345 not in subscribed
        assert 67890 in subscribed
    
    def test_process_tick(self):
        """Test processing tick data."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        tick_data = {
            'instrument_token': 12345,
            'last_price': 100.50,
            'volume': 1000,
        }
        
        feed.process_tick(tick_data)
        
        latest = feed.get_latest_tick(12345)
        assert latest is not None
        assert latest['last_price'] == 100.50
        assert 'timestamp' in latest
    
    def test_data_buffering(self):
        """Test data buffer management."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client, buffer_size=5)
        
        # Add 10 ticks
        for i in range(10):
            tick = {
                'instrument_token': 12345,
                'last_price': 100.0 + i,
                'volume': 1000,
            }
            feed.process_tick(tick)
        
        # Buffer should only contain last 5
        buffered = feed.get_buffered_ticks()
        assert len(buffered) == 5
        assert buffered[-1]['last_price'] == 109.0
    
    def test_get_buffered_ticks_with_count(self):
        """Test retrieving specific number of buffered ticks."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        for i in range(10):
            tick = {
                'instrument_token': 12345,
                'last_price': 100.0 + i,
            }
            feed.process_tick(tick)
        
        recent_ticks = feed.get_buffered_ticks(count=3)
        assert len(recent_ticks) == 3
    
    def test_clear_buffer(self):
        """Test clearing data buffer."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        for i in range(5):
            tick = {'instrument_token': 12345, 'last_price': 100.0 + i}
            feed.process_tick(tick)
        
        feed.clear_buffer()
        
        buffered = feed.get_buffered_ticks()
        assert len(buffered) == 0
    
    def test_register_tick_callback(self):
        """Test registering and triggering tick callback."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        callback_data = []
        
        def on_tick(tick):
            callback_data.append(tick)
        
        feed.register_callback('tick', on_tick)
        
        tick = {'instrument_token': 12345, 'last_price': 100.50}
        feed.process_tick(tick)
        
        assert len(callback_data) == 1
        assert callback_data[0]['last_price'] == 100.50
    
    def test_register_connect_callback(self):
        """Test registering and triggering connect callback."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        callback_triggered = []
        
        def on_connect():
            callback_triggered.append(True)
        
        feed.register_callback('connect', on_connect)
        feed.connect()
        
        assert len(callback_triggered) == 1
    
    def test_get_stats(self):
        """Test getting feed statistics."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        feed.connect()
        feed.subscribe_instruments([12345, 67890])
        
        for i in range(5):
            tick = {'instrument_token': 12345, 'last_price': 100.0 + i}
            feed.process_tick(tick)
        
        stats = feed.get_stats()
        
        assert stats['state'] == ConnectionState.CONNECTED.value
        assert stats['subscribed_instruments'] == 2
        assert stats['buffered_ticks'] == 5
        assert stats['reconnect_count'] == 0
    
    def test_connection_state_transitions(self):
        """Test connection state transitions."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        assert feed.get_connection_state() == ConnectionState.DISCONNECTED
        
        feed.connect()
        assert feed.get_connection_state() == ConnectionState.CONNECTED
        
        feed.disconnect()
        assert feed.get_connection_state() == ConnectionState.DISCONNECTED
    
    def test_multiple_instrument_ticks(self):
        """Test handling ticks from multiple instruments."""
        api_client = MockAPIClient()
        feed = MarketDataFeed(api_client)
        
        feed.connect()
        feed.subscribe_instruments([12345, 67890])
        
        tick1 = {'instrument_token': 12345, 'last_price': 100.50}
        tick2 = {'instrument_token': 67890, 'last_price': 200.75}
        
        feed.process_tick(tick1)
        feed.process_tick(tick2)
        
        latest1 = feed.get_latest_tick(12345)
        latest2 = feed.get_latest_tick(67890)
        
        assert latest1['last_price'] == 100.50
        assert latest2['last_price'] == 200.75
