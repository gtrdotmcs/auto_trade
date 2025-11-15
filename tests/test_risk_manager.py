"""
Unit tests for Risk Manager Service.
"""

import unittest
from datetime import datetime, date, timedelta
from kite_auto_trading.services.risk_manager import (
    RiskManagerService,
    RiskValidationResult,
    PositionSizeResult
)
from kite_auto_trading.models.base import Order, Position, OrderType, TransactionType
from kite_auto_trading.config.models import RiskManagementConfig, PortfolioConfig


class TestRiskManagerInitialization(unittest.TestCase):
    """Test RiskManager initialization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        self.portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
    
    def test_initialization_with_valid_config(self):
        """Test RiskManager initializes correctly with valid configuration."""
        manager = RiskManagerService(self.risk_config, self.portfolio_config)
        
        self.assertEqual(manager.risk_config, self.risk_config)
        self.assertEqual(manager.portfolio_config, self.portfolio_config)
        self.assertEqual(manager._daily_pnl, 0.0)
        self.assertEqual(manager._daily_trades, 0)
        self.assertEqual(manager._current_date, date.today())
        self.assertEqual(manager._total_portfolio_value, self.portfolio_config.initial_capital)
    
    def test_initialization_sets_logger(self):
        """Test that logger is properly initialized."""
        manager = RiskManagerService(self.risk_config, self.portfolio_config)
        self.assertIsNotNone(manager.logger)
        self.assertEqual(manager.logger.name, "kite_auto_trading.services.risk_manager")


class TestPositionSizing(unittest.TestCase):
    """Test position sizing calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_calculate_position_size_with_stop_loss(self):
        """Test position size calculation with stop loss."""
        signal = {
            'risk_percent': 2.0,
            'stop_loss_percent': 2.0
        }
        current_price = 2500.0
        account_balance = 100000.0
        
        result = self.risk_manager.calculate_position_size(signal, current_price, account_balance)
        
        self.assertIsInstance(result, PositionSizeResult)
        self.assertGreater(result.quantity, 0)
        self.assertGreater(result.risk_amount, 0)
        self.assertGreater(result.position_value, 0)
        # With 2% risk on 100k = 2000, and 2% stop loss on 2500 = 50 per share
        # Expected quantity = 2000 / 50 = 40
        self.assertEqual(result.quantity, 40)
    
    def test_calculate_position_size_without_stop_loss(self):
        """Test position size calculation without stop loss."""
        signal = {
            'risk_percent': 2.0,
            'stop_loss_percent': 0.0
        }
        current_price = 2500.0
        account_balance = 100000.0
        
        result = self.risk_manager.calculate_position_size(signal, current_price, account_balance)
        
        self.assertIsInstance(result, PositionSizeResult)
        self.assertGreater(result.quantity, 0)
        # With 2% position size on 100k = 2000 / 2500 = 0.8, rounds to 1
        self.assertEqual(result.quantity, 1)
    
    def test_calculate_position_size_exceeds_balance(self):
        """Test position size calculation when it exceeds available balance."""
        signal = {
            'risk_percent': 50.0,  # Very high risk
            'stop_loss_percent': 1.0
        }
        current_price = 2500.0
        account_balance = 10000.0  # Small balance
        
        result = self.risk_manager.calculate_position_size(signal, current_price, account_balance)
        
        # Should limit to what's affordable
        self.assertLessEqual(result.quantity, int(account_balance / current_price))
        self.assertLessEqual(result.position_value, account_balance)
    
    def test_calculate_position_size_minimum_quantity(self):
        """Test that minimum quantity is always 1."""
        signal = {
            'risk_percent': 0.01,  # Very small risk
            'stop_loss_percent': 2.0
        }
        current_price = 10000.0  # High price
        account_balance = 100000.0
        
        result = self.risk_manager.calculate_position_size(signal, current_price, account_balance)
        
        self.assertGreaterEqual(result.quantity, 1)


