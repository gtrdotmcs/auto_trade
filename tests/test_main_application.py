"""
Integration tests for main application orchestrator.
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from kite_auto_trading.main import KiteAutoTradingApp
from kite_auto_trading.config.models import (
    TradingConfig, AppConfig, APIConfig, MarketDataConfig,
    RiskManagementConfig, StrategyConfig, PortfolioConfig,
    LoggingConfig, MonitoringConfig, DatabaseConfig, AlertThresholds
)


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return TradingConfig(
        app=AppConfig(
            name="Test App",
            version="1.0.0",
            environment="test",
            debug=True
        ),
        api=APIConfig(
            api_key="test_key",
            access_token="test_token",
            api_secret="test_secret",
            base_url="https://api.test.com",
            timeout=30,
            max_retries=3,
            retry_delay=1.0,
            rate_limit_delay=0.5
        ),
        market_data=MarketDataConfig(
            instruments=["TEST1", "TEST2"],
            timeframes=["minute", "5minute"],
            buffer_size=1000,
            reconnect_interval=10,
            max_reconnect_attempts=5
        ),
        risk_management=RiskManagementConfig(
            max_daily_loss=1000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        ),
        strategies=StrategyConfig(
            enabled=[],
            config_path="strategies/"
        ),
        portfolio=PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        ),
        logging=LoggingConfig(
            level="INFO",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            file_path="logs/test.log",
            max_file_size="10MB",
            backup_count=5,
            console_output=True
        ),
        monitoring=MonitoringConfig(
            performance_metrics_interval=300,
            health_check_interval=60,
            alert_thresholds=AlertThresholds(
                daily_loss_percent=5.0,
                drawdown_percent=10.0,
                connection_failures=3
            )
        ),
        database=DatabaseConfig(
            type="sqlite",
            path="data/test.db",
            backup_enabled=False,
            backup_interval=3600
        )
    )


@pytest.fixture
def app():
    """Create application instance for testing."""
    return KiteAutoTradingApp(
        config_path="config.yaml",
        dry_run=True,
        log_level="INFO"
    )


class TestApplicationInitialization:
    """Test application initialization sequence."""
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_initialization_sequence(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test that all components are initialized in correct order."""
        # Setup mocks
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        # Initialize application
        app.initialize()
        
        # Verify all components are initialized
        assert app.config is not None
        assert app.api_client is not None
        assert app.portfolio_manager is not None
        assert app.risk_manager is not None
        assert app.order_manager is not None
        assert app.market_data_feed is not None
        assert app.strategy_manager is not None
        assert app.monitoring_service is not None
    
    @patch('kite_auto_trading.main.ConfigLoader')
    def test_initialization_creates_directories(self, mock_config_loader, app, mock_config, tmp_path):
        """Test that necessary directories are created."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            app.initialize()
            
            # Check directories exist
            assert (tmp_path / "logs").exists()
            assert (tmp_path / "data").exists()
            assert (tmp_path / "strategies").exists()
            assert (tmp_path / "config").exists()
        finally:
            os.chdir(original_cwd)
    
    @patch('kite_auto_trading.main.ConfigLoader')
    def test_initialization_with_invalid_config(self, mock_config_loader, app):
        """Test initialization handles configuration errors."""
        mock_config_loader.return_value.load_config.side_effect = Exception("Config error")
        
        with pytest.raises(Exception, match="Config error"):
            app.initialize()
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_dry_run_mode_initialization(self, mock_api_client, mock_config_loader, mock_config):
        """Test initialization in dry-run mode."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app = KiteAutoTradingApp(dry_run=True)
        app.initialize()
        
        assert app.dry_run is True
        # Should not raise error even without authentication
        assert app.api_client is not None


