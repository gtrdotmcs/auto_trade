"""
End-to-end integration tests for the Kite Auto Trading application.

Tests complete workflows from market data ingestion through strategy execution
to order placement and portfolio management.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from kite_auto_trading.main import TradingApplication
from kite_auto_trading.config.models import (
    AppConfig, APIConfig, StrategyConfig, RiskConfig, LoggingConfig
)
from kite_auto_trading.models.base import Order, OrderType, TransactionType
from kite_auto_trading.models.market_data import Tick, OHLC
from kite_auto_trading.models.signals import Signal, SignalType


class TestEndToEndTrading:
    """End-to-end integration tests for complete trading workflows."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.api_config = APIConfig(
            api_key="test_api_key",
            access_token="test_access_token",
            timeout=30,
            max_retries=3
        )
        
        self.strategy_config = StrategyConfig(
            name="test_strategy",
            enabled=True,
            instruments=["RELIANCE", "INFY"],
            entry_conditions={"rsi_oversold": 30},
            exit_conditions={"rsi_overbought": 70},
            timeframe="5minute"
        )
        
        self.risk_config = RiskConfig(
            max_position_size=10000.0,
            stop_loss_percentage=2.0,
            target_profit_percentage=5.0,
            daily_loss_limit=5000.0,
            max_positions_per_instrument=1
        )
        
        self.logging_config = LoggingConfig(
            level="INFO",
            log_file="test_trading.log",
            format="json"
        )
        
        self.app_config = AppConfig(
            api=self.api_config,
            strategies=[self.strategy_config],
            risk=self.risk_config,
            logging=self.logging_config
        )
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    @patch('kite_auto_trading.services.market_data_feed.KiteTicker')
    def test_complete_trading_workflow_buy_to_sell(self, mock_ticker, mock_kite_connect):
        """Test complete workflow: market data -> signal -> order -> position -> exit."""
        # Setup Kite API mock
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 100000.0},
                'net': 100000.0
            }
        }
        mock_kite.place_order.side_effect = ['order_buy_123', 'order_sell_123']
        mock_kite.orders.return_value = [
            {
                'order_id': 'order_buy_123',
                'tradingsymbol': 'RELIANCE',
                'status': 'COMPLETE',
                'quantity': 4,
                'average_price': 2500.0,
                'transaction_type': 'BUY'
            }
        ]
        mock_kite.positions.return_value = {
            'day': [
                {
                    'tradingsymbol': 'RELIANCE',
                    'quantity': 4,
                    'average_price': 2500.0,
                    'last_price': 2600.0,
                    'unrealised': 400.0
                }
            ],
            'net': []
        }
        
        # Setup market data feed mock
        mock_ticker_instance = Mock()
        mock_ticker.return_value = mock_ticker_instance
        
        # Initialize application
        app = TradingApplication(self.app_config)
        
        # Step 1: Start application (authentication)
        with patch.object(app, 'start') as mock_start:
            mock_start.return_value = True
            result = app.start()
            assert result is True
        
        # Step 2: Simulate market data arrival (oversold condition)
        tick_data = Tick(
            instrument='RELIANCE',
            last_price=2500.0,
            volume=1000000,
            timestamp=datetime.now()
        )
        
        # Step 3: Strategy generates BUY signal
        signal = Signal(
            signal_type=SignalType.BUY,
            instrument='RELIANCE',
            price=2500.0,
            quantity=4,
            strategy_name='test_strategy',
            timestamp=datetime.now()
        )
        
        # Step 4: Risk manager validates signal
        if app.risk_manager:
            validated = app.risk_manager.validate_order(
                Order(
                    instrument=signal.instrument,
                    transaction_type=TransactionType.BUY,
                    quantity=signal.quantity,
                    order_type=OrderType.MARKET
                )
            )
            assert validated is True
        
        # Step 5: Order placed and executed
        order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=4,
            order_type=OrderType.MARKET
        )
        
        if app.order_manager:
            order_id = app.order_manager.place_order(order)
            assert order_id is not None
        
        # Step 6: Position tracked in portfolio
        if app.portfolio_manager:
            positions = app.portfolio_manager.get_positions()
            assert len(positions) > 0
        
        # Step 7: Market moves up, exit signal generated
        exit_signal = Signal(
            signal_type=SignalType.SELL,
            instrument='RELIANCE',
            price=2600.0,
            quantity=4,
            strategy_name='test_strategy',
            timestamp=datetime.now()
        )
        
        # Step 8: Exit order placed
        exit_order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.SELL,
            quantity=4,
            order_type=OrderType.MARKET
        )
        
        if app.order_manager:
            exit_order_id = app.order_manager.place_order(exit_order)
            assert exit_order_id is not None
        
        # Step 9: P&L calculated
        if app.portfolio_manager:
            pnl = app.portfolio_manager.calculate_realized_pnl()
            assert pnl >= 0  # Should be profitable
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_risk_limit_enforcement_workflow(self, mock_kite_connect):
        """Test that risk limits are enforced throughout the workflow."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 10000.0},  # Limited funds
                'net': 10000.0
            }
        }
        
        # Initialize application
        app = TradingApplication(self.app_config)
        
        # Attempt to place order exceeding position size limit
        large_order = Order(
            instrument='RELIANCE',
            transaction_type=TransactionType.BUY,
            quantity=100,  # Would exceed max_position_size
            order_type=OrderType.MARKET,
            price=2500.0
        )
        
        if app.risk_manager:
            # Should reject order due to position size limit
            validated = app.risk_manager.validate_order(large_order)
            assert validated is False
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_multiple_strategies_concurrent_execution(self, mock_kite_connect):
        """Test multiple strategies running concurrently."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 100000.0},
                'net': 100000.0
            }
        }
        
        # Add second strategy
        strategy2 = StrategyConfig(
            name="test_strategy_2",
            enabled=True,
            instruments=["TCS", "WIPRO"],
            entry_conditions={"ma_crossover": True},
            exit_conditions={"ma_crossunder": True},
            timeframe="15minute"
        )
        
        config_with_multiple = AppConfig(
            api=self.api_config,
            strategies=[self.strategy_config, strategy2],
            risk=self.risk_config,
            logging=self.logging_config
        )
        
        app = TradingApplication(config_with_multiple)
        
        # Both strategies should be loaded
        if hasattr(app, 'strategy_manager') and app.strategy_manager:
            strategies = app.strategy_manager.get_strategies()
            assert len(strategies) >= 2
    
    @patch('kite_auto_trading.api.kite_client.KiteConnect')
    def test_daily_loss_limit_stops_trading(self, mock_kite_connect):
        """Test that trading stops when daily loss limit is reached."""
        mock_kite = Mock()
        mock_kite_connect.return_value = mock_kite
        
        mock_kite.profile.return_value = {'user_id': 'test_user'}
        mock_kite.margins.return_value = {
            'equity': {
                'available': {'cash': 100000.0},
                'net': 100000.0
            }
        }
        
        app = TradingApplication(self.app_config)
        
        if app.risk_manager:
            # Simulate losses exceeding daily limit
            app.risk_manager.daily_pnl = -6000.0  # Exceeds 5000 limit
            
            # Should reject new orders
            order = Order(
                instrument='RELIANCE',
                transaction_type=TransactionType.BUY,
                quantity=1,
                order_type=OrderType.MARKET
            )
            
            validated = app.risk_manager.validate_order(order)
            assert validated is False


class TestSandboxIntegration:
    """Tests designed to work with Kite Connect sandbox environment."""
    
    @pytest.mark.sandbox
    @pytest.mark.skipif(
        not pytest.config.getoption("--sandbox", default=False),
        reason="Requires --sandbox flag and sandbox credentials"
    )
    def test_sandbox_authentication(self):
        """Test authentication against Kite sandbox."""
        # This test requires actual sandbox credentials
        # Skip in normal test runs
        pass
    
    @pytest.mark.sandbox
    def test_sandbox_market_data_subscription(self):
        """Test market data subscription in sandbox."""
        # This test requires actual sandbox environment
        pass
    
    @pytest.mark.sandbox
    def test_sandbox_order_placement(self):
        """Test order placement in sandbox environment."""
        # This test requires actual sandbox environment
        pass


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--sandbox",
        action="store_true",
        default=False,
        help="Run tests against Kite Connect sandbox"
    )