class TestOrderValidation(unittest.TestCase):
    """Test order validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=2,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_validate_order_passes_all_checks(self):
        """Test order validation when all checks pass."""
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=1,  # 1 * 2500 = 2500, which is 2.5% but within reasonable limits
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        current_price=1000.0  # 1 * 1000 = 1000, which is 1% of portfolio
        available_funds = 50000.0
        
        result = self.risk_manager.validate_order(order, current_price, available_funds)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.reason, "Order passes all risk checks")
    
    def test_validate_order_insufficient_funds(self):
        """Test order validation with insufficient funds."""
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        current_price = 2500.0
        available_funds = 10000.0  # Not enough for 100 shares
        
        result = self.risk_manager.validate_order(order, current_price, available_funds)
        
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "Insufficient funds")
        self.assertIsNotNone(result.suggested_quantity)
        self.assertEqual(result.suggested_quantity, 4)  # 10000 / 2500 = 4
    
    def test_validate_order_exceeds_position_size_limit(self):
        """Test order validation when position size exceeds limit."""
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=100,  # 100 * 2500 = 250000, which is > 2% of 100000
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        current_price = 2500.0
        available_funds = 300000.0
        
        result = self.risk_manager.validate_order(order, current_price, available_funds)
        
        self.assertFalse(result.is_valid)
        self.assertIn("Position size exceeds limit", result.reason)
        self.assertIsNotNone(result.suggested_quantity)
    
    def test_validate_order_max_positions_per_instrument(self):
        """Test order validation when max positions per instrument reached."""
        # Add positions to reach limit
        position1 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        position2 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        self.risk_manager.add_position(position1)
        self.risk_manager.add_position(position2)
        
        # Try to add another position
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        current_price = 2500.0
        available_funds = 50000.0
        
        result = self.risk_manager.validate_order(order, current_price, available_funds)
        
        self.assertFalse(result.is_valid)
        self.assertIn("Maximum positions per instrument", result.reason)
    
    def test_validate_order_daily_loss_limit_exceeded(self):
        """Test order validation when daily loss limit is exceeded."""
        # Simulate daily loss exceeding limit
        self.risk_manager.update_daily_pnl(-11000.0)  # Exceeds 10000 limit
        
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        current_price = 2500.0
        available_funds = 50000.0
        
        result = self.risk_manager.validate_order(order, current_price, available_funds)
        
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "Daily loss limit exceeded")


class TestPositionTracking(unittest.TestCase):
    """Test position tracking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=3,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_add_position(self):
        """Test adding a position."""
        position = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position)
        
        positions = self.risk_manager.get_positions("RELIANCE")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].instrument, "RELIANCE")
        self.assertEqual(positions[0].quantity, 10)
    
    def test_add_multiple_positions_same_instrument(self):
        """Test adding multiple positions for same instrument."""
        position1 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        position2 = Position(
            instrument="RELIANCE",
            quantity=15,
            average_price=2550.0,
            current_price=2550.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position1)
        self.risk_manager.add_position(position2)
        
        positions = self.risk_manager.get_positions("RELIANCE")
        self.assertEqual(len(positions), 2)
    
    def test_remove_position(self):
        """Test removing a position."""
        position = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position)
        result = self.risk_manager.remove_position("RELIANCE")
        
        self.assertTrue(result)
        positions = self.risk_manager.get_positions("RELIANCE")
        self.assertEqual(len(positions), 0)
    
    def test_remove_position_nonexistent(self):
        """Test removing a position that doesn't exist."""
        result = self.risk_manager.remove_position("NONEXISTENT")
        self.assertFalse(result)
    
    def test_get_position_count(self):
        """Test getting position count for an instrument."""
        position1 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        position2 = Position(
            instrument="RELIANCE",
            quantity=15,
            average_price=2550.0,
            current_price=2550.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position1)
        self.risk_manager.add_position(position2)
        
        count = self.risk_manager.get_position_count("RELIANCE")
        self.assertEqual(count, 2)
    
    def test_get_all_positions(self):
        """Test getting all positions across instruments."""
        position1 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        position2 = Position(
            instrument="TCS",
            quantity=5,
            average_price=3500.0,
            current_price=3500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position1)
        self.risk_manager.add_position(position2)
        
        all_positions = self.risk_manager.get_positions()
        self.assertEqual(len(all_positions), 2)


