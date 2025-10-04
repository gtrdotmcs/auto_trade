"""
Logging configuration for Kite Auto Trading application.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Dict, Any

from .constants import DEFAULT_LOG_PATH, LOG_LEVEL_INFO


def setup_logging(config: Dict[str, Any] = None) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        config: Logging configuration dictionary
    """
    if config is None:
        config = get_default_logging_config()
    
    # Create logs directory if it doesn't exist
    log_file_path = config.get('file_path', DEFAULT_LOG_PATH)
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.get('level', LOG_LEVEL_INFO)),
        format=config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        handlers=[]
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Add console handler if enabled
    if config.get('console_output', True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.get('level', LOG_LEVEL_INFO)))
        console_formatter = logging.Formatter(config.get('format'))
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=_parse_file_size(config.get('max_file_size', '10MB')),
        backupCount=config.get('backup_count', 5),
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, config.get('level', LOG_LEVEL_INFO)))
    file_formatter = logging.Formatter(config.get('format'))
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_default_logging_config() -> Dict[str, Any]:
    """
    Get default logging configuration.
    
    Returns:
        Default logging configuration dictionary
    """
    return {
        'level': LOG_LEVEL_INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_path': DEFAULT_LOG_PATH,
        'max_file_size': '10MB',
        'backup_count': 5,
        'console_output': True
    }


def _parse_file_size(size_str: str) -> int:
    """
    Parse file size string to bytes.
    
    Args:
        size_str: Size string like '10MB', '1GB', etc.
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        # Assume bytes if no unit specified
        return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)