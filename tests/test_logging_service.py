"""
Unit tests for logging service.
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from kite_auto_trading.services.logging_service import (
    StructuredLogger,
    LogLevel,
    TradeLogger,
    ErrorLogger,
    PerformanceLogger,
    LoggingServiceImpl,
    JSONFormatter,
)
from kite_auto_trading.models.base import Order, OrderType, TransactionType


class TestStructuredLogger(unittest.TestCase):
    """Test structured logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.logger = StructuredLogger("test_logger", self.test_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers to release file locks
        for handler in self.logger.general_logger.handlers[:]:
            handler.close()
            self.logger.general_logger.removeHandler(handler)
        for handler in self.logger.trade_logger.handlers[:]:
            handler.close()
            self.logger.trade_logger.removeHandler(handler)
        for handler in self.logger.error_logger.handlers[:]:
            handler.close()
            self.logger.error_logger.removeHandler(handler)
        for handler in self.logger.performance_logger.handlers[:]:
            handler.close()
            self.logger.performance_logger.removeHandler(handler)
        
        # Small delay to ensure Windows releases file handles
        import time
        time.sleep(0.1)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_logger_initialization(self):
        """Test logger is properly initialized."""
        self.assertEqual(self.logger.name, "test_logger")
        self.assertTrue(Path(self.test_dir).exists())
        self.assertIsNotNone(self.logger.general_logger)
        self.assertIsNotNone(self.logger.trade_logger)
        self.assertIsNotNone(self.logger.error_logger)
        self.assertIsNotNone(self.logger.performance_logger)
    
    def test_log_creates_file(self):
        """Test that logging creates log file."""
        self.logger.info("Test message", key="value")
        
        log_file = Path(self.test_dir) / "general.log"
        self.assertTrue(log_file.exists())
    
    def test_log_json_format(self):
        """Test that logs are in JSON format."""
        self.logger.info("Test message", test_key="test_value")
        
        log_file = Path(self.test_dir) / "general.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["level"], "INFO")
            self.assertEqual(log_data["message"], "Test message")
            self.assertEqual(log_data["test_key"], "test_value")
            self.assertIn("timestamp", log_data)
    
    def test_log_levels(self):
        """Test different log levels."""
        self.logger.debug("Debug message")
        self.logger.info("Info message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        self.logger.critical("Critical message")
        
        log_file = Path(self.test_dir) / "general.log"
        with open(log_file, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 5)
            
            levels = [json.loads(line)["level"] for line in lines]
            self.assertEqual(levels, ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])


class TestJSONFormatter(unittest.TestCase):
    """Test JSON formatter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = JSONFormatter()
    
    def test_format_simple_message(self):
        """Test formatting simple message."""
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["message"], "Test message")
        self.assertIn("timestamp", log_data)
    
    def test_format_json_message(self):
        """Test formatting message that's already JSON."""
        import logging
        json_msg = json.dumps({"key": "value", "number": 42})
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg=json_msg,
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data["key"], "value")
        self.assertEqual(log_data["number"], 42)


class TestTradeLogger(unittest.TestCase):
    """Test trade logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.structured_logger = StructuredLogger("test_logger", self.test_dir)
        self.trade_logger = TradeLogger(self.structured_logger.trade_logger)
        
        self.sample_order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            price=None,
            trigger_price=None,
            strategy_id="test_strategy",
            timestamp=datetime.now()
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers
        for handler in self.structured_logger.trade_logger.handlers[:]:
            handler.close()
            self.structured_logger.trade_logger.removeHandler(handler)
        for handler in self.structured_logger.error_logger.handlers[:]:
            handler.close()
            self.structured_logger.error_logger.removeHandler(handler)
        
        import time
        time.sleep(0.1)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_log_order_placed(self):
        """Test logging order placement."""
        self.trade_logger.log_order_placed(self.sample_order, "test_strategy")
        
        log_file = Path(self.test_dir) / "trades.log"
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "order_placed")
            self.assertEqual(log_data["instrument"], "RELIANCE")
            self.assertEqual(log_data["transaction_type"], "BUY")
            self.assertEqual(log_data["quantity"], 10)
            self.assertEqual(log_data["strategy_id"], "test_strategy")
    
    def test_log_order_executed(self):
        """Test logging order execution."""
        execution_details = {
            "filled_quantity": 10,
            "average_price": 2500.50,
            "total_cost": 25005.00,
            "brokerage": 20.00,
            "taxes": 5.00,
            "status": "COMPLETE",
            "exchange_timestamp": datetime.now().isoformat()
        }
        
        self.trade_logger.log_order_executed(self.sample_order, execution_details)
        
        log_file = Path(self.test_dir) / "trades.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "order_executed")
            self.assertEqual(log_data["quantity"], 10)
            self.assertEqual(log_data["average_price"], 2500.50)
            self.assertEqual(log_data["brokerage"], 20.00)
    
    def test_log_order_rejected(self):
        """Test logging order rejection."""
        self.trade_logger.log_order_rejected(self.sample_order, "Insufficient funds")
        
        log_file = Path(self.test_dir) / "trades.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "order_rejected")
            self.assertEqual(log_data["reason"], "Insufficient funds")
    
    def test_log_order_cancelled(self):
        """Test logging order cancellation."""
        self.trade_logger.log_order_cancelled("ORDER123", "User requested")
        
        log_file = Path(self.test_dir) / "trades.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "order_cancelled")
            self.assertEqual(log_data["order_id"], "ORDER123")
            self.assertEqual(log_data["reason"], "User requested")


class TestErrorLogger(unittest.TestCase):
    """Test error logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.structured_logger = StructuredLogger("test_logger", self.test_dir)
        self.error_logger = ErrorLogger(self.structured_logger.error_logger)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers
        for handler in self.structured_logger.error_logger.handlers[:]:
            handler.close()
            self.structured_logger.error_logger.removeHandler(handler)
        
        import time
        time.sleep(0.1)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_log_error(self):
        """Test logging error with context."""
        error = ValueError("Invalid value")
        context = {"component": "test", "operation": "validation"}
        
        self.error_logger.log_error(error, context)
        
        log_file = Path(self.test_dir) / "errors.log"
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "error")
            self.assertEqual(log_data["error_type"], "ValueError")
            self.assertEqual(log_data["error_message"], "Invalid value")
            self.assertEqual(log_data["context"]["component"], "test")
    
    def test_log_api_error(self):
        """Test logging API error."""
        error = ConnectionError("API connection failed")
        
        self.error_logger.log_api_error("/api/orders", error, {"order_id": "123"})
        
        log_file = Path(self.test_dir) / "errors.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["context"]["component"], "api")
            self.assertEqual(log_data["context"]["endpoint"], "/api/orders")
    
    def test_log_strategy_error(self):
        """Test logging strategy error."""
        error = RuntimeError("Strategy execution failed")
        market_data = {"price": 2500, "volume": 1000}
        
        self.error_logger.log_strategy_error("test_strategy", error, market_data)
        
        log_file = Path(self.test_dir) / "errors.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["context"]["component"], "strategy")
            self.assertEqual(log_data["context"]["strategy_name"], "test_strategy")
    
    def test_log_risk_violation(self):
        """Test logging risk violation."""
        details = {"limit": 10000, "current": 12000, "instrument": "RELIANCE"}
        
        self.error_logger.log_risk_violation("position_limit_exceeded", details)
        
        log_file = Path(self.test_dir) / "errors.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "risk_violation")
            self.assertEqual(log_data["violation_type"], "position_limit_exceeded")