class TestDailyMetrics(unittest.TestCase):
    """Test daily metrics tracking."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_update_daily_pnl_profit(self):
        """Test updating daily P&L with profit."""
        self.risk_manager.update_daily_pnl(500.0)
        
        metrics = self.risk_manager.get_daily_metrics()
        self.assertEqual(metrics['daily_pnl'], 500.0)
        self.assertEqual(metrics['daily_trades'], 1)
        self.assertTrue(metrics['within_limits'])
    
    def test_update_daily_pnl_loss(self):
        """Test updating daily P&L with loss."""
        self.risk_manager.update_daily_pnl(-2000.0)
        
        metrics = self.risk_manager.get_daily_metrics()
        self.assertEqual(metrics['daily_pnl'], -2000.0)
        self.assertEqual(metrics['daily_trades'], 1)
        self.assertTrue(metrics['within_limits'])
    
    def test_update_daily_pnl_multiple_trades(self):
        """Test updating daily P&L with multiple trades."""
        self.risk_manager.update_daily_pnl(500.0)
        self.risk_manager.update_daily_pnl(-300.0)
        self.risk_manager.update_daily_pnl(200.0)
        
        metrics = self.risk_manager.get_daily_metrics()
        self.assertEqual(metrics['daily_pnl'], 400.0)
        self.assertEqual(metrics['daily_trades'], 3)
    
    def test_check_daily_limits_within_bounds(self):
        """Test daily limits check when within bounds."""
        self.risk_manager.update_daily_pnl(-5000.0)
        
        result = self.risk_manager.check_daily_limits()
        self.assertTrue(result)
    
    def test_check_daily_limits_exceeded(self):
        """Test daily limits check when exceeded."""
        self.risk_manager.update_daily_pnl(-11000.0)
        
        result = self.risk_manager.check_daily_limits()
        self.assertFalse(result)
    
    def test_get_daily_metrics(self):
        """Test getting daily metrics."""
        self.risk_manager.update_daily_pnl(-3000.0)
        
        metrics = self.risk_manager.get_daily_metrics()
        
        self.assertIn('date', metrics)
        self.assertIn('daily_pnl', metrics)
        self.assertIn('daily_trades', metrics)
        self.assertIn('daily_loss_limit', metrics)
        self.assertIn('remaining_loss_capacity', metrics)
        self.assertIn('within_limits', metrics)
        
        self.assertEqual(metrics['daily_pnl'], -3000.0)
        self.assertEqual(metrics['daily_trades'], 1)
        self.assertEqual(metrics['daily_loss_limit'], 10000.0)
        self.assertEqual(metrics['remaining_loss_capacity'], 7000.0)


class TestPortfolioValueUpdate(unittest.TestCase):
    """Test portfolio value updates."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_update_portfolio_value(self):
        """Test updating portfolio value."""
        new_value = 120000.0
        self.risk_manager.update_portfolio_value(new_value)
        
        self.assertEqual(self.risk_manager._total_portfolio_value, new_value)
    
    def test_position_size_calculation_uses_updated_portfolio_value(self):
        """Test that position sizing uses updated portfolio value."""
        # Update portfolio value
        self.risk_manager.update_portfolio_value(200000.0)
        
        signal = {
            'risk_percent': 2.0,
            'stop_loss_percent': 0.0
        }
        current_price = 2500.0
        account_balance = 200000.0
        
        result = self.risk_manager.calculate_position_size(signal, current_price, account_balance)
        
        # With 2% of 200k = 4000 / 2500 = 1.6, rounds to 1
        self.assertEqual(result.quantity, 1)


