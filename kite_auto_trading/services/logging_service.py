"""
Comprehensive logging service for the Kite Auto-Trading application.

This module provides structured logging with JSON format, trade execution audit trails,
and error logging with context information.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from enum import Enum

from kite_auto_trading.models.base import Order


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """
    Structured logger that outputs logs in JSON format for easy parsing and analysis.
    """
    
    def __init__(self, name: str, log_dir: str = "logs"):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            log_dir: Directory for log files
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create separate loggers for different purposes
        self.general_logger = self._create_logger(f"{name}.general", "general.log")
        self.trade_logger = self._create_logger(f"{name}.trades", "trades.log")
        self.error_logger = self._create_logger(f"{name}.errors", "errors.log")
        self.performance_logger = self._create_logger(f"{name}.performance", "performance.log")
    
    def _create_logger(self, logger_name: str, filename: str) -> logging.Logger:
        """
        Create a logger with JSON formatter.
        
        Args:
            logger_name: Name of the logger
            filename: Log file name
            
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(
            self.log_dir / filename,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
        
        # Console handler for errors
        if "error" in logger_name:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(JSONFormatter())
            logger.addHandler(console_handler)
        
        logger.propagate = False
        return logger
    
    def log(self, level: LogLevel, message: str, **kwargs):
        """
        Log a message with structured data.
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional structured data
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            **kwargs
        }
        
        log_method = getattr(self.general_logger, level.value.lower())
        log_method(json.dumps(log_data))
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in JSON format.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record
            
        Returns:
            JSON formatted log string
        """
        # Try to parse message as JSON if it's already JSON
        try:
            log_data = json.loads(record.getMessage())
        except (json.JSONDecodeError, ValueError):
            # If not JSON, create structured log
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class TradeLogger:
    """
    Specialized logger for trade execution with complete audit trail.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize trade logger.
        
        Args:
            logger: Underlying logger instance
        """
        self.logger = logger
    
    def log_order_placed(self, order: Order, strategy_id: str):
        """
        Log order placement.
        
        Args:
            order: Order object
            strategy_id: Strategy that generated the order
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "order_placed",
            "order_id": getattr(order, 'order_id', None),
            "instrument": order.instrument,
            "transaction_type": order.transaction_type.value,
            "quantity": order.quantity,
            "order_type": order.order_type.value,
            "price": order.price,
            "trigger_price": order.trigger_price,
            "strategy_id": strategy_id
        }
        self.logger.info(json.dumps(log_data))
    
    def log_order_executed(self, order: Order, execution_details: Dict[str, Any]):
        """
        Log order execution.
        
        Args:
            order: Order object
            execution_details: Execution details including fill price, quantity, etc.
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "order_executed",
            "order_id": getattr(order, 'order_id', None),
            "instrument": order.instrument,
            "transaction_type": order.transaction_type.value,
            "quantity": execution_details.get('filled_quantity', order.quantity),
            "average_price": execution_details.get('average_price'),
            "total_cost": execution_details.get('total_cost'),
            "brokerage": execution_details.get('brokerage', 0),
            "taxes": execution_details.get('taxes', 0),
            "status": execution_details.get('status'),
            "exchange_timestamp": execution_details.get('exchange_timestamp')
        }
        self.logger.info(json.dumps(log_data))
    
    def log_order_rejected(self, order: Order, reason: str):
        """
        Log order rejection.
        
        Args:
            order: Order object
            reason: Rejection reason
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "order_rejected",
            "order_id": getattr(order, 'order_id', None),
            "instrument": order.instrument,
            "transaction_type": order.transaction_type.value,
            "quantity": order.quantity,
            "reason": reason
        }
        self.logger.warning(json.dumps(log_data))
    
    def log_order_cancelled(self, order_id: str, reason: str):
        """
        Log order cancellation.
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "order_cancelled",
            "order_id": order_id,
            "reason": reason
        }
        self.logger.info(json.dumps(log_data))


class ErrorLogger:
    """
    Specialized logger for errors with context and debugging information.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize error logger.
        
        Args:
            logger: Underlying logger instance
        """
        self.logger = logger
    
    def log_error(self, error: Exception, context: Dict[str, Any], severity: str = "ERROR"):
        """
        Log error with context information.
        
        Args:
            error: Exception object
            context: Context information
            severity: Error severity level
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "error",
            "severity": severity,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context
        }
        
        if severity == "CRITICAL":
            self.logger.critical(json.dumps(log_data), exc_info=True)
        else:
            self.logger.error(json.dumps(log_data), exc_info=True)
    
    def log_api_error(self, endpoint: str, error: Exception, request_data: Optional[Dict[str, Any]] = None):
        """
        Log API-related error.
        
        Args:
            endpoint: API endpoint
            error: Exception object
            request_data: Request data (optional)
        """
        context = {
            "component": "api",
            "endpoint": endpoint,
            "request_data": request_data
        }
        self.log_error(error, context)
    
    def log_strategy_error(self, strategy_name: str, error: Exception, market_data: Optional[Dict[str, Any]] = None):
        """
        Log strategy-related error.
        
        Args:
            strategy_name: Strategy name
            error: Exception object
            market_data: Market data at time of error (optional)
        """
        context = {
            "component": "strategy",
            "strategy_name": strategy_name,
            "market_data": market_data
        }
        self.log_error(error, context)
    
    def log_risk_violation(self, violation_type: str, details: Dict[str, Any]):
        """
        Log risk management violation.
        
        Args:
            violation_type: Type of violation
            details: Violation details
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "risk_violation",
            "violation_type": violation_type,
            "details": details
        }
        self.logger.warning(json.dumps(log_data))


class PerformanceLogger:
    """
    Logger for performance metrics and system health.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize performance logger.
        
        Args:
            logger: Underlying logger instance
        """
        self.logger = logger
    
    def log_metrics(self, metrics: Dict[str, Any]):
        """
        Log performance metrics.
        
        Args:
            metrics: Performance metrics dictionary
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "performance_metrics",
            "metrics": metrics
        }
        self.logger.info(json.dumps(log_data))
    
    def log_system_health(self, health_data: Dict[str, Any]):
        """
        Log system health information.
        
        Args:
            health_data: System health data
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "system_health",
            "health": health_data
        }
        self.logger.info(json.dumps(log_data))


class LoggingServiceImpl:
    """
    Implementation of LoggingService interface with comprehensive logging capabilities.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize logging service.
        
        Args:
            log_dir: Directory for log files
        """
        self.structured_logger = StructuredLogger("kite_auto_trading", log_dir)
        self.trade_logger = TradeLogger(self.structured_logger.trade_logger)
        self.error_logger = ErrorLogger(self.structured_logger.error_logger)
        self.performance_logger = PerformanceLogger(self.structured_logger.performance_logger)
    
    def log_trade(self, order: Order, execution_details: Dict[str, Any]) -> None:
        """
        Log trade execution details.
        
        Args:
            order: Order object
            execution_details: Execution details
        """
        self.trade_logger.log_order_executed(order, execution_details)
    
    def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Log error with context information.
        
        Args:
            error: Exception object
            context: Context information
        """
        self.error_logger.log_error(error, context)
    
    def log_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics.
        
        Args:
            metrics: Performance metrics
        """
        self.performance_logger.log_metrics(metrics)
    
    def send_notification(self, message: str, level: str) -> None:
        """
        Send notification for critical events.
        
        Args:
            message: Notification message
            level: Notification level
        """
        # Log as structured message
        self.structured_logger.log(
            LogLevel[level.upper()],
            message,
            event="notification",
            notification_level=level
        )