class TestPerformanceLogger(unittest.TestCase):
    """Test performance logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.structured_logger = StructuredLogger("test_logger", self.test_dir)
        self.performance_logger = PerformanceLogger(self.structured_logger.performance_logger)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers
        for handler in self.structured_logger.performance_logger.handlers[:]:
            handler.close()
            self.structured_logger.performance_logger.removeHandler(handler)
        
        import time
        time.sleep(0.1)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_log_metrics(self):
        """Test logging performance metrics."""
        metrics = {
            "total_pnl": 5000.00,
            "win_rate": 0.65,
            "sharpe_ratio": 1.5,
            "max_drawdown": -2000.00
        }
        
        self.performance_logger.log_metrics(metrics)
        
        log_file = Path(self.test_dir) / "performance.log"
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "performance_metrics")
            self.assertEqual(log_data["metrics"]["total_pnl"], 5000.00)
            self.assertEqual(log_data["metrics"]["win_rate"], 0.65)
    
    def test_log_system_health(self):
        """Test logging system health."""
        health_data = {
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "active_strategies": 3,
            "open_positions": 5
        }
        
        self.performance_logger.log_system_health(health_data)
        
        log_file = Path(self.test_dir) / "performance.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "system_health")
            self.assertEqual(log_data["health"]["cpu_usage"], 45.5)


class TestLoggingServiceImpl(unittest.TestCase):
    """Test logging service implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.logging_service = LoggingServiceImpl(self.test_dir)
        
        self.sample_order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            price=None,
            trigger_price=None,
            strategy_id="test_strategy",
            timestamp=datetime.now()
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers
        logger = self.logging_service.structured_logger
        for handler in logger.general_logger.handlers[:]:
            handler.close()
            logger.general_logger.removeHandler(handler)
        for handler in logger.trade_logger.handlers[:]:
            handler.close()
            logger.trade_logger.removeHandler(handler)
        for handler in logger.error_logger.handlers[:]:
            handler.close()
            logger.error_logger.removeHandler(handler)
        for handler in logger.performance_logger.handlers[:]:
            handler.close()
            logger.performance_logger.removeHandler(handler)
        
        import time
        time.sleep(0.1)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_log_trade(self):
        """Test logging trade through service."""
        execution_details = {
            "filled_quantity": 10,
            "average_price": 2500.50,
            "status": "COMPLETE"
        }
        
        self.logging_service.log_trade(self.sample_order, execution_details)
        
        log_file = Path(self.test_dir) / "trades.log"
        self.assertTrue(log_file.exists())
    
    def test_log_error(self):
        """Test logging error through service."""
        error = ValueError("Test error")
        context = {"component": "test"}
        
        self.logging_service.log_error(error, context)
        
        log_file = Path(self.test_dir) / "errors.log"
        self.assertTrue(log_file.exists())
    
    def test_log_performance_metrics(self):
        """Test logging performance metrics through service."""
        metrics = {"total_pnl": 5000.00}
        
        self.logging_service.log_performance_metrics(metrics)
        
        log_file = Path(self.test_dir) / "performance.log"
        self.assertTrue(log_file.exists())
    
    def test_send_notification(self):
        """Test sending notification through service."""
        self.logging_service.send_notification("Critical alert", "CRITICAL")
        
        log_file = Path(self.test_dir) / "general.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data["event"], "notification")
            self.assertEqual(log_data["level"], "CRITICAL")


if __name__ == '__main__':
    unittest.main()