if __name__ == '__main__':
    unittest.main()


class TestEmergencyStop(unittest.TestCase):
    """Test emergency stop functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_trigger_emergency_stop(self):
        """Test triggering emergency stop."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.assertFalse(self.risk_manager.is_emergency_stop_active())
        
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.DAILY_LOSS_LIMIT)
        
        self.assertTrue(self.risk_manager.is_emergency_stop_active())
        
        info = self.risk_manager.get_emergency_stop_info()
        self.assertIsNotNone(info)
        self.assertTrue(info['active'])
        self.assertEqual(info['reason'], EmergencyStopReason.DAILY_LOSS_LIMIT.value)
    
    def test_clear_emergency_stop(self):
        """Test clearing emergency stop."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.MANUAL_TRIGGER)
        self.assertTrue(self.risk_manager.is_emergency_stop_active())
        
        result = self.risk_manager.clear_emergency_stop()
        
        self.assertTrue(result)
        self.assertFalse(self.risk_manager.is_emergency_stop_active())
        self.assertIsNone(self.risk_manager.get_emergency_stop_info())
    
    def test_clear_emergency_stop_when_not_active(self):
        """Test clearing emergency stop when it's not active."""
        result = self.risk_manager.clear_emergency_stop()
        self.assertFalse(result)
    
    def test_validate_order_with_emergency_stop_active(self):
        """Test that orders are rejected when emergency stop is active."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.MAX_DRAWDOWN)
        
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            strategy_id="test_strategy"
        )
        
        result = self.risk_manager.validate_order(order, 2500.0, 50000.0)
        
        self.assertFalse(result.is_valid)
        self.assertIn("Emergency stop active", result.reason)
    
    def test_emergency_stop_callback(self):
        """Test emergency stop callback execution."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        callback_executed = []
        
        def test_callback(reason: EmergencyStopReason):
            callback_executed.append(reason)
        
        self.risk_manager.register_emergency_stop_callback(test_callback)
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.SYSTEM_ERROR)
        
        self.assertEqual(len(callback_executed), 1)
        self.assertEqual(callback_executed[0], EmergencyStopReason.SYSTEM_ERROR)
    
    def test_multiple_emergency_stop_callbacks(self):
        """Test multiple emergency stop callbacks."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        callback_count = [0]
        
        def callback1(reason):
            callback_count[0] += 1
        
        def callback2(reason):
            callback_count[0] += 10
        
        self.risk_manager.register_emergency_stop_callback(callback1)
        self.risk_manager.register_emergency_stop_callback(callback2)
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.MANUAL_TRIGGER)
        
        self.assertEqual(callback_count[0], 11)


class TestDrawdownMonitoring(unittest.TestCase):
    """Test drawdown monitoring functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_initial_drawdown_metrics(self):
        """Test initial drawdown metrics."""
        metrics = self.risk_manager.get_drawdown_metrics()
        
        self.assertEqual(metrics.peak_value, 100000.0)
        self.assertEqual(metrics.current_value, 100000.0)
        self.assertEqual(metrics.current_drawdown_percent, 0.0)
        self.assertEqual(metrics.max_drawdown_percent, 0.0)
    
    def test_update_drawdown_with_profit(self):
        """Test drawdown tracking when portfolio increases."""
        self.risk_manager.update_drawdown_tracking(120000.0)
        
        metrics = self.risk_manager.get_drawdown_metrics()
        
        self.assertEqual(metrics.peak_value, 120000.0)
        self.assertEqual(metrics.current_value, 120000.0)
        self.assertEqual(metrics.current_drawdown_percent, 0.0)
    
    def test_update_drawdown_with_loss(self):
        """Test drawdown tracking when portfolio decreases."""
        self.risk_manager.update_drawdown_tracking(90000.0)
        
        metrics = self.risk_manager.get_drawdown_metrics()
        
        self.assertEqual(metrics.peak_value, 100000.0)
        self.assertEqual(metrics.current_value, 90000.0)
        self.assertEqual(metrics.current_drawdown_percent, 10.0)
        self.assertEqual(metrics.max_drawdown_percent, 10.0)
    
    def test_drawdown_recovery(self):
        """Test drawdown tracking during recovery."""
        # Drop to 80k (20% drawdown)
        self.risk_manager.update_drawdown_tracking(80000.0)
        
        metrics = self.risk_manager.get_drawdown_metrics()
        self.assertEqual(metrics.current_drawdown_percent, 20.0)
        self.assertEqual(metrics.max_drawdown_percent, 20.0)
        
        # Recover to 95k (5% drawdown from peak)
        self.risk_manager.update_drawdown_tracking(95000.0)
        
        metrics = self.risk_manager.get_drawdown_metrics()
        self.assertEqual(metrics.current_drawdown_percent, 5.0)
        self.assertEqual(metrics.max_drawdown_percent, 20.0)  # Max stays at 20%
    
    def test_new_peak_after_recovery(self):
        """Test new peak establishment after recovery."""
        # Drop and recover
        self.risk_manager.update_drawdown_tracking(90000.0)
        self.risk_manager.update_drawdown_tracking(110000.0)
        
        metrics = self.risk_manager.get_drawdown_metrics()
        
        self.assertEqual(metrics.peak_value, 110000.0)
        self.assertEqual(metrics.current_drawdown_percent, 0.0)
        # Max drawdown from previous period should be preserved
        self.assertEqual(metrics.max_drawdown_percent, 10.0)


