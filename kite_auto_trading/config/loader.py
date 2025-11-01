"""
Configuration loader for Kite Auto Trading application.
"""

import json
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import asdict
from enum import Enum

from .models import (
    TradingConfig, AppConfig, APIConfig, MarketDataConfig, RiskManagementConfig,
    StrategyConfig, PortfolioConfig, LoggingConfig, MonitoringConfig, DatabaseConfig,
    AlertThresholds, Environment, LogLevel
)
from .constants import DEFAULT_CONFIG_PATH


class ConfigurationError(Exception):
    """Configuration related errors."""
    pass


class ConfigLoader:
    """Configuration loader with support for YAML, JSON and environment variables."""
    
    def __init__(self, config_path: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to configuration file
            environment: Environment name for environment-specific configs
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self._config_cache: Optional[TradingConfig] = None
    
    def load_config(self, reload: bool = False) -> TradingConfig:
        """
        Load configuration from file and environment variables.
        
        Args:
            reload: Force reload configuration from file
            
        Returns:
            TradingConfig instance
            
        Raises:
            ConfigurationError: If configuration loading fails
        """
        if self._config_cache is not None and not reload:
            return self._config_cache
        
        try:
            # Load base configuration from file
            config_data = self._load_config_file()
            
            # Apply environment-specific overrides
            config_data = self._apply_environment_overrides(config_data)
            
            # Apply environment variable overrides
            config_data = self._apply_env_var_overrides(config_data)
            
            # Create configuration object
            config = self._create_config_object(config_data)
            
            # Validate configuration
            validation_errors = config.validate()
            if validation_errors:
                raise ConfigurationError(f"Configuration validation failed: {', '.join(validation_errors)}")
            
            self._config_cache = config
            return config
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    
    def save_config(self, config: TradingConfig, file_path: Optional[str] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            file_path: Optional file path, defaults to current config_path
        """
        save_path = file_path or self.config_path
        config_dict = self._config_to_dict(config)
        
        try:
            if save_path.endswith('.json'):
                self._save_json(config_dict, save_path)
            else:
                self._save_yaml(config_dict, save_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {str(e)}")
    
    def reload_config(self) -> TradingConfig:
        """
        Reload configuration from file.
        
        Returns:
            Reloaded TradingConfig instance
        """
        return self.load_config(reload=True)
    
    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not Path(self.config_path).exists():
            # Return default configuration if file doesn't exist
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.endswith('.json'):
                    return json.load(f)
                else:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to parse configuration file {self.config_path}: {str(e)}")
    
    def _apply_environment_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment-specific configuration overrides."""
        env_config_path = self._get_environment_config_path()
        
        if Path(env_config_path).exists():
            try:
                with open(env_config_path, 'r', encoding='utf-8') as f:
                    if env_config_path.endswith('.json'):
                        env_config = json.load(f)
                    else:
                        env_config = yaml.safe_load(f) or {}
                
                # Deep merge environment config
                config_data = self._deep_merge(config_data, env_config)
            except Exception as e:
                raise ConfigurationError(f"Failed to load environment config {env_config_path}: {str(e)}")
        
        return config_data
    
    def _apply_env_var_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        # API configuration from environment variables
        api_config = config_data.setdefault('api', {})
        api_config['api_key'] = os.getenv('KITE_API_KEY', api_config.get('api_key'))
        api_config['access_token'] = os.getenv('KITE_ACCESS_TOKEN', api_config.get('access_token'))
        api_config['api_secret'] = os.getenv('KITE_API_SECRET', api_config.get('api_secret'))
        
        # App configuration
        app_config = config_data.setdefault('app', {})
        if os.getenv('ENVIRONMENT'):
            app_config['environment'] = os.getenv('ENVIRONMENT')
        
        # Logging configuration
        logging_config = config_data.setdefault('logging', {})
        if os.getenv('LOG_LEVEL'):
            logging_config['level'] = os.getenv('LOG_LEVEL')
        
        # Risk management
        risk_config = config_data.setdefault('risk_management', {})
        if os.getenv('MAX_DAILY_LOSS'):
            risk_config['max_daily_loss'] = float(os.getenv('MAX_DAILY_LOSS'))
        if os.getenv('DEFAULT_POSITION_SIZE_PERCENT'):
            risk_config['max_position_size_percent'] = float(os.getenv('DEFAULT_POSITION_SIZE_PERCENT'))
        
        # Market data configuration
        market_data_config = config_data.setdefault('market_data', {})
        if os.getenv('MARKET_DATA_TIMEOUT'):
            market_data_config['timeout'] = int(os.getenv('MARKET_DATA_TIMEOUT'))
        if os.getenv('RECONNECT_INTERVAL'):
            market_data_config['reconnect_interval'] = int(os.getenv('RECONNECT_INTERVAL'))
        
        return config_data
    
    def _create_config_object(self, config_data: Dict[str, Any]) -> TradingConfig:
        """Create TradingConfig object from configuration data."""
        # Create sub-configuration objects
        app_config = AppConfig(**self._extract_config_section(config_data, 'app', AppConfig))
        api_config = APIConfig(**self._extract_config_section(config_data, 'api', APIConfig))
        market_data_config = MarketDataConfig(**self._extract_config_section(config_data, 'market_data', MarketDataConfig))
        risk_config = RiskManagementConfig(**self._extract_config_section(config_data, 'risk_management', RiskManagementConfig))
        strategy_config = StrategyConfig(**self._extract_config_section(config_data, 'strategies', StrategyConfig))
        portfolio_config = PortfolioConfig(**self._extract_config_section(config_data, 'portfolio', PortfolioConfig))
        logging_config = LoggingConfig(**self._extract_config_section(config_data, 'logging', LoggingConfig))
        database_config = DatabaseConfig(**self._extract_config_section(config_data, 'database', DatabaseConfig))
        
        # Handle monitoring config with nested alert thresholds
        monitoring_data = config_data.get('monitoring', {})
        alert_thresholds_data = monitoring_data.pop('alert_thresholds', {})
        alert_thresholds = AlertThresholds(**self._filter_dataclass_fields(alert_thresholds_data, AlertThresholds))
        monitoring_config = MonitoringConfig(
            alert_thresholds=alert_thresholds,
            **self._filter_dataclass_fields(monitoring_data, MonitoringConfig)
        )
        
        return TradingConfig(
            app=app_config,
            api=api_config,
            market_data=market_data_config,
            risk_management=risk_config,
            strategies=strategy_config,
            portfolio=portfolio_config,
            logging=logging_config,
            monitoring=monitoring_config,
            database=database_config
        )
    
    def _extract_config_section(self, config_data: Dict[str, Any], section: str, dataclass_type) -> Dict[str, Any]:
        """Extract and filter configuration section for dataclass."""
        section_data = config_data.get(section, {})
        return self._filter_dataclass_fields(section_data, dataclass_type)
    
    def _filter_dataclass_fields(self, data: Dict[str, Any], dataclass_type) -> Dict[str, Any]:
        """Filter data to only include fields that exist in the dataclass."""
        if not hasattr(dataclass_type, '__dataclass_fields__'):
            return data
        
        valid_fields = set(dataclass_type.__dataclass_fields__.keys())
        filtered_data = {}
        
        for key, value in data.items():
            if key in valid_fields:
                # Handle enum conversions
                field_type = dataclass_type.__dataclass_fields__[key].type
                if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
                    # Handle Optional types
                    args = getattr(field_type, '__args__', ())
                    if len(args) == 2 and type(None) in args:
                        field_type = args[0] if args[1] is type(None) else args[1]
                
                if isinstance(field_type, type) and issubclass(field_type, Enum):
                    try:
                        filtered_data[key] = field_type(value)
                    except ValueError:
                        # Use default if enum value is invalid
                        continue
                else:
                    filtered_data[key] = value
        
        return filtered_data
    
    def _get_environment_config_path(self) -> str:
        """Get environment-specific configuration file path."""
        base_path = Path(self.config_path)
        env_filename = f"{base_path.stem}.{self.environment}{base_path.suffix}"
        return str(base_path.parent / env_filename)
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _config_to_dict(self, config: TradingConfig) -> Dict[str, Any]:
        """Convert TradingConfig to dictionary."""
        config_dict = asdict(config)
        
        # Convert enums to their values
        def convert_enums(obj):
            if isinstance(obj, dict):
                return {k: convert_enums(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_enums(item) for item in obj]
            elif hasattr(obj, 'value'):  # Enum
                return obj.value
            else:
                return obj
        
        return convert_enums(config_dict)
    
    def _save_yaml(self, data: Dict[str, Any], file_path: str) -> None:
        """Save data as YAML file."""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)
    
    def _save_json(self, data: Dict[str, Any], file_path: str) -> None:
        """Save data as JSON file."""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# Convenience functions
def load_config(config_path: Optional[str] = None, environment: Optional[str] = None) -> TradingConfig:
    """
    Load configuration using default loader.
    
    Args:
        config_path: Path to configuration file
        environment: Environment name
        
    Returns:
        TradingConfig instance
    """
    loader = ConfigLoader(config_path, environment)
    return loader.load_config()


def save_config(config: TradingConfig, file_path: Optional[str] = None) -> None:
    """
    Save configuration using default loader.
    
    Args:
        config: Configuration to save
        file_path: File path to save to
    """
    loader = ConfigLoader()
    loader.save_config(config, file_path)