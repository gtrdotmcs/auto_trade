"""
Base API interfaces for the Kite Auto-Trading application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from kite_auto_trading.models.base import Order, Position


class APIClient(ABC):
    """Abstract base class for API clients."""
    
    @abstractmethod
    def authenticate(self, api_key: str, access_token: str) -> bool:
        """Authenticate with the API."""
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        pass
    
    @abstractmethod
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        pass


class TradingAPIClient(APIClient):
    """Abstract interface for trading API operations."""
    
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """Place a trading order."""
        pass
    
    @abstractmethod
    def modify_order(self, order_id: str, modifications: Dict[str, Any]) -> bool:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders for the day."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        pass
    
    @abstractmethod
    def get_funds(self) -> Dict[str, Any]:
        """Get available funds and margins."""
        pass


class MarketDataAPIClient(APIClient):
    """Abstract interface for market data API operations."""
    
    @abstractmethod
    def get_instruments(self) -> List[Dict[str, Any]]:
        """Get list of available instruments."""
        pass
    
    @abstractmethod
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get current quotes for instruments."""
        pass
    
    @abstractmethod
    def get_historical_data(
        self, 
        instrument_token: str, 
        from_date: str, 
        to_date: str, 
        interval: str
    ) -> List[Dict[str, Any]]:
        """Get historical data for an instrument."""
        pass
    
    @abstractmethod
    def start_websocket(self, instruments: List[str]) -> None:
        """Start WebSocket connection for live data."""
        pass
    
    @abstractmethod
    def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        pass