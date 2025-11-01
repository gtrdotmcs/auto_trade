"""
Unit tests for KiteAPIClient core API operations.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from kiteconnect.exceptions import OrderException, NetworkException
from kite_auto_trading.api.kite_client import KiteAPIClient
from kite_auto_trading.config.models import APIConfig
from kite_auto_trading.models.base import Order, Position, OrderType, TransactionType, OrderStatus


class TestKiteAPIClientCoreOperations:
    """Test cases for KiteAPIClient core API operations."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = APIConfig(
            api_key="test_api_key",
            access_token="test_access_token",
            timeout=30,
            max_retries=3,
            retry_delay=1.0,
            rate_limit_delay=0.1
        )
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_place_order_success(self, mock_kite_connect):
        """Test successful order placement."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.place_order.return_value = {'order_id': 'test_order_123'}
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Create test order
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        # Test order placement
        order_id = client.place_order(order)
        
        assert order_id == 'test_order_123'
        mock_kite.place_order.assert_called_once()
        
        # Verify order parameters
        call_args = mock_kite.place_order.call_args[1]
        assert call_args['tradingsymbol'] == 'RELIANCE'
        assert call_args['transaction_type'] == 'BUY'
        assert call_args['quantity'] == 10
        assert call_args['order_type'] == 'MARKET'
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_place_limit_order_with_price(self, mock_kite_connect):
        """Test placing limit order with price."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.place_order.return_value = {'order_id': 'test_order_456'}
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Create limit order
        order = Order(
            instrument='INFY',
            transaction_type=TransactionType.SELL,
            quantity=5,
            order_type=OrderType.LIMIT,
            price=1500.0
        )
        
        # Test order placement
        order_id = client.place_order(order)
        
        assert order_id == 'test_order_456'
        
        # Verify price is included
        call_args = mock_kite.place_order.call_args[1]
        assert call_args['price'] == 1500.0
        assert call_args['order_type'] == 'LIMIT'
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_place_order_not_authenticated(self, mock_kite_connect):
        """Test order placement when not authenticated."""
        client = KiteAPIClient(self.config)
        client._authenticated = False
        
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        with pytest.raises(Exception, match="Not authenticated"):
            client.place_order(order)
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_place_order_api_error(self, mock_kite_connect):
        """Test order placement API error handling."""
        # Setup mock to raise exception
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.place_order.side_effect = OrderException("Order rejected")
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        with pytest.raises(OrderException):
            client.place_order(order)
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_modify_order_success(self, mock_kite_connect):
        """Test successful order modification."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.modify_order.return_value = {'order_id': 'test_order_123'}
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test order modification
        modifications = {'quantity': 20, 'price': 1600.0}
        result = client.modify_order('test_order_123', modifications)
        
        assert result is True
        mock_kite.modify_order.assert_called_once_with(
            'test_order_123', 
            quantity=20, 
            price=1600.0
        )
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_cancel_order_success(self, mock_kite_connect):
        """Test successful order cancellation."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.cancel_order.return_value = {'order_id': 'test_order_123'}
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test order cancellation
        result = client.cancel_order('test_order_123')
        
        assert result is True
        mock_kite.cancel_order.assert_called_once_with('test_order_123')
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_get_orders_success(self, mock_kite_connect):
        """Test successful orders retrieval."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        
        mock_orders = [
            {'order_id': '1', 'tradingsymbol': 'RELIANCE', 'status': 'COMPLETE'},
            {'order_id': '2', 'tradingsymbol': 'INFY', 'status': 'OPEN'}
        ]
        mock_kite.orders.return_value = mock_orders
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test orders retrieval
        orders = client.get_orders()
        
        assert len(orders) == 2
        assert orders[0]['order_id'] == '1'
        assert orders[1]['tradingsymbol'] == 'INFY'
        mock_kite.orders.assert_called_once()
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_get_positions_success(self, mock_kite_connect):
        """Test successful positions retrieval."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        
        mock_positions = {
            'day': [
                {
                    'tradingsymbol': 'RELIANCE',
                    'quantity': 10,
                    'average_price': 2500.0,
                    'last_price': 2520.0,
                    'unrealised': 200.0
                }
            ],
            'net': []
        }
        mock_kite.positions.return_value = mock_positions
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test positions retrieval
        positions = client.get_positions()
        
        assert len(positions) == 1
        assert positions[0].instrument == 'RELIANCE'
        assert positions[0].quantity == 10
        assert positions[0].average_price == 2500.0
        assert positions[0].unrealized_pnl == 200.0
        mock_kite.positions.assert_called_once()
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_get_funds_success(self, mock_kite_connect):
        """Test successful funds retrieval."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        
        mock_margins = {
            'equity': {
                'available': {'cash': 50000.0, 'adhoc_margin': 10000.0},
                'utilised': {'debits': 5000.0},
                'net': 55000.0
            }
        }
        mock_kite.margins.return_value = mock_margins
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test funds retrieval
        funds = client.get_funds()
        
        assert funds['available_cash'] == 50000.0
        assert funds['available_margin'] == 10000.0
        assert funds['used_margin'] == 5000.0
        assert funds['total_margin'] == 55000.0
        mock_kite.margins.assert_called_once()
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_get_quote_success(self, mock_kite_connect):
        """Test successful quote retrieval."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        
        mock_quotes = {
            'NSE:RELIANCE': {
                'last_price': 2520.0,
                'volume': 1000000,
                'ohlc': {'open': 2500.0, 'high': 2530.0, 'low': 2495.0, 'close': 2520.0}
            }
        }
        mock_kite.quote.return_value = mock_quotes
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test quote retrieval
        quotes = client.get_quote(['RELIANCE'])
        
        assert 'NSE:RELIANCE' in quotes
        assert quotes['NSE:RELIANCE']['last_price'] == 2520.0
        mock_kite.quote.assert_called_once_with(['NSE:RELIANCE'])
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_get_historical_data_success(self, mock_kite_connect):
        """Test successful historical data retrieval."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        
        mock_historical = [
            {'date': '2023-01-01', 'open': 2500.0, 'high': 2520.0, 'low': 2495.0, 'close': 2510.0},
            {'date': '2023-01-02', 'open': 2510.0, 'high': 2530.0, 'low': 2505.0, 'close': 2525.0}
        ]
        mock_kite.historical_data.return_value = mock_historical
        
        client = KiteAPIClient(self.config)
        client._authenticated = True
        
        # Test historical data retrieval
        data = client.get_historical_data('738561', '2023-01-01', '2023-01-02', 'day')
        
        assert len(data) == 2
        assert data[0]['open'] == 2500.0
        assert data[1]['close'] == 2525.0
        mock_kite.historical_data.assert_called_once()
    
    def test_convert_order_type(self):
        """Test order type conversion."""
        client = KiteAPIClient(self.config)
        
        assert client._convert_order_type(OrderType.MARKET) == 'MARKET'
        assert client._convert_order_type(OrderType.LIMIT) == 'LIMIT'
        assert client._convert_order_type(OrderType.SL) == 'SL'
        assert client._convert_order_type(OrderType.SL_M) == 'SL-M'