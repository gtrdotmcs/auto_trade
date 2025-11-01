"""
Kite Connect API client implementation with authentication and session management.
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from kiteconnect import KiteConnect
from kiteconnect.exceptions import (
    KiteException, 
    NetworkException, 
    TokenException,
    PermissionException,
    OrderException,
    InputException
)

from kite_auto_trading.api.base import TradingAPIClient, MarketDataAPIClient
from kite_auto_trading.models.base import Order, Position, OrderStatus, TransactionType, OrderType
from kite_auto_trading.config.models import APIConfig


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages API session persistence and recovery."""
    
    def __init__(self, session_file: str = "session.json"):
        self.session_file = Path(session_file)
        self.session_data = {}
        self._load_session()
    
    def _load_session(self) -> None:
        """Load session data from file."""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    self.session_data = json.load(f)
                logger.info("Session data loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load session data: {e}")
            self.session_data = {}
    
    def save_session(self, api_key: str, access_token: str, user_id: str = None) -> None:
        """Save session data to file."""
        try:
            self.session_data = {
                'api_key': api_key,
                'access_token': access_token,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(hours=8)).isoformat()  # Kite tokens expire in 8 hours
            }
            
            # Ensure directory exists
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.session_file, 'w') as f:
                json.dump(self.session_data, f, indent=2)
            logger.info("Session data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")
    
    def get_session(self) -> Optional[Dict[str, Any]]:
        """Get current session data if valid."""
        if not self.session_data:
            return None
        
        try:
            expires_at = datetime.fromisoformat(self.session_data.get('expires_at', ''))
            if datetime.now() >= expires_at:
                logger.info("Session expired")
                self.clear_session()
                return None
            return self.session_data
        except Exception as e:
            logger.warning(f"Invalid session data: {e}")
            self.clear_session()
            return None
    
    def clear_session(self) -> None:
        """Clear session data."""
        self.session_data = {}
        try:
            if self.session_file.exists():
                self.session_file.unlink()
            logger.info("Session data cleared")
        except Exception as e:
            logger.warning(f"Failed to clear session file: {e}")