class TestLimitEnforcement(unittest.TestCase):
    """Test limit enforcement and protective actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_check_and_enforce_limits_within_bounds(self):
        """Test limit enforcement when all limits are within bounds."""
        self.risk_manager.update_daily_pnl(-5000.0)
        
        result = self.risk_manager.check_and_enforce_limits()
        
        self.assertTrue(result)
        self.assertFalse(self.risk_manager.is_emergency_stop_active())
    
    def test_check_and_enforce_limits_daily_loss_exceeded(self):
        """Test limit enforcement when daily loss limit is exceeded."""
        self.risk_manager.update_daily_pnl(-11000.0)
        
        result = self.risk_manager.check_and_enforce_limits()
        
        self.assertFalse(result)
        self.assertTrue(self.risk_manager.is_emergency_stop_active())
        
        info = self.risk_manager.get_emergency_stop_info()
        self.assertEqual(info['reason'], "Daily loss limit exceeded")
    
    def test_check_and_enforce_limits_max_drawdown_exceeded(self):
        """Test limit enforcement when max drawdown is exceeded."""
        # Simulate 25% drawdown (exceeds 20% threshold)
        self.risk_manager.update_drawdown_tracking(75000.0)
        
        result = self.risk_manager.check_and_enforce_limits()
        
        self.assertFalse(result)
        self.assertTrue(self.risk_manager.is_emergency_stop_active())
        
        info = self.risk_manager.get_emergency_stop_info()
        self.assertEqual(info['reason'], "Maximum drawdown exceeded")
    
    def test_check_and_enforce_limits_with_emergency_stop_disabled(self):
        """Test limit enforcement when emergency stop is disabled."""
        # Disable emergency stop
        self.risk_manager.risk_config.emergency_stop_enabled = False
        
        self.risk_manager.update_daily_pnl(-11000.0)
        
        result = self.risk_manager.check_and_enforce_limits()
        
        # Should return False but not trigger emergency stop
        self.assertFalse(result)
        self.assertFalse(self.risk_manager.is_emergency_stop_active())
    
    def test_check_and_enforce_limits_already_in_emergency_stop(self):
        """Test limit enforcement when already in emergency stop."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.MANUAL_TRIGGER)
        
        result = self.risk_manager.check_and_enforce_limits()
        
        self.assertFalse(result)
        # Should still be in emergency stop with original reason
        info = self.risk_manager.get_emergency_stop_info()
        self.assertEqual(info['reason'], EmergencyStopReason.MANUAL_TRIGGER.value)


