"""
Unit tests for KiteAPIClient authentication and session management.
"""

import json
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime, timedelta

from kiteconnect.exceptions import TokenException
from kite_auto_trading.api.kite_client import KiteAPIClient, SessionManager
from kite_auto_trading.config.models import APIConfig


class TestSessionManager:
    """Test cases for SessionManager class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.session_file = "test_session.json"
        self.session_manager = SessionManager(self.session_file)
    
    def teardown_method(self):
        """Cleanup test files."""
        session_path = Path(self.session_file)
        if session_path.exists():
            session_path.unlink()
    
    def test_save_and_load_session(self):
        """Test saving and loading session data."""
        api_key = "test_api_key"
        access_token = "test_access_token"
        user_id = "test_user"
        
        # Save session
        self.session_manager.save_session(api_key, access_token, user_id)
        
        # Load session
        session = self.session_manager.get_session()
        
        assert session is not None
        assert session['api_key'] == api_key
        assert session['access_token'] == access_token
        assert session['user_id'] == user_id
        assert 'timestamp' in session
        assert 'expires_at' in session


class TestKiteAPIClient:
    """Test cases for KiteAPIClient authentication functionality."""
    
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
    def test_initialization(self, mock_kite_connect):
        """Test KiteAPIClient initialization."""
        client = KiteAPIClient(self.config)
        
        assert client.config == self.config
        assert not client._authenticated
        assert client._user_profile is None
        mock_kite_connect.assert_called_once_with(api_key=self.config.api_key)
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_successful_authentication(self, mock_kite_connect):
        """Test successful authentication flow."""
        # Setup mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.return_value = {
            'user_id': 'test_user',
            'user_name': 'Test User',
            'email': 'test@example.com'
        }
        
        client = KiteAPIClient(self.config)
        
        # Test authentication
        result = client.authenticate("test_api_key", "test_access_token")
        
        assert result is True
        assert client._authenticated is True
        assert client._user_profile is not None
        mock_kite.set_access_token.assert_called_once_with("test_access_token")
        mock_kite.profile.assert_called()
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_authentication_failure(self, mock_kite_connect):
        """Test authentication failure handling."""
        # Setup mock to raise exception
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        mock_kite.profile.side_effect = TokenException("Invalid token")
        
        client = KiteAPIClient(self.config)
        
        # Test authentication failure
        result = client.authenticate("test_api_key", "invalid_token")
        
        assert result is False
        assert client._authenticated is False
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_is_authenticated_check(self, mock_kite_connect):
        """Test authentication status checking."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        client = KiteAPIClient(self.config)
        
        # Initially not authenticated
        assert client.is_authenticated() is False
        
        # Mock successful profile call
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        client._authenticated = True
        
        assert client.is_authenticated() is True