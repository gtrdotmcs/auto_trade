"""
Unit tests for configuration management system.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from kite_auto_trading.config import (
    TradingConfig, AppConfig, APIConfig, ConfigLoader, ConfigManager,
    ConfigurationError, Environment, LogLevel, load_config
)


class TestConfigModels(unittest.TestCase):
    """Test configuration data models."""
    
    def test_trading_config_defaults(self):
        """Test TradingConfig with default values."""
        config = TradingConfig()
        
        self.assertEqual(config.app.name, "Kite Auto Trading")
        self.assertEqual(config.app.version, "1.0.0")
        self.assertEqual(config.app.environment, Environment.DEVELOPMENT)
        self.assertTrue(config.app.debug)
        
        self.assertEqual(config.api.base_url, "https://api.kite.trade")
        self.assertEqual(config.api.timeout, 30)
        self.assertEqual(config.api.max_retries, 3)
        
        self.assertEqual(config.risk_management.max_daily_loss, 10000.0)
        self.assertEqual(config.risk_management.max_position_size_percent, 2.0)
        
    def test_config_validation_valid(self):
        """Test configuration validation with valid config."""
        config = TradingConfig()
        errors = config.validate()
        self.assertEqual(len(errors), 0)
        self.assertTrue(config.is_valid())
    
    def test_config_validation_invalid_api(self):
        """Test configuration validation with invalid API config."""
        config = TradingConfig()
        config.api.base_url = ""
        config.api.timeout = -1
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertFalse(config.is_valid())
        self.assertIn("API base_url is required", errors)
        self.assertIn("API timeout must be positive", errors)
    
    def test_config_validation_invalid_risk(self):
        """Test configuration validation with invalid risk management."""
        config = TradingConfig()
        config.risk_management.max_daily_loss = -1000
        config.risk_management.max_position_size_percent = 150
        config.risk_management.stop_loss_percent = -1
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertIn("Risk management max_daily_loss must be positive", errors)
        self.assertIn("Risk management max_position_size_percent must be between 0 and 100", errors)
        self.assertIn("Risk management stop_loss_percent must be positive", errors)
    
    def test_config_validation_invalid_portfolio(self):
        """Test configuration validation with invalid portfolio config."""
        config = TradingConfig()
        config.portfolio.initial_capital = -50000
        config.portfolio.tax_rate = 1.5
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertIn("Portfolio initial_capital must be positive", errors)
        self.assertIn("Portfolio tax_rate must be between 0 and 1", errors)


class TestConfigLoader(unittest.TestCase):
    """Test configuration loader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
        self.env_config_path = os.path.join(self.temp_dir, "test_config.testing.yaml")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_no_file(self):
        """Test loading config when no file exists."""
        loader = ConfigLoader(self.config_path, "testing")
        config = loader.load_config()
        
        # Should return default configuration
        self.assertIsInstance(config, TradingConfig)
        self.assertEqual(config.app.name, "Kite Auto Trading")
    
    def test_load_config_yaml_file(self):
        """Test loading config from YAML file."""
        config_data = {
            'app': {
                'name': 'Test Trading App',
                'version': '2.0.0',
                'environment': 'testing'
            },
            'api': {
                'timeout': 60,
                'max_retries': 5
            },
            'risk_management': {
                'max_daily_loss': 5000.0,
                'stop_loss_percent': 1.5
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(self.config_path, "testing")
        config = loader.load_config()
        
        self.assertEqual(config.app.name, "Test Trading App")
        self.assertEqual(config.app.version, "2.0.0")
        self.assertEqual(config.app.environment, Environment.TESTING)
        self.assertEqual(config.api.timeout, 60)
        self.assertEqual(config.api.max_retries, 5)
        self.assertEqual(config.risk_management.max_daily_loss, 5000.0)
        self.assertEqual(config.risk_management.stop_loss_percent, 1.5)
    
    def test_load_config_json_file(self):
        """Test loading config from JSON file."""
        json_config_path = os.path.join(self.temp_dir, "test_config.json")
        config_data = {
            'app': {
                'name': 'JSON Test App',
                'environment': 'production'
            },
            'api': {
                'timeout': 45
            }
        }
        
        with open(json_config_path, 'w') as f:
            json.dump(config_data, f)
        
        loader = ConfigLoader(json_config_path, "production")
        config = loader.load_config()
        
        self.assertEqual(config.app.name, "JSON Test App")
        self.assertEqual(config.app.environment, Environment.PRODUCTION)
        self.assertEqual(config.api.timeout, 45)
    
    def test_environment_specific_config(self):
        """Test environment-specific configuration overrides."""
        # Base config
        base_config = {
            'app': {'name': 'Base App'},
            'api': {'timeout': 30, 'max_retries': 3}
        }
        
        # Environment-specific config
        env_config = {
            'app': {'name': 'Testing App'},
            'api': {'timeout': 60}
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(base_config, f)
        
        with open(self.env_config_path, 'w') as f:
            yaml.dump(env_config, f)
        
        loader = ConfigLoader(self.config_path, "testing")
        config = loader.load_config()
        
        # Environment config should override base config
        self.assertEqual(config.app.name, "Testing App")
        self.assertEqual(config.api.timeout, 60)
        self.assertEqual(config.api.max_retries, 3)  # Should keep base value
    
    @patch.dict(os.environ, {
        'KITE_API_KEY': 'test_api_key',
        'KITE_ACCESS_TOKEN': 'test_token',
        'LOG_LEVEL': 'DEBUG',
        'MAX_DAILY_LOSS': '15000'
    })
    def test_environment_variable_overrides(self):
        """Test environment variable overrides."""
        loader = ConfigLoader(self.config_path, "testing")
        config = loader.load_config()
        
        self.assertEqual(config.api.api_key, "test_api_key")
        self.assertEqual(config.api.access_token, "test_token")
        self.assertEqual(config.logging.level, LogLevel.DEBUG)
        self.assertEqual(config.risk_management.max_daily_loss, 15000.0)
    
    def test_invalid_yaml_file(self):
        """Test handling of invalid YAML file."""
        with open(self.config_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        loader = ConfigLoader(self.config_path, "testing")
        
        with self.assertRaises(ConfigurationError):
            loader.load_config()
    
    def test_config_validation_failure(self):
        """Test configuration validation failure."""
        config_data = {
            'api': {'timeout': -1},  # Invalid timeout
            'risk_management': {'max_daily_loss': -1000}  # Invalid loss limit
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(self.config_path, "testing")
        
        with self.assertRaises(ConfigurationError) as cm:
            loader.load_config()
        
        self.assertIn("Configuration validation failed", str(cm.exception))
    
    def test_save_config_yaml(self):
        """Test saving configuration to YAML file."""
        config = TradingConfig()
        config.app.name = "Saved Test App"
        config.api.timeout = 120
        
        save_path = os.path.join(self.temp_dir, "saved_config.yaml")
        loader = ConfigLoader()
        loader.save_config(config, save_path)
        
        # Load and verify saved config
        with open(save_path, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        self.assertEqual(saved_data['app']['name'], "Saved Test App")
        self.assertEqual(saved_data['api']['timeout'], 120)
    
    def test_save_config_json(self):
        """Test saving configuration to JSON file."""
        config = TradingConfig()
        config.app.name = "JSON Saved App"
        
        save_path = os.path.join(self.temp_dir, "saved_config.json")
        loader = ConfigLoader()
        loader.save_config(config, save_path)
        
        # Load and verify saved config
        with open(save_path, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data['app']['name'], "JSON Saved App")
    
    def test_config_caching(self):
        """Test configuration caching."""
        config_data = {'app': {'name': 'Cached App'}}
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(self.config_path, "testing")
        
        # First load
        config1 = loader.load_config()
        
        # Modify file
        config_data['app']['name'] = 'Modified App'
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Second load without reload should return cached config
        config2 = loader.load_config()
        self.assertEqual(config1.app.name, config2.app.name)
        self.assertEqual(config2.app.name, "Cached App")
        
        # Reload should get new config
        config3 = loader.load_config(reload=True)
        self.assertEqual(config3.app.name, "Modified App")


class TestConfigManager(unittest.TestCase):
    """Test configuration manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "manager_test.yaml")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_manager_basic(self):
        """Test basic configuration manager functionality."""
        config_data = {'app': {'name': 'Manager Test'}}
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(self.config_path, "testing")
        config = manager.get_config()
        
        self.assertEqual(config.app.name, "Manager Test")
    
    def test_config_manager_reload(self):
        """Test configuration manager reload functionality."""
        config_data = {'app': {'name': 'Original'}}
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(self.config_path, "testing")
        config1 = manager.get_config()
        self.assertEqual(config1.app.name, "Original")
        
        # Modify config file
        config_data['app']['name'] = 'Reloaded'
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Reload
        config2 = manager.reload_config()
        self.assertEqual(config2.app.name, "Reloaded")
    
    def test_config_manager_update(self):
        """Test configuration manager update functionality."""
        manager = ConfigManager(self.config_path, "testing")
        
        # Update configuration
        updated_config = manager.update_config(**{
            'app.name': 'Updated App',
            'api.timeout': 90
        })
        
        self.assertEqual(updated_config.app.name, "Updated App")
        self.assertEqual(updated_config.api.timeout, 90)
    
    def test_config_manager_change_callbacks(self):
        """Test configuration change callbacks."""
        manager = ConfigManager(self.config_path, "testing")
        
        callback_called = []
        
        def config_changed(config):
            callback_called.append(config.app.name)
        
        manager.add_change_callback(config_changed)
        
        # Update config should trigger callback
        manager.update_config(**{'app.name': 'Callback Test'})
        
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0], "Callback Test")
        
        # Remove callback
        manager.remove_change_callback(config_changed)
        manager.update_config(**{'app.name': 'No Callback'})
        
        # Should still be 1 (callback not called again)
        self.assertEqual(len(callback_called), 1)
    
    def test_config_manager_context_manager(self):
        """Test configuration manager as context manager."""
        with ConfigManager(self.config_path, "testing") as manager:
            config = manager.get_config()
            self.assertIsInstance(config, TradingConfig)


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for configuration system."""
    
    def test_load_config_function(self):
        """Test load_config convenience function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'app': {'name': 'Function Test'}}, f)
            config_path = f.name
        
        try:
            config = load_config(config_path, "testing")
            self.assertEqual(config.app.name, "Function Test")
        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()