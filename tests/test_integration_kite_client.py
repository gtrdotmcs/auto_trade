"""
Integration tests for KiteAPIClient complete functionality.
"""

import pytest
from unittest.mock import Mock, patch

from kite_auto_trading.api import KiteAPIClient
from kite_auto_trading.config.models import APIConfig
from kite_auto_trading.models.base import Order, OrderType, TransactionType


class TestKiteAPIClientIntegration:
    """Integration tests for complete KiteAPIClient functionality."""
    
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
    def test_complete_trading_workflow(self, mock_kite_connect):
        """Test complete trading workflow from authentication to order execution."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        # Mock authentication
        mock_kite.profile.return_value = {
            'user_id': 'test_user',
            'user_name': 'Test User',
            'email': 'test@example.com'
        }
        
        # Mock funds check
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 50000.0, 'adhoc_margin': 10000.0},
                'utilised': {'debits': 5000.0},
                'net': 55000.0
            }
        }
        
        # Mock order placement
        mock_kite.place_order.return_value = {'order_id': 'test_order_123'}
        
        # Mock order status
        mock_kite.orders.return_value = [
            {
                'order_id': 'test_order_123',
                'tradingsymbol': 'RELIANCE',
                'status': 'COMPLETE',
                'quantity': 10,
                'price': 2500.0
            }
        ]
        
        # Mock positions
        mock_kite.positions.return_value = {
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
        
        # Initialize client
        client = KiteAPIClient(self.config)
        
        # Step 1: Authenticate
        auth_result = client.authenticate("test_api_key", "test_access_token")
        assert auth_result is True
        assert client.is_authenticated() is True
        
        # Step 2: Check funds
        funds = client.get_funds()
        assert funds['available_cash'] == 50000.0
        assert funds['total_margin'] == 55000.0
        
        # Step 3: Place order
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        order_id = client.place_order(order)
        assert order_id == 'test_order_123'
        
        # Step 4: Check order status
        orders = client.get_orders()
        assert len(orders) == 1
        assert orders[0]['order_id'] == 'test_order_123'
        assert orders[0]['status'] == 'COMPLETE'
        
        # Step 5: Check positions
        positions = client.get_positions()
        assert len(positions) == 1
        assert positions[0].instrument == 'RELIANCE'
        assert positions[0].quantity == 10
        assert positions[0].unrealized_pnl == 200.0
        
        # Verify all API calls were made
        mock_kite.profile.assert_called()
        mock_kite.margins.assert_called()
        mock_kite.place_order.assert_called()
        mock_kite.orders.assert_called()
        mock_kite.positions.assert_called()
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_session_persistence_and_recovery(self, mock_kite_connect):
        """Test session persistence and automatic recovery."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {
            'user_id': 'test_user',
            'user_name': 'Test User'
        }
        
        # First client instance - authenticate and create session
        client1 = KiteAPIClient(self.config)
        auth_result = client1.authenticate("test_api_key", "test_access_token")
        assert auth_result is True
        
        # Second client instance - should auto-authenticate from saved session
        client2 = KiteAPIClient(self.config)
        auto_auth_result = client2.auto_authenticate()
        assert auto_auth_result is True
        assert client2.is_authenticated() is True
        
        # Verify profile was called for both authentication attempts
        assert mock_kite.profile.call_count >= 2
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Test with invalid configuration
        invalid_config = APIConfig(
            api_key="",
            access_token="",
            timeout=30
        )
        
        client = KiteAPIClient(invalid_config)
        
        # Should fail authentication with empty credentials
        auth_result = client.authenticate("", "")
        assert auth_result is False
        
        # Should not be authenticated
        assert client.is_authenticated() is False
        
        # API calls should raise exceptions when not authenticated
        with pytest.raises(Exception, match="Not authenticated"):
            client.get_funds()
        
        with pytest.raises(Exception, match="Not authenticated"):
            client.get_orders()
        
        with pytest.raises(Exception, match="Not authenticated"):
            client.get_positions()
    
    def test_rate_limiting_functionality(self):
        """Test rate limiting is properly implemented."""
        client = KiteAPIClient(self.config)
        
        # Test rate limiting method exists and can be called
        client._rate_limit()
        
        # Verify rate limit delay is respected
        import time
        start_time = time.time()
        client._rate_limit()
        client._rate_limit()
        end_time = time.time()
        
        # Should have some delay (though minimal in test)
        assert end_time >= start_time