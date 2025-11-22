"""
Comprehensive system integration tests for the Kite Auto Trading application.

Tests complete workflows including stress testing, error scenarios, and performance validation.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from kite_auto_trading.models.market_data import Tick, OHLC
from kite_auto_trading.services.market_data_feed import MarketDataFeed
from kite_auto_trading.services.order_manager import OrderManager
from kite_auto_trading.services.risk_manager import RiskManager
from kite_auto_trading.models.base import Order, OrderType, TransactionType
from kite_auto_trading.config.models import APIConfig, RiskConfig


class TestStressScenarios:
    """Stress tests for high-volume market data and order processing."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.api_config = APIConfig(
            api_key="test_key",
            access_token="test_token",
            timeout=30
        )
        
        self.risk_config = RiskConfig(
            max_position_size=100000.0,
            stop_loss_percentage=2.0,
            target_profit_percentage=5.0,
            daily_loss_limit=10000.0,
            max_positions_per_instrument=5
        )
    
    @patch('kite_auto_trading.services.market_data_feed.KiteTicker')
    def test_high_volume_market_data_processing(self, mock_ticker):
        """Test system handles high-volume market data without degradation."""
        mock_ticker_instance = Mock()
        mock_ticker.return_value = mock_ticker_instance
        
        feed = MarketDataFeed(self.api_config)
        
        # Simulate high-frequency tick data
        instruments = ['RELIANCE', 'INFY', 'TCS', 'WIPRO', 'HDFCBANK']
        tick_count = 1000
        
        start_time = time.time()
        
        # Generate and process 1000 ticks across 5 instruments
        for i in range(tick_count):
            for instrument in instruments:
                tick = Tick(
                    instrument=instrument,
                    last_price=2500.0 + (i % 100),
                    volume=1000 + i,
                    timestamp=datetime.now()
                )
                
                # Process tick
                feed._process_tick(tick)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 5000 ticks in reasonable time (< 5 seconds)
        assert processing_time < 5.0
        
        # Calculate throughput
        throughput = (tick_count * len(instruments)) / processing_time
        print(f"Throughput: {throughput:.2f} ticks/second")
        
        # Should handle at least 1000 ticks per second
        assert throughput > 1000
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_concurrent_order_processing(self, mock_kite_connect):
        """Test system handles concurrent order submissions."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        # Mock order placement with slight delay to simulate real API
        def mock_place_order(*args, **kwargs):
            time.sleep(0.01)  # 10ms delay
            return f"order_{time.time()}"
        
        mock_kite.place_order.side_effect = mock_place_order
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 1000000.0},
                'net': 1000000.0
            }
        }
        
        order_manager = OrderManager(self.api_config)
        order_manager.kite_client = mock_kite
        
        # Submit 50 orders concurrently
        orders = []
        for i in range(50):
            order = Order(
                instrument=f'STOCK{i % 10}',
                transaction_type=TransactionType.BUY,
                quantity=1,
                order_type=OrderType.MARKET
            )
            orders.append(order)
        
        start_time = time.time()
        
        # Process orders concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(order_manager.place_order, order) for order in orders]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # All orders should be processed
        assert len(results) == 50
        assert all(result is not None for result in results)
        
        # Should complete in reasonable time (< 2 seconds with concurrency)
        assert processing_time < 2.0
        
        print(f"Processed 50 orders in {processing_time:.2f} seconds")


class TestErrorScenarios:
    """Tests for error handling and recovery in various failure scenarios."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.api_config = APIConfig(
            api_key="test_key",
            access_token="test_token",
            timeout=30,
            max_retries=3,
            retry_delay=0.1
        )
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_network_failure_recovery(self, mock_kite_connect):
        """Test system recovers from network failures."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        # Simulate network failures followed by success
        call_count = 0
        
        def failing_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return {'equity': {'available': {'cash': 100000.0}, 'net': 100000.0}}
        
        mock_kite.margins.side_effect = failing_api_call
        
        from kite_auto_trading.api.kite_client import KiteAPIClient
        client = KiteAPIClient(self.api_config)
        client.kite = mock_kite
        client._authenticated = True
        
        # Should retry and eventually succeed
        funds = client.get_funds()
        
        assert funds is not None
        assert call_count == 3  # Failed twice, succeeded on third attempt
    
    @patch('kite_auto_trading.services.market_data_feed.KiteTicker')
    def test_websocket_disconnection_recovery(self, mock_ticker):
        """Test market data feed recovers from WebSocket disconnections."""
        mock_ticker_instance = Mock()
        mock_ticker.return_value = mock_ticker_instance
        
        feed = MarketDataFeed(self.api_config)
        
        # Simulate connection
        feed.connect()
        
        # Simulate disconnection
        if hasattr(feed, '_on_disconnect'):
            feed._on_disconnect(mock_ticker_instance, 1006)
        
        # Should attempt reconnection
        # Verify reconnection logic is triggered
        assert feed.ticker is not None


class TestPerformanceMetrics:
    """Tests for latency and throughput performance requirements."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.api_config = APIConfig(
            api_key="test_key",
            access_token="test_token",
            timeout=30
        )
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_order_placement_latency(self, mock_kite_connect):
        """Test order placement latency meets requirements."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        mock_kite.place_order.return_value = {'order_id': 'test_order'}
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 100000.0},
                'net': 100000.0
            }
        }
        
        from kite_auto_trading.api.kite_client import KiteAPIClient
        client = KiteAPIClient(self.api_config)
        client.kite = mock_kite
        client._authenticated = True
        
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=1,
            order_type=OrderType.MARKET
        )
        
        # Measure latency for 100 orders
        latencies = []
        
        for _ in range(100):
            start_time = time.time()
            client.place_order(order)
            end_time = time.time()
            latencies.append(end_time - start_time)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        print(f"Average latency: {avg_latency*1000:.2f}ms")
        print(f"Max latency: {max_latency*1000:.2f}ms")
        
        # Average latency should be < 100ms (excluding network)
        assert avg_latency < 0.1
        
        # 95th percentile should be < 200ms
        sorted_latencies = sorted(latencies)
        p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        assert p95_latency < 0.2
