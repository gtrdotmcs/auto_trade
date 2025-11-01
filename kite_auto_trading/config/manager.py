"""
Configuration manager for Kite Auto Trading application.
"""

import os
import threading
from pathlib import Path
from typing import Optional, Callable, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .loader import ConfigLoader, ConfigurationError
from .models import TradingConfig
from .constants import DEFAULT_CONFIG_PATH


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.config_files = {
            config_manager.loader.config_path,
            config_manager.loader._get_environment_config_path()
        }
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path in self.config_files:
            self.config_manager._reload_config()


class ConfigManager:
    """
    Configuration manager with hot-reloading and change notification support.
    """
    
    def __init__(self, config_path: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
            environment: Environment name
        """
        self.loader = ConfigLoader(config_path, environment)
        self._config: Optional[TradingConfig] = None
        self._lock = threading.RLock()
        self._observers: list = []
        self._file_observer: Optional[Observer] = None
        self._change_callbacks: list[Callable[[TradingConfig], None]] = []
        
    def get_config(self) -> TradingConfig:
        """
        Get current configuration.
        
        Returns:
            Current TradingConfig instance
        """
        with self._lock:
            if self._config is None:
                self._config = self.loader.load_config()
            return self._config
    
    def reload_config(self) -> TradingConfig:
        """
        Manually reload configuration from file.
        
        Returns:
            Reloaded TradingConfig instance
        """
        with self._lock:
            old_config = self._config
            try:
                self._config = self.loader.reload_config()
                self._notify_change_callbacks(self._config)
                return self._config
            except ConfigurationError:
                # Keep old config if reload fails
                if old_config is not None:
                    self._config = old_config
                raise
    
    def save_config(self, config: Optional[TradingConfig] = None, file_path: Optional[str] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save (defaults to current config)
            file_path: File path to save to
        """
        with self._lock:
            config_to_save = config or self._config
            if config_to_save is None:
                raise ConfigurationError("No configuration to save")
            
            self.loader.save_config(config_to_save, file_path)
            
            # Update current config if we saved it
            if config is not None:
                self._config = config
    
    def update_config(self, **kwargs) -> TradingConfig:
        """
        Update configuration with new values.
        
        Args:
            **kwargs: Configuration updates
            
        Returns:
            Updated TradingConfig instance
        """
        with self._lock:
            current_config = self.get_config()
            
            # Create updated config
            config_dict = self.loader._config_to_dict(current_config)
            
            # Apply updates
            for key, value in kwargs.items():
                if '.' in key:
                    # Handle nested updates like 'api.timeout'
                    keys = key.split('.')
                    target = config_dict
                    for k in keys[:-1]:
                        target = target.setdefault(k, {})
                    target[keys[-1]] = value
                else:
                    config_dict[key] = value
            
            # Create new config object
            updated_config = self.loader._create_config_object(config_dict)
            
            # Validate
            validation_errors = updated_config.validate()
            if validation_errors:
                raise ConfigurationError(f"Configuration validation failed: {', '.join(validation_errors)}")
            
            self._config = updated_config
            self._notify_change_callbacks(updated_config)
            return updated_config
    
    def start_hot_reload(self) -> None:
        """Start hot-reloading of configuration files."""
        if self._file_observer is not None:
            return  # Already started
        
        config_path = Path(self.loader.config_path)
        if not config_path.exists():
            return  # No config file to watch
        
        try:
            self._file_observer = Observer()
            event_handler = ConfigFileHandler(self)
            self._file_observer.schedule(
                event_handler,
                str(config_path.parent),
                recursive=False
            )
            self._file_observer.start()
        except Exception:
            # Hot-reload is optional, don't fail if it can't be started
            self._file_observer = None
    
    def stop_hot_reload(self) -> None:
        """Stop hot-reloading of configuration files."""
        if self._file_observer is not None:
            self._file_observer.stop()
            self._file_observer.join()
            self._file_observer = None
    
    def add_change_callback(self, callback: Callable[[TradingConfig], None]) -> None:
        """
        Add callback to be called when configuration changes.
        
        Args:
            callback: Function to call with new configuration
        """
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[TradingConfig], None]) -> None:
        """
        Remove configuration change callback.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _reload_config(self) -> None:
        """Internal method to reload configuration (called by file watcher)."""
        try:
            self.reload_config()
        except ConfigurationError:
            # Log error but don't crash on hot-reload failure
            pass
    
    def _notify_change_callbacks(self, config: TradingConfig) -> None:
        """Notify all change callbacks of configuration update."""
        for callback in self._change_callbacks:
            try:
                callback(config)
            except Exception:
                # Don't let callback errors affect config management
                pass
    
    def __enter__(self):
        """Context manager entry."""
        self.start_hot_reload()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_hot_reload()


# Global configuration manager instance
_global_config_manager: Optional[ConfigManager] = None
_global_lock = threading.Lock()


def get_config_manager(config_path: Optional[str] = None, environment: Optional[str] = None) -> ConfigManager:
    """
    Get global configuration manager instance.
    
    Args:
        config_path: Path to configuration file (only used on first call)
        environment: Environment name (only used on first call)
        
    Returns:
        ConfigManager instance
    """
    global _global_config_manager
    
    with _global_lock:
        if _global_config_manager is None:
            _global_config_manager = ConfigManager(config_path, environment)
        return _global_config_manager


def get_config() -> TradingConfig:
    """
    Get current configuration from global manager.
    
    Returns:
        Current TradingConfig instance
    """
    return get_config_manager().get_config()


def reload_config() -> TradingConfig:
    """
    Reload configuration from global manager.
    
    Returns:
        Reloaded TradingConfig instance
    """
    return get_config_manager().reload_config()