class TestRiskStatus(unittest.TestCase):
    """Test comprehensive risk status reporting."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=2,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_get_risk_status_normal_conditions(self):
        """Test risk status report under normal conditions."""
        status = self.risk_manager.get_risk_status()
        
        self.assertIn('emergency_stop', status)
        self.assertIn('daily_metrics', status)
        self.assertIn('drawdown', status)
        self.assertIn('position_count', status)
        self.assertIn('instruments_traded', status)
        
        self.assertIsNone(status['emergency_stop'])
        self.assertEqual(status['position_count'], 0)
        self.assertEqual(status['instruments_traded'], 0)
    
    def test_get_risk_status_with_positions(self):
        """Test risk status report with active positions."""
        position1 = Position(
            instrument="RELIANCE",
            quantity=10,
            average_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        position2 = Position(
            instrument="TCS",
            quantity=5,
            average_price=3500.0,
            current_price=3500.0,
            unrealized_pnl=0.0,
            strategy_id="test_strategy",
            entry_time=datetime.now()
        )
        
        self.risk_manager.add_position(position1)
        self.risk_manager.add_position(position2)
        
        status = self.risk_manager.get_risk_status()
        
        self.assertEqual(status['position_count'], 2)
        self.assertEqual(status['instruments_traded'], 2)
    
    def test_get_risk_status_with_emergency_stop(self):
        """Test risk status report with emergency stop active."""
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.risk_manager.trigger_emergency_stop(EmergencyStopReason.DAILY_LOSS_LIMIT)
        
        status = self.risk_manager.get_risk_status()
        
        self.assertIsNotNone(status['emergency_stop'])
        self.assertTrue(status['emergency_stop']['active'])
        self.assertEqual(status['emergency_stop']['reason'], EmergencyStopReason.DAILY_LOSS_LIMIT.value)
    
    def test_get_risk_status_with_drawdown(self):
        """Test risk status report with drawdown."""
        self.risk_manager.update_drawdown_tracking(85000.0)
        
        status = self.risk_manager.get_risk_status()
        
        self.assertEqual(status['drawdown']['peak_value'], 100000.0)
        self.assertEqual(status['drawdown']['current_value'], 85000.0)
        self.assertEqual(status['drawdown']['current_drawdown_percent'], 15.0)


class TestDailyMetricsReset(unittest.TestCase):
    """Test daily metrics reset functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        risk_config = RiskManagementConfig(
            max_daily_loss=10000.0,
            max_position_size_percent=2.0,
            max_positions_per_instrument=1,
            stop_loss_percent=2.0,
            target_profit_percent=4.0,
            emergency_stop_enabled=True
        )
        portfolio_config = PortfolioConfig(
            initial_capital=100000.0,
            currency="INR",
            brokerage_per_trade=20.0,
            tax_rate=0.15
        )
        self.risk_manager = RiskManagerService(risk_config, portfolio_config)
    
    def test_reset_daily_metrics(self):
        """Test manual reset of daily metrics."""
        self.risk_manager.update_daily_pnl(-5000.0)
        self.risk_manager.update_daily_pnl(1000.0)
        
        metrics_before = self.risk_manager.get_daily_metrics()
        self.assertEqual(metrics_before['daily_pnl'], -4000.0)
        self.assertEqual(metrics_before['daily_trades'], 2)
        
        self.risk_manager.reset_daily_metrics()
        
        metrics_after = self.risk_manager.get_daily_metrics()
        self.assertEqual(metrics_after['daily_pnl'], 0.0)
        self.assertEqual(metrics_after['daily_trades'], 0)
        self.assertEqual(metrics_after['date'], date.today().isoformat())


if __name__ == '__main__':
    unittest.main()