class KiteAPIClient(TradingAPIClient, MarketDataAPIClient):
    """
    Kite Connect API client with comprehensive authentication, session management,
    and error handling capabilities.
    """
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.kite = None
        self.session_manager = SessionManager()
        self._authenticated = False
        self._user_profile = None
        self._last_request_time = 0
        self._setup_session()
        
        logger.info("KiteAPIClient initialized")
    
    def _setup_session(self) -> None:
        """Setup HTTP session with retry strategy."""
        if self.config.api_key:
            self.kite = KiteConnect(api_key=self.config.api_key)
            
            # Configure session with retry strategy
            retry_strategy = Retry(
                total=self.config.max_retries,
                backoff_factor=self.config.retry_delay,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.kite.reqsession.mount("http://", adapter)
            self.kite.reqsession.mount("https://", adapter)
            self.kite.reqsession.timeout = self.config.timeout
    
    def _rate_limit(self) -> None:
        """Implement rate limiting between API calls."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.config.rate_limit_delay:
            sleep_time = self.config.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _handle_api_error(self, error: Exception) -> None:
        """Handle and log API errors appropriately."""
        if isinstance(error, TokenException):
            logger.error(f"Authentication error: {error}")
            self._authenticated = False
            self.session_manager.clear_session()
        elif isinstance(error, NetworkException):
            logger.error(f"Network error: {error}")
        elif isinstance(error, PermissionException):
            logger.error(f"Permission error: {error}")
        elif isinstance(error, OrderException):
            logger.error(f"Order error: {error}")
        elif isinstance(error, InputException):
            logger.error(f"Input validation error: {error}")
        else:
            logger.error(f"Unexpected API error: {error}")
    
    def authenticate(self, api_key: str, access_token: str) -> bool:
        """
        Authenticate with Kite Connect API.
        
        Args:
            api_key: Kite Connect API key
            access_token: Access token obtained from login flow
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            if not api_key or not access_token:
                logger.error("API key and access token are required")
                return False
            
            # Update config and setup session
            self.config.api_key = api_key
            self.config.access_token = access_token
            self._setup_session()
            
            if not self.kite:
                logger.error("Failed to initialize Kite client")
                return False
            
            # Set access token
            self.kite.set_access_token(access_token)
            
            # Validate authentication by fetching profile
            self._rate_limit()
            profile = self.kite.profile()
            
            if profile and profile.get('user_id'):
                self._authenticated = True
                self._user_profile = profile
                
                # Save session for persistence
                self.session_manager.save_session(
                    api_key=api_key,
                    access_token=access_token,
                    user_id=profile.get('user_id')
                )
                
                logger.info(f"Authentication successful for user: {profile.get('user_name')}")
                return True
            else:
                logger.error("Invalid authentication response")
                return False
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if client is currently authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self._authenticated or not self.kite:
            return False
        
        try:
            # Validate by making a lightweight API call
            self._rate_limit()
            profile = self.kite.profile()
            return profile is not None and profile.get('user_id') is not None
        except TokenException:
            logger.warning("Authentication token expired or invalid")
            self._authenticated = False
            return False
        except Exception as e:
            logger.warning(f"Authentication check failed: {e}")
            return False
    
    def auto_authenticate(self) -> bool:
        """
        Attempt automatic authentication using saved session.
        
        Returns:
            True if auto-authentication successful, False otherwise
        """
        session = self.session_manager.get_session()
        if not session:
            logger.info("No valid session found for auto-authentication")
            return False
        
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        if not api_key or not access_token:
            logger.warning("Incomplete session data for auto-authentication")
            return False
        
        logger.info("Attempting auto-authentication with saved session")
        return self.authenticate(api_key, access_token)
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Returns:
            User profile data
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            return self.kite.profile()
        except Exception as e:
            self._handle_api_error(e)
            raise
    
    def validate_token(self) -> Tuple[bool, Optional[str]]:
        """
        Validate current access token.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not self.kite or not self._authenticated:
                return False, "Not authenticated"
            
            self._rate_limit()
            profile = self.kite.profile()
            
            if profile and profile.get('user_id'):
                return True, None
            else:
                return False, "Invalid token response"
                
        except TokenException as e:
            return False, f"Token validation failed: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def refresh_session(self) -> bool:
        """
        Refresh the current session by re-authenticating.
        
        Returns:
            True if session refresh successful, False otherwise
        """
        session = self.session_manager.get_session()
        if not session:
            logger.warning("No session data available for refresh")
            return False
        
        # Clear current authentication state
        self._authenticated = False
        
        # Attempt re-authentication
        return self.authenticate(
            session.get('api_key'),
            session.get('access_token')
        )
    
    # Trading API methods
    def place_order(self, order: Order) -> str:
        """
        Place a trading order.
        
        Args:
            order: Order object containing order details
            
        Returns:
            Order ID if successful
            
        Raises:
            Exception: If not authenticated or order placement fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            # Convert Order object to Kite API format
            order_params = {
                'tradingsymbol': order.instrument,
                'exchange': 'NSE',  # Default to NSE, can be made configurable
                'transaction_type': order.transaction_type.value,
                'quantity': order.quantity,
                'order_type': self._convert_order_type(order.order_type),
                'product': 'MIS',  # Default to MIS (Margin Intraday Square-off)
                'validity': 'DAY'
            }
            
            # Add price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.SL]:
                if order.price is None:
                    raise ValueError("Price is required for LIMIT and SL orders")
                order_params['price'] = order.price
            
            # Add trigger price for stop-loss orders
            if order.order_type in [OrderType.SL, OrderType.SL_M]:
                if order.trigger_price is None:
                    raise ValueError("Trigger price is required for SL and SL-M orders")
                order_params['trigger_price'] = order.trigger_price
            
            # Place the order
            response = self.kite.place_order(**order_params)
            
            if response and response.get('order_id'):
                logger.info(f"Order placed successfully: {response['order_id']}")
                return response['order_id']
            else:
                raise Exception("Invalid order response")
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to place order: {e}")
            raise
    
    def modify_order(self, order_id: str, modifications: Dict[str, Any]) -> bool:
        """
        Modify an existing order.
        
        Args:
            order_id: ID of the order to modify
            modifications: Dictionary of fields to modify
            
        Returns:
            True if modification successful, False otherwise
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            # Convert modifications to Kite API format
            modify_params = {}
            
            if 'quantity' in modifications:
                modify_params['quantity'] = modifications['quantity']
            
            if 'price' in modifications:
                modify_params['price'] = modifications['price']
            
            if 'trigger_price' in modifications:
                modify_params['trigger_price'] = modifications['trigger_price']
            
            if 'order_type' in modifications:
                modify_params['order_type'] = self._convert_order_type(modifications['order_type'])
            
            response = self.kite.modify_order(order_id, **modify_params)
            
            if response and response.get('order_id'):
                logger.info(f"Order modified successfully: {order_id}")
                return True
            else:
                logger.warning(f"Order modification failed: {order_id}")
                return False
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to modify order {order_id}: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            response = self.kite.cancel_order(order_id)
            
            if response and response.get('order_id'):
                logger.info(f"Order cancelled successfully: {order_id}")
                return True
            else:
                logger.warning(f"Order cancellation failed: {order_id}")
                return False
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all orders for the day.
        
        Returns:
            List of order dictionaries
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            orders = self.kite.orders()
            
            if orders is not None:
                logger.debug(f"Retrieved {len(orders)} orders")
                return orders
            else:
                logger.warning("No orders data received")
                return []
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get orders: {e}")
            raise
    
    def get_positions(self) -> List[Position]:
        """
        Get current positions.
        
        Returns:
            List of Position objects
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            positions_data = self.kite.positions()
            
            if not positions_data:
                return []
            
            positions = []
            
            # Process both day and net positions
            all_positions = positions_data.get('day', []) + positions_data.get('net', [])
            
            for pos_data in all_positions:
                if pos_data.get('quantity', 0) != 0:  # Only include non-zero positions
                    position = Position(
                        instrument=pos_data.get('tradingsymbol', ''),
                        quantity=pos_data.get('quantity', 0),
                        average_price=pos_data.get('average_price', 0.0),
                        current_price=pos_data.get('last_price', 0.0),
                        unrealized_pnl=pos_data.get('unrealised', 0.0),
                        strategy_id='',  # Will be set by strategy manager
                        entry_time=datetime.now()  # Approximate, actual time not available from API
                    )
                    positions.append(position)
            
            logger.debug(f"Retrieved {len(positions)} positions")
            return positions
            
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get positions: {e}")
            raise
    
    def get_funds(self) -> Dict[str, Any]:
        """
        Get available funds and margins.
        
        Returns:
            Dictionary containing funds information
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            margins = self.kite.margins()
            
            if margins:
                # Extract key fund information
                equity_margin = margins.get('equity', {})
                
                funds_info = {
                    'available_cash': equity_margin.get('available', {}).get('cash', 0.0),
                    'available_margin': equity_margin.get('available', {}).get('adhoc_margin', 0.0),
                    'used_margin': equity_margin.get('utilised', {}).get('debits', 0.0),
                    'total_margin': equity_margin.get('net', 0.0),
                    'raw_data': margins  # Include raw data for advanced use cases
                }
                
                logger.debug(f"Retrieved funds info: Available cash: {funds_info['available_cash']}")
                return funds_info
            else:
                logger.warning("No funds data received")
                return {}
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get funds: {e}")
            raise
    
    def _convert_order_type(self, order_type: OrderType) -> str:
        """
        Convert internal OrderType enum to Kite API format.
        
        Args:
            order_type: Internal OrderType enum value
            
        Returns:
            Kite API compatible order type string
        """
        conversion_map = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
            OrderType.SL: 'SL',
            OrderType.SL_M: 'SL-M'
        }
        
        return conversion_map.get(order_type, 'MARKET')
    
    # Market Data API methods
    def get_instruments(self) -> List[Dict[str, Any]]:
        """
        Get list of available instruments.
        
        Returns:
            List of instrument dictionaries
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            # Get instruments for NSE (can be extended for other exchanges)
            instruments = self.kite.instruments('NSE')
            
            if instruments is not None:
                logger.debug(f"Retrieved {len(instruments)} instruments")
                return instruments
            else:
                logger.warning("No instruments data received")
                return []
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get instruments: {e}")
            raise
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get current quotes for instruments.
        
        Args:
            instruments: List of instrument identifiers (trading symbols or tokens)
            
        Returns:
            Dictionary containing quote data for each instrument
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        if not instruments:
            return {}
        
        try:
            self._rate_limit()
            
            # Convert trading symbols to full instrument identifiers if needed
            formatted_instruments = []
            for instrument in instruments:
                if ':' not in instrument:
                    # Assume NSE if no exchange specified
                    formatted_instruments.append(f'NSE:{instrument}')
                else:
                    formatted_instruments.append(instrument)
            
            quotes = self.kite.quote(formatted_instruments)
            
            if quotes is not None:
                logger.debug(f"Retrieved quotes for {len(quotes)} instruments")
                return quotes
            else:
                logger.warning("No quote data received")
                return {}
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get quotes: {e}")
            raise
    
    def get_historical_data(
        self, 
        instrument_token: str, 
        from_date: str, 
        to_date: str, 
        interval: str
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for an instrument.
        
        Args:
            instrument_token: Instrument token or trading symbol
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            interval: Data interval (minute, 5minute, 15minute, day, etc.)
            
        Returns:
            List of historical data records
            
        Raises:
            Exception: If not authenticated or API call fails
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            self._rate_limit()
            
            # Convert string dates to datetime objects if needed
            from datetime import datetime as dt
            
            if isinstance(from_date, str):
                from_date = dt.strptime(from_date, '%Y-%m-%d')
            if isinstance(to_date, str):
                to_date = dt.strptime(to_date, '%Y-%m-%d')
            
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            if historical_data is not None:
                logger.debug(f"Retrieved {len(historical_data)} historical records")
                return historical_data
            else:
                logger.warning("No historical data received")
                return []
                
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to get historical data: {e}")
            raise
    
    def start_websocket(self, instruments: List[str]) -> None:
        """
        Start WebSocket connection for live data.
        
        Args:
            instruments: List of instrument tokens to subscribe to
            
        Note:
            This is a placeholder implementation. Full WebSocket functionality
            will be implemented in the market data management system.
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        try:
            logger.info(f"WebSocket subscription requested for {len(instruments)} instruments")
            # Placeholder - actual WebSocket implementation will be in market data manager
            # This method serves as the interface for future implementation
            
        except Exception as e:
            self._handle_api_error(e)
            logger.error(f"Failed to start WebSocket: {e}")
            raise
    
    def stop_websocket(self) -> None:
        """
        Stop WebSocket connection.
        
        Note:
            This is a placeholder implementation. Full WebSocket functionality
            will be implemented in the market data management system.
        """
        try:
            logger.info("WebSocket disconnection requested")
            # Placeholder - actual WebSocket implementation will be in market data manager
            # This method serves as the interface for future implementation
            
        except Exception as e:
            logger.error(f"Failed to stop WebSocket: {e}")
            raise