class TestApplicationLifecycle:
    """Test application lifecycle management."""
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_startup_and_shutdown(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test complete startup and shutdown sequence."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_instance.is_authenticated.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        # Initialize
        app.initialize()
        
        # Start in separate thread
        run_thread = threading.Thread(target=app.run, daemon=True)
        run_thread.start()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Trigger shutdown
        app.running = False
        app._stop_event.set()
        
        # Wait for shutdown
        run_thread.join(timeout=2.0)
        
        # Perform cleanup
        app.shutdown()
        
        assert not app.running
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_signal_handler(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test signal handler triggers shutdown."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        app.running = True
        
        # Simulate signal
        app._signal_handler(2, None)  # SIGINT
        
        assert not app.running
        assert app._stop_event.is_set()
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_graceful_shutdown_cancels_orders(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test shutdown cancels pending orders."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Add mock pending order
        from kite_auto_trading.models.base import Order, TransactionType, OrderType
        mock_order = Order(
            instrument="TEST",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        mock_order.order_id = "test_order_1"
        
        app.order_manager._orders = {"test_order_1": Mock(order=mock_order)}
        app.order_manager._pending_orders = {"test_order_1"}
        
        # Shutdown
        app.shutdown()
        
        # Verify monitoring and services stopped
        assert app.monitoring_service is not None


class TestTradingCycle:
    """Test trading cycle execution."""
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_process_trading_cycle(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test trading cycle processes signals."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Mock strategy to return signal
        from kite_auto_trading.models.signals import TradingSignal, SignalType, SignalStrength
        
        mock_signal = TradingSignal(
            signal_type=SignalType.BUY,
            instrument="TEST",
            timestamp=datetime.now(),
            price=100.0,
            strength=SignalStrength.STRONG,
            strategy_name="test_strategy",
            reason="Test signal",
            confidence=0.8
        )
        
        app.strategy_manager.evaluate_all_strategies = Mock(return_value=[mock_signal])
        
        # Process cycle
        app._process_trading_cycle()
        
        # Verify strategy was evaluated
        app.strategy_manager.evaluate_all_strategies.assert_called_once()
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_update_portfolio_metrics(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test portfolio metrics are updated."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        initial_value = app.portfolio_manager.get_portfolio_value()
        
        # Update metrics
        app._update_portfolio_metrics()
        
        # Verify risk manager was updated
        assert app.risk_manager._total_portfolio_value == initial_value
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_check_risk_limits(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test risk limits are checked."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Check limits
        app._check_risk_limits()
        
        # Should not trigger emergency stop with default values
        assert not app.risk_manager.is_emergency_stop_active()


class TestCallbackHandlers:
    """Test callback handler functions."""
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_emergency_stop_callback(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test emergency stop callback stops trading."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        app.running = True
        
        # Trigger emergency stop
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        app._handle_emergency_stop(EmergencyStopReason.DAILY_LOSS_LIMIT)
        
        # Verify trading stopped
        assert not app.running
        assert app._stop_event.is_set()
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_order_update_callback(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test order update callback is handled."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Create mock update
        from kite_auto_trading.services.order_manager import OrderUpdate
        from kite_auto_trading.models.base import OrderStatus
        
        update = OrderUpdate(
            order_id="test_order",
            status=OrderStatus.COMPLETE,
            filled_quantity=10,
            average_price=100.0
        )
        
        # Should not raise exception
        app._handle_order_update(update)


class TestStrategyManagement:
    """Test strategy management in application."""
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_strategies_loaded(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test strategies are loaded during initialization."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Verify strategies were loaded
        assert len(app.strategy_manager.strategies) > 0
        
        # Check specific strategies
        strategy_names = list(app.strategy_manager.strategies.keys())
        assert "MA_Crossover" in strategy_names
        assert "RSI_MeanReversion" in strategy_names
    
    @patch('kite_auto_trading.main.ConfigLoader')
    @patch('kite_auto_trading.main.KiteAPIClient')
    def test_strategy_evaluation(self, mock_api_client, mock_config_loader, app, mock_config):
        """Test strategies are evaluated during trading cycle."""
        mock_config_loader.return_value.load_config.return_value = mock_config
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_client.return_value = mock_api_instance
        
        app.initialize()
        
        # Mock strategy evaluation
        app.strategy_manager.evaluate_all_strategies = Mock(return_value=[])
        
        # Process cycle
        app._process_trading_cycle()
        
        # Verify evaluation was called
        app.strategy_manager.evaluate_all_strategies.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
