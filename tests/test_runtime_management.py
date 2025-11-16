"""
Tests for configuration hot-reloading and runtime management.
"""

import pytest
import time
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from kite_auto_trading.main import KiteAutoTradingApp
from kite_auto_trading.config.models import (
    TradingConfig, AppConfig, APIConfig, MarketDataConfig,
    RiskManagementConfig, StrategyConfig, PortfolioConfig,
    LoggingConfig, MonitoringConfig, DatabaseConfig, AlertThresholds
)


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file."""
    config_data = {
        'app': {'name': 'Test App', 'version': '1.0.0', 'environment': 'test', 'debug': True},
        'api': {
            'api_key': 'test_key',
            'access_token': 'test_token',
            'api_secret': 'test_secret',
            'base_url': 'https://api.test.com',
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 1.0,
            'rate_limit_delay': 0.5
        },
        'market_data': {
            'instruments': ['TEST1', 'TEST2'],
            'timeframes': ['minute', '5minute'],
            'buffer_size': 1000,
            'reconnect_interval': 10,
            'max_reconnect_attempts': 5
        },
        'risk_management': {
            'max_daily_loss': 1000.0,
            'max_position_size_percent': 2.0,
            'max_positions_per_instrument': 1,
            'stop_loss_percent': 2.0,
            'target_profit_percent': 4.0,
            'emergency_stop_enabled': True
        },
        'strategies': {
            'enabled': [],
            'config_path': 'strategies/'
        },
        'portfolio': {
            'initial_capital': 100000.0,
            'currency': 'INR',
            'brokerage_per_trade': 20.0,
            'tax_rate': 0.15
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file_path': 'logs/test.log',
            'max_file_size': '10MB',
            'backup_count': 5,
            'console_output': True
        },
        'monitoring': {
            'performance_metrics_interval': 300,
            'health_check_interval': 60,
            'alert_thresholds': {
                'daily_loss_percent': 5.0,
                'drawdown_percent': 10.0,
                'connection_failures': 3
            }
        },
        'database': {
            'type': 'sqlite',
            'path': 'data/test.db',
            'backup_enabled': False,
            'backup_interval': 3600
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def initialized_app(temp_config_file):
    """Create and initialize an application instance."""
    with patch('kite_auto_trading.main.KiteAPIClient') as mock_api:
        mock_api_instance = Mock()
        mock_api_instance.auto_authenticate.return_value = False
        mock_api_instance.is_authenticated.return_value = False
        mock_api.return_value = mock_api_instance
        
        app = KiteAutoTradingApp(
            config_path=temp_config_file,
            dry_run=True,
            log_level="INFO"
        )
        app.initialize()
        
        yield app
        
        # Cleanup
        if app._config_watch_enabled:
            app.disable_config_hot_reload()


class TestConfigurationHotReload:
    """Test configuration hot-reloading functionality."""
    
    def test_enable_config_hot_reload(self, initialized_app):
        """Test enabling configuration hot-reload."""
        app = initialized_app
        
        app.enable_config_hot_reload()
        
        assert app._config_watch_enabled is True
        assert app._config_watch_thread is not None
        assert app._config_watch_thread.is_alive()
    
    def test_disable_config_hot_reload(self, initialized_app):
        """Test disabling configuration hot-reload."""
        app = initialized_app
        
        app.enable_config_hot_reload()
        time.sleep(0.5)  # Let thread start
        
        app.disable_config_hot_reload()
        
        assert app._config_watch_enabled is False
    
    def test_config_file_change_detection(self, initialized_app, temp_config_file):
        """Test configuration file change detection."""
        app = initialized_app
        
        # Enable hot-reload
        app.enable_config_hot_reload()
        time.sleep(0.5)
        
        # Modify config file
        config_path = Path(temp_config_file)
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config_data['risk_management']['max_daily_loss'] = 2000.0
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Wait for change detection
        time.sleep(6)  # Config watcher checks every 5 seconds
        
        # Verify config was reloaded
        assert app.config.risk_management.max_daily_loss == 2000.0
    
    def test_reload_configuration_manually(self, initialized_app):
        """Test manual configuration reload."""
        app = initialized_app
        
        original_loss_limit = app.config.risk_management.max_daily_loss
        
        # Modify config in memory
        app.config.risk_management.max_daily_loss = 5000.0
        
        # Reload from file
        app._reload_configuration()
        
        # Should be back to original value from file
        assert app.config.risk_management.max_daily_loss == original_loss_limit


class TestRuntimeStrategyManagement:
    """Test runtime strategy management functionality."""
    
    def test_enable_strategy(self, initialized_app):
        """Test enabling a strategy at runtime."""
        app = initialized_app
        
        # Get a strategy name
        strategies = app.list_strategies()
        assert len(strategies) > 0
        
        strategy_name = strategies[0]
        
        # Disable it first
        app.disable_strategy(strategy_name)
        
        # Enable it
        success = app.enable_strategy(strategy_name)
        
        assert success is True
        assert app.strategy_manager.is_strategy_enabled(strategy_name)
    
    def test_disable_strategy(self, initialized_app):
        """Test disabling a strategy at runtime."""
        app = initialized_app
        
        # Get a strategy name
        strategies = app.list_strategies()
        assert len(strategies) > 0
        
        strategy_name = strategies[0]
        
        # Ensure it's enabled first
        app.enable_strategy(strategy_name)
        
        # Disable it
        success = app.disable_strategy(strategy_name)
        
        assert success is True
        assert not app.strategy_manager.is_strategy_enabled(strategy_name)
    
    def test_get_strategy_status(self, initialized_app):
        """Test getting strategy status."""
        app = initialized_app
        
        status = app.get_strategy_status()
        
        assert isinstance(status, dict)
        assert len(status) > 0
        
        # Check status structure
        for strategy_name, stats in status.items():
            assert 'evaluations' in stats
            assert 'errors' in stats
            assert 'enabled' in stats
    
    def test_list_strategies(self, initialized_app):
        """Test listing all strategies."""
        app = initialized_app
        
        strategies = app.list_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        assert "MA_Crossover" in strategies
        assert "RSI_MeanReversion" in strategies


class TestAdministrativeInterface:
    """Test administrative interface functionality."""
    
    def test_get_application_status(self, initialized_app):
        """Test getting application status."""
        app = initialized_app
        
        status = app.get_application_status()
        
        assert isinstance(status, dict)
        assert 'running' in status
        assert 'dry_run' in status
        assert 'components' in status
        assert 'strategies' in status
        assert 'portfolio' in status
        assert 'risk' in status
        
        # Check components
        components = status['components']
        assert components['api_client'] is True
        assert components['portfolio_manager'] is True
        assert components['risk_manager'] is True
        assert components['order_manager'] is True
        assert components['strategy_manager'] is True
    
    def test_get_performance_report(self, initialized_app):
        """Test getting performance report."""
        app = initialized_app
        
        report = app.get_performance_report()
        
        assert isinstance(report, dict)
        # Report structure depends on monitoring service implementation
    
    def test_trigger_emergency_stop(self, initialized_app):
        """Test manually triggering emergency stop."""
        app = initialized_app
        app.running = True
        
        app.trigger_emergency_stop("Test emergency stop")
        
        assert app.risk_manager.is_emergency_stop_active()
        assert not app.running
    
    def test_clear_emergency_stop(self, initialized_app):
        """Test clearing emergency stop."""
        app = initialized_app
        
        # Trigger emergency stop first
        app.trigger_emergency_stop("Test")
        assert app.risk_manager.is_emergency_stop_active()
        
        # Clear it
        success = app.clear_emergency_stop()
        
        assert success is True
        assert not app.risk_manager.is_emergency_stop_active()
        assert app.running is True


class TestConfigurationChanges:
    """Test applying configuration changes."""
    
    def test_apply_risk_config_changes(self, initialized_app):
        """Test applying risk management configuration changes."""
        app = initialized_app
        
        old_config = app.config
        new_config = app.config_loader.load_config()
        new_config.risk_management.max_daily_loss = 5000.0
        
        app._apply_config_changes(old_config, new_config)
        
        assert app.risk_manager.risk_config.max_daily_loss == 5000.0
    
    def test_apply_monitoring_config_changes(self, initialized_app):
        """Test applying monitoring configuration changes."""
        app = initialized_app
        
        old_config = app.config
        new_config = app.config_loader.load_config()
        new_config.monitoring.alert_thresholds.drawdown_percent = 15.0
        
        app._apply_config_changes(old_config, new_config)
        
        assert app.monitoring_service.alert_thresholds['max_drawdown_pct'] == 15.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
