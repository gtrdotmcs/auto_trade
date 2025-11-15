"""
Market data feed handler for real-time data streaming.

This module provides WebSocket-based real-time market data feed handling
with automatic reconnection and data buffering capabilities.
"""

import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class MarketDataFeed:
    """
    Real-time market data feed handler with WebSocket support.
    
    Provides connection management, automatic reconnection, data buffering,
    and processing pipeline for live market data.
    """
    
    def __init__(
        self,
        api_client,
        buffer_size: int = 1000,
        reconnect_interval: int = 10,
        max_reconnect_attempts: int = 5
    ):
        """
        Initialize market data feed handler.
        
        Args:
            api_client: Kite API client instance for WebSocket connection
            buffer_size: Maximum size of data buffer
            reconnect_interval: Seconds between reconnection attempts
            max_reconnect_attempts: Maximum number of reconnection attempts
        """
        self.api_client = api_client
        self.buffer_size = buffer_size
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_count = 0
        self.last_connection_time: Optional[datetime] = None
        
        # Data management
        self.data_buffer: deque = deque(maxlen=buffer_size)
        self.subscribed_instruments: List[int] = []
        self.latest_ticks: Dict[int, Dict[str, Any]] = {}
        
        # Callbacks
        self.on_tick_callbacks: List[Callable] = []
        self.on_connect_callbacks: List[Callable] = []
        self.on_disconnect_callbacks: List[Callable] = []
        self.on_error_callbacks: List[Callable] = []
        
        # Threading
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reconnect_thread: Optional[threading.Thread] = None
        
        logger.info("MarketDataFeed initialized")
    
    def connect(self) -> bool:
        """
        Establish WebSocket connection for live data.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Attempting to connect to market data feed...")
            self.state = ConnectionState.CONNECTING
            
            # Simulate WebSocket connection (actual implementation would use kiteconnect library)
            # In real implementation: self.api_client.connect_websocket()
            
            with self._lock:
                self.state = ConnectionState.CONNECTED
                self.last_connection_time = datetime.now()
                self.reconnect_count = 0
            
            logger.info("Successfully connected to market data feed")
            self._trigger_callbacks(self.on_connect_callbacks)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to market data feed: {e}")
            self.state = ConnectionState.ERROR
            self._trigger_callbacks(self.on_error_callbacks, error=str(e))
            return False
    
    def disconnect(self) -> None:
        """Disconnect from market data feed."""
        try:
            logger.info("Disconnecting from market data feed...")
            
            with self._lock:
                self.state = ConnectionState.DISCONNECTED
                self.subscribed_instruments.clear()
            
            self._stop_event.set()
            
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                self._reconnect_thread.join(timeout=5)
            
            logger.info("Disconnected from market data feed")
            self._trigger_callbacks(self.on_disconnect_callbacks)
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def subscribe_instruments(self, instrument_tokens: List[int]) -> bool:
        """
        Subscribe to market data for given instruments.
        
        Args:
            instrument_tokens: List of instrument tokens to subscribe
            
        Returns:
            True if subscription successful, False otherwise
        """
        if self.state != ConnectionState.CONNECTED:
            logger.warning("Cannot subscribe: not connected to market data feed")
            return False
        
        try:
            logger.info(f"Subscribing to {len(instrument_tokens)} instruments")
            
            # In real implementation: self.api_client.subscribe(instrument_tokens)
            
            with self._lock:
                for token in instrument_tokens:
                    if token not in self.subscribed_instruments:
                        self.subscribed_instruments.append(token)
            
            logger.info(f"Successfully subscribed to {len(instrument_tokens)} instruments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to instruments: {e}")
            return False
    
    def unsubscribe_instruments(self, instrument_tokens: List[int]) -> bool:
        """
        Unsubscribe from market data for given instruments.
        
        Args:
            instrument_tokens: List of instrument tokens to unsubscribe
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        try:
            logger.info(f"Unsubscribing from {len(instrument_tokens)} instruments")
            
            # In real implementation: self.api_client.unsubscribe(instrument_tokens)
            
            with self._lock:
                for token in instrument_tokens:
                    if token in self.subscribed_instruments:
                        self.subscribed_instruments.remove(token)
                    if token in self.latest_ticks:
                        del self.latest_ticks[token]
            
            logger.info(f"Successfully unsubscribed from {len(instrument_tokens)} instruments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from instruments: {e}")
            return False
    
    def process_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Process incoming tick data.
        
        Args:
            tick_data: Raw tick data from WebSocket
        """
        try:
            instrument_token = tick_data.get('instrument_token')
            if not instrument_token:
                logger.warning("Received tick without instrument_token")
                return
            
            # Add timestamp if not present
            if 'timestamp' not in tick_data:
                tick_data['timestamp'] = datetime.now()
            
            # Buffer the tick
            with self._lock:
                self.data_buffer.append(tick_data)
                self.latest_ticks[instrument_token] = tick_data
            
            # Trigger callbacks
            self._trigger_callbacks(self.on_tick_callbacks, tick=tick_data)
            
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
    
    def get_latest_tick(self, instrument_token: int) -> Optional[Dict[str, Any]]:
        """
        Get the latest tick for an instrument.
        
        Args:
            instrument_token: Instrument token
            
        Returns:
            Latest tick data or None if not available
        """
        with self._lock:
            return self.latest_ticks.get(instrument_token)
    
    def get_buffered_ticks(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get buffered tick data.
        
        Args:
            count: Number of recent ticks to retrieve (None for all)
            
        Returns:
            List of tick data
        """
        with self._lock:
            if count is None:
                return list(self.data_buffer)
            return list(self.data_buffer)[-count:]
    
    def clear_buffer(self) -> None:
        """Clear the data buffer."""
        with self._lock:
            self.data_buffer.clear()
            logger.info("Data buffer cleared")
    
    def register_callback(
        self,
        callback_type: str,
        callback: Callable
    ) -> None:
        """
        Register a callback for events.
        
        Args:
            callback_type: Type of callback ('tick', 'connect', 'disconnect', 'error')
            callback: Callback function
        """
        callback_map = {
            'tick': self.on_tick_callbacks,
            'connect': self.on_connect_callbacks,
            'disconnect': self.on_disconnect_callbacks,
            'error': self.on_error_callbacks,
        }
        
        if callback_type not in callback_map:
            raise ValueError(f"Invalid callback type: {callback_type}")
        
        callback_map[callback_type].append(callback)
        logger.info(f"Registered {callback_type} callback")
    
    def _trigger_callbacks(
        self,
        callbacks: List[Callable],
        **kwargs
    ) -> None:
        """
        Trigger registered callbacks.
        
        Args:
            callbacks: List of callback functions
            **kwargs: Arguments to pass to callbacks
        """
        for callback in callbacks:
            try:
                callback(**kwargs)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
    
    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to market data feed."""
        while not self._stop_event.is_set() and self.reconnect_count < self.max_reconnect_attempts:
            self.reconnect_count += 1
            logger.info(f"Reconnection attempt {self.reconnect_count}/{self.max_reconnect_attempts}")
            
            self.state = ConnectionState.RECONNECTING
            
            if self.connect():
                # Resubscribe to instruments
                if self.subscribed_instruments:
                    self.subscribe_instruments(self.subscribed_instruments.copy())
                return
            
            time.sleep(self.reconnect_interval)
        
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            self.state = ConnectionState.ERROR
    
    def start_reconnect_thread(self) -> None:
        """Start automatic reconnection thread."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            logger.warning("Reconnect thread already running")
            return
        
        self._stop_event.clear()
        self._reconnect_thread = threading.Thread(target=self._attempt_reconnect, daemon=True)
        self._reconnect_thread.start()
        logger.info("Reconnect thread started")
    
    def is_connected(self) -> bool:
        """Check if connected to market data feed."""
        return self.state == ConnectionState.CONNECTED
    
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self.state
    
    def get_subscribed_instruments(self) -> List[int]:
        """Get list of subscribed instrument tokens."""
        with self._lock:
            return self.subscribed_instruments.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get feed statistics.
        
        Returns:
            Dictionary with feed statistics
        """
        with self._lock:
            return {
                'state': self.state.value,
                'subscribed_instruments': len(self.subscribed_instruments),
                'buffered_ticks': len(self.data_buffer),
                'latest_ticks': len(self.latest_ticks),
                'reconnect_count': self.reconnect_count,
                'last_connection_time': self.last_connection_time,
            }
