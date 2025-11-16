"""
Main entry point for the Kite Auto Trading application.
"""

import logging
import sys
import signal
import argparse
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kite_auto_trading.config.logging_config import setup_logging, get_logger
from kite_auto_trading.config.constants import APP_NAME, APP_VERSION
from kite_auto_trading.config.loader import ConfigLoader
from kite_auto_trading.api.kite_client import KiteAPIClient
from kite_auto_trading.services.market_data_feed import MarketDataFeed
from kite_auto_trading.services.risk_manager import RiskManagerService
from kite_auto_trading.services.order_manager import OrderManager
from kite_auto_trading.services.portfolio_manager import PortfolioManager
from kite_auto_trading.services.monitoring_service import MonitoringService
from kite_auto_trading.strategies.base import StrategyManager
from kite_auto_trading.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from kite_auto_trading.strategies.rsi_mean_reversion import RSIMeanReversionStrategy
from kite_auto_trading.models.base import StrategyConfig


class KiteAutoTradingApp:
    """Main application class for Kite Auto Trading."""
    
    def __init__(self, config_path: str = "config.yaml", dry_run: bool = False, log_level: str = "INFO"):
        """Initialize the application."""
        self.config_path = config_path
        self.dry_run = dry_run
        self.log_level = log_level
        self.logger: Optional[logging.Logger] = None
        self.running = False
        
        # Component references
        self.config = None
        self.config_loader = None
        self.api_client = None
        self.market_data_feed = None
        self.risk_manager = None
        self.order_manager = None
        self.portfolio_manager = None
        self.strategy_manager = None
        self.monitoring_service = None
        
        # Threading
        self._main_loop_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._config_watch_thread: Optional[threading.Thread] = None
        self._config_reload_event = threading.Event()
        
        # Configuration hot-reload
        self._config_last_modified = None
        self._config_watch_enabled = False
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        if self.logger:
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        self._stop_event.set()
    
    def initialize(self):
        """Initialize all application components in proper order."""
        # Set up logging first
        self._setup_logging()
        
        self.logger.info(f"Initializing {APP_NAME} v{APP_VERSION}")
        self.logger.info(f"Configuration file: {self.config_path}")
        self.logger.info(f"Dry run mode: {self.dry_run}")
        self.logger.info(f"Log level: {self.log_level}")
        
        # Create necessary directories
        self._create_directories()
        
        # Initialize configuration manager
        self._initialize_configuration()
        
        # Initialize API client
        self._initialize_api_client()
        
        # Initialize portfolio manager
        self._initialize_portfolio_manager()
        
        # Initialize risk manager
        self._initialize_risk_manager()
        
        # Initialize order manager
        self._initialize_order_manager()
        
        # Initialize market data manager
        self._initialize_market_data_feed()
        
        # Initialize strategy engine
        self._initialize_strategy_manager()
        
        # Initialize monitoring service
        self._initialize_monitoring()
        
        self.logger.info("Application initialization completed successfully")
    
    def _setup_logging(self):
        """Set up logging configuration."""
        logging_config = {
            'level': self.log_level,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file_path': 'logs/trading.log',
            'max_file_size': '10MB',
            'backup_count': 5,
            'console_output': True
        }
        setup_logging(logging_config)
        self.logger = get_logger(__name__)
    
    def _create_directories(self):
        """Create necessary directories for the application."""
        directories = [
            "logs",
            "data",
            "strategies",
            "config"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {directory}")
    
    def _initialize_configuration(self):
        """Initialize configuration manager."""
        try:
            self.logger.info("Loading configuration...")
            self.config_loader = ConfigLoader(self.config_path)
            self.config = self.config_loader.load_config()
            
            # Track config file modification time
            config_file = Path(self.config_path)
            if config_file.exists():
                self._config_last_modified = config_file.stat().st_mtime
            
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _initialize_api_client(self):
        """Initialize Kite API client."""
        try:
            self.logger.info("Initializing API client...")
            self.api_client = KiteAPIClient(self.config.api)
            
            # Attempt auto-authentication with saved session
            if self.api_client.auto_authenticate():
                self.logger.info("Auto-authentication successful")
            else:
                self.logger.warning("Auto-authentication failed - manual authentication required")
                # In production, this would trigger the login flow
                # For now, we'll continue without authentication in dry-run mode
                if not self.dry_run:
                    raise Exception("Authentication required for live trading")
            
            self.logger.info("API client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize API client: {e}")
            if not self.dry_run:
                raise
    
    def _initialize_portfolio_manager(self):
        """Initialize portfolio manager."""
        try:
            self.logger.info("Initializing portfolio manager...")
            self.portfolio_manager = PortfolioManager(
                initial_capital=self.config.portfolio.initial_capital,
                commission_rate=self.config.portfolio.brokerage_per_trade / 10000,  # Convert to rate
                tax_rate=self.config.portfolio.tax_rate
            )
            self.logger.info("Portfolio manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize portfolio manager: {e}")
            raise
    
    def _initialize_risk_manager(self):
        """Initialize risk manager."""
        try:
            self.logger.info("Initializing risk manager...")
            self.risk_manager = RiskManagerService(
                risk_config=self.config.risk_management,
                portfolio_config=self.config.portfolio
            )
            
            # Register emergency stop callback
            self.risk_manager.register_emergency_stop_callback(self._handle_emergency_stop)
            
            self.logger.info("Risk manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize risk manager: {e}")
            raise
    
    def _initialize_order_manager(self):
        """Initialize order manager."""
        try:
            self.logger.info("Initializing order manager...")
            
            # Use API client as executor if not in dry-run mode
            executor = self.api_client if not self.dry_run else None
            
            self.order_manager = OrderManager(
                executor=executor,
                max_retries=self.config.api.max_retries,
                retry_delay=self.config.api.retry_delay,
                enable_queue_processing=True
            )
            
            # Register callbacks
            self.order_manager.register_callback(self._handle_order_update)
            self.order_manager.register_fill_callback(self._handle_fill_update)
            
            # Start execution monitoring
            self.order_manager.start_execution_monitoring()
            
            self.logger.info("Order manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize order manager: {e}")
            raise
    
    def _initialize_market_data_feed(self):
        """Initialize market data feed."""
        try:
            self.logger.info("Initializing market data feed...")
            self.market_data_feed = MarketDataFeed(
                api_client=self.api_client,
                buffer_size=self.config.market_data.buffer_size,
                reconnect_interval=self.config.market_data.reconnect_interval,
                max_reconnect_attempts=self.config.market_data.max_reconnect_attempts
            )
            
            # Register callbacks
            self.market_data_feed.register_callback('tick', self._handle_market_tick)
            self.market_data_feed.register_callback('connect', self._handle_market_connect)
            self.market_data_feed.register_callback('disconnect', self._handle_market_disconnect)
            self.market_data_feed.register_callback('error', self._handle_market_error)
            
            self.logger.info("Market data feed initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize market data feed: {e}")
            raise
    
    def _initialize_strategy_manager(self):
        """Initialize strategy manager and load strategies."""
        try:
            self.logger.info("Initializing strategy manager...")
            self.strategy_manager = StrategyManager()
            
            # Load and register strategies from configuration
            self._load_strategies()
            
            self.logger.info(f"Strategy manager initialized with {len(self.strategy_manager.strategies)} strategies")
        except Exception as e:
            self.logger.error(f"Failed to initialize strategy manager: {e}")
            raise
    
    def _load_strategies(self):
        """Load strategies from configuration."""
        # Example: Load Moving Average Crossover strategy
        ma_config = StrategyConfig(
            name="MA_Crossover",
            enabled=True,
            instruments=self.config.market_data.instruments or ["RELIANCE", "TCS"],
            entry_conditions={"fast_period": 10, "slow_period": 20},
            exit_conditions={"stop_loss_pct": 2.0, "target_pct": 4.0},
            risk_params=None,
            timeframe="5minute"
        )
        ma_strategy = MovingAverageCrossoverStrategy(ma_config)
        self.strategy_manager.register_strategy(ma_strategy)
        
        # Example: Load RSI Mean Reversion strategy
        rsi_config = StrategyConfig(
            name="RSI_MeanReversion",
            enabled=True,
            instruments=self.config.market_data.instruments or ["INFY", "WIPRO"],
            entry_conditions={"rsi_period": 14, "oversold": 30, "overbought": 70},
            exit_conditions={"stop_loss_pct": 2.0, "target_pct": 3.0},
            risk_params=None,
            timeframe="15minute"
        )
        rsi_strategy = RSIMeanReversionStrategy(rsi_config)
        self.strategy_manager.register_strategy(rsi_strategy)
        
        self.logger.info(f"Loaded {len(self.strategy_manager.strategies)} strategies")
    
    def _initialize_monitoring(self):
        """Initialize monitoring service."""
        try:
            self.logger.info("Initializing monitoring service...")
            
            # Create metrics calculator
            from kite_auto_trading.services.portfolio_metrics import PortfolioMetricsCalculator
            metrics_calculator = PortfolioMetricsCalculator(
                portfolio_manager=self.portfolio_manager,
                risk_free_rate=0.05,
                trading_days_per_year=252
            )
            
            # Initialize monitoring service
            self.monitoring_service = MonitoringService(
                metrics_calculator=metrics_calculator,
                alert_thresholds={
                    'max_drawdown_pct': self.config.monitoring.alert_thresholds.drawdown_percent,
                    'max_leverage': 2.0,
                    'max_concentration_pct': 20.0,
                    'max_daily_loss_pct': self.config.monitoring.alert_thresholds.daily_loss_percent,
                    'min_health_score': 70.0,
                    'max_api_latency_ms': 1000.0,
                    'max_error_rate': 0.05,
                },
                metrics_update_interval=self.config.monitoring.performance_metrics_interval,
                health_check_interval=self.config.monitoring.health_check_interval
            )
            
            # Start monitoring
            self.monitoring_service.start_monitoring()
            
            self.logger.info("Monitoring service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring service: {e}")
            raise
    
    def run(self):
        """Run the main application loop."""
        self.logger.info("Starting main application loop...")
        self.running = True
        
        if self.dry_run:
            self.logger.info("Running in DRY RUN mode - no real trades will be executed")
        
        try:
            # Connect to market data feed
            if not self.dry_run and self.api_client and self.api_client.is_authenticated():
                self._start_market_data()
            
            # Main application loop
            self.logger.info("Application is running. Press Ctrl+C to stop.")
            
            while self.running and not self._stop_event.is_set():
                try:
                    # Process market data and evaluate strategies
                    self._process_trading_cycle()
                    
                    # Update portfolio metrics
                    self._update_portfolio_metrics()
                    
                    # Check risk limits
                    self._check_risk_limits()
                    
                    # Sleep to control loop frequency (e.g., every 5 seconds)
                    time.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Error in trading cycle: {e}", exc_info=True)
                    time.sleep(5)  # Continue after error
                
        except Exception as e:
            self.logger.error(f"Fatal error in main application loop: {e}", exc_info=True)
            raise
    
    def _start_market_data(self):
        """Start market data feed."""
        try:
            self.logger.info("Starting market data feed...")
            
            # Connect to market data
            if self.market_data_feed.connect():
                # Subscribe to instruments from all strategies
                instruments = set()
                for strategy in self.strategy_manager.get_enabled_strategies():
                    instruments.update(strategy.config.instruments)
                
                if instruments:
                    # Convert instrument symbols to tokens (simplified - would need actual token lookup)
                    instrument_tokens = list(range(1, len(instruments) + 1))  # Placeholder
                    self.market_data_feed.subscribe_instruments(instrument_tokens)
                    self.logger.info(f"Subscribed to {len(instruments)} instruments")
            else:
                self.logger.warning("Failed to connect to market data feed")
                
        except Exception as e:
            self.logger.error(f"Error starting market data: {e}")
    
    def _process_trading_cycle(self):
        """Process one trading cycle - evaluate strategies and execute trades."""
        try:
            # Prepare market data for strategy evaluation
            market_data = {
                'positions': self.portfolio_manager.get_positions(),
                'portfolio_value': self.portfolio_manager.get_portfolio_value(),
                'cash_balance': self.portfolio_manager.get_cash_balance(),
                'timestamp': datetime.now()
            }
            
            # Evaluate all strategies
            signals = self.strategy_manager.evaluate_all_strategies(market_data)
            
            if signals:
                self.logger.info(f"Generated {len(signals)} trading signals")
                
                # Process each signal
                for signal in signals:
                    self._process_trading_signal(signal)
            
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}", exc_info=True)
    
    def _process_trading_signal(self, signal):
        """Process a trading signal and execute if valid."""
        try:
            # Get current price (simplified - would use actual market data)
            current_price = signal.price
            
            # Calculate position size
            available_funds = self.portfolio_manager.get_cash_balance()
            position_size_result = self.risk_manager.calculate_position_size(
                signal={'risk_percent': 2.0, 'stop_loss_percent': 2.0},
                current_price=current_price,
                account_balance=available_funds
            )
            
            # Create order from signal
            from kite_auto_trading.models.base import Order, TransactionType, OrderType
            from kite_auto_trading.models.signals import SignalType
            
            # Determine transaction type from signal
            if signal.signal_type in [SignalType.ENTRY_LONG, SignalType.EXIT_SHORT]:
                transaction_type = TransactionType.BUY
            else:
                transaction_type = TransactionType.SELL
            
            order = Order(
                instrument=signal.instrument,
                transaction_type=transaction_type,
                quantity=position_size_result.quantity,
                order_type=OrderType.MARKET,
                price=None,
                trigger_price=None,
                strategy_id=signal.strategy_name
            )
            
            # Validate order with risk manager
            validation_result = self.risk_manager.validate_order(
                order=order,
                current_price=current_price,
                available_funds=available_funds
            )
            
            if validation_result.is_valid:
                # Submit order
                if not self.dry_run:
                    order_id = self.order_manager.submit_order(order)
                    self.logger.info(f"Order submitted: {order_id} for signal {signal.reason}")
                else:
                    self.logger.info(f"DRY RUN: Would submit order for {signal.instrument}")
            else:
                self.logger.warning(f"Order validation failed: {validation_result.reason}")
                
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}", exc_info=True)
    
    def _update_portfolio_metrics(self):
        """Update portfolio metrics and tracking."""
        try:
            # Update portfolio value in risk manager
            portfolio_value = self.portfolio_manager.get_portfolio_value()
            self.risk_manager.update_portfolio_value(portfolio_value)
            
            # Update drawdown tracking
            self.risk_manager.update_drawdown_tracking(portfolio_value)
            
            # Create portfolio snapshot periodically
            # (In production, this would be time-based)
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {e}")
    
    def _check_risk_limits(self):
        """Check and enforce risk limits."""
        try:
            # Check all risk limits
            if not self.risk_manager.check_and_enforce_limits():
                self.logger.critical("Risk limits breached - emergency stop activated")
                # Emergency stop will be handled by callback
                
        except Exception as e:
            self.logger.error(f"Error checking risk limits: {e}")
    
    # Callback handlers
    
    def _handle_order_update(self, update):
        """Handle order status updates."""
        self.logger.info(f"Order update: {update.order_id} -> {update.status.value}")
    
    def _handle_fill_update(self, fill):
        """Handle order fill updates."""
        self.logger.info(f"Order fill: {fill.order_id} - {fill.quantity}@{fill.price}")
        
        # Update portfolio with trade
        trade_data = {
            'instrument': fill.order_id,  # Would need to lookup instrument from order
            'transaction_type': None,  # Would need from order
            'quantity': fill.quantity,
            'price': fill.price,
            'timestamp': fill.timestamp,
            'order_id': fill.order_id
        }
        # self.portfolio_manager.update_position(trade_data)
    
    def _handle_market_tick(self, tick):
        """Handle market data tick."""
        # Update portfolio with current prices
        instrument_token = tick.get('instrument_token')
        last_price = tick.get('last_price')
        
        if instrument_token and last_price:
            # Would need to map token to instrument symbol
            pass
    
    def _handle_market_connect(self):
        """Handle market data connection."""
        self.logger.info("Market data feed connected")
    
    def _handle_market_disconnect(self):
        """Handle market data disconnection."""
        self.logger.warning("Market data feed disconnected")
    
    def _handle_market_error(self, error):
        """Handle market data errors."""
        self.logger.error(f"Market data error: {error}")
    
    def _handle_emergency_stop(self, reason):
        """Handle emergency stop activation."""
        self.logger.critical(f"EMERGENCY STOP ACTIVATED: {reason.value}")
        
        # Cancel all pending orders
        if self.order_manager:
            pending_orders = self.order_manager.get_pending_orders()
            for order in pending_orders:
                try:
                    self.order_manager.cancel_order(order.order_id)
                except Exception as e:
                    self.logger.error(f"Failed to cancel order {order.order_id}: {e}")
        
        # Stop trading
        self.running = False
        self._stop_event.set()
    
    # Configuration Hot-Reloading
    
    def enable_config_hot_reload(self):
        """Enable configuration hot-reloading."""
        if self._config_watch_enabled:
            self.logger.warning("Config hot-reload already enabled")
            return
        
        self._config_watch_enabled = True
        self._config_watch_thread = threading.Thread(
            target=self._watch_config_file,
            daemon=True,
            name="ConfigWatcher"
        )
        self._config_watch_thread.start()
        self.logger.info("Configuration hot-reload enabled")
    
    def disable_config_hot_reload(self):
        """Disable configuration hot-reloading."""
        self._config_watch_enabled = False
        if self._config_watch_thread:
            self._config_watch_thread.join(timeout=5)
        self.logger.info("Configuration hot-reload disabled")
    
    def _watch_config_file(self):
        """Watch configuration file for changes."""
        self.logger.info("Config file watcher started")
        
        while self._config_watch_enabled and not self._stop_event.is_set():
            try:
                config_file = Path(self.config_path)
                if config_file.exists():
                    current_mtime = config_file.stat().st_mtime
                    
                    if self._config_last_modified and current_mtime > self._config_last_modified:
                        self.logger.info("Configuration file changed, reloading...")
                        self._reload_configuration()
                        self._config_last_modified = current_mtime
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error watching config file: {e}")
                time.sleep(5)
        
        self.logger.info("Config file watcher stopped")
    
    def _reload_configuration(self):
        """Reload configuration and apply changes."""
        try:
            # Load new configuration
            new_config = self.config_loader.reload_config()
            
            # Apply configuration changes
            self._apply_config_changes(self.config, new_config)
            
            # Update current config
            self.config = new_config
            
            self.logger.info("Configuration reloaded successfully")
            self._config_reload_event.set()
            
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
    
    def _apply_config_changes(self, old_config, new_config):
        """Apply configuration changes to running components."""
        try:
            # Update risk manager settings
            if old_config.risk_management != new_config.risk_management:
                self.logger.info("Updating risk management configuration...")
                self.risk_manager.risk_config = new_config.risk_management
            
            # Update strategy configurations
            if old_config.strategies != new_config.strategies:
                self.logger.info("Strategy configuration changed")
                # Strategy changes are handled by runtime strategy management
            
            # Update monitoring thresholds
            if old_config.monitoring != new_config.monitoring:
                self.logger.info("Updating monitoring configuration...")
                if self.monitoring_service:
                    self.monitoring_service.alert_thresholds = {
                        'max_drawdown_pct': new_config.monitoring.alert_thresholds.drawdown_percent,
                        'max_leverage': 2.0,
                        'max_concentration_pct': 20.0,
                        'max_daily_loss_pct': new_config.monitoring.alert_thresholds.daily_loss_percent,
                        'min_health_score': 70.0,
                        'max_api_latency_ms': 1000.0,
                        'max_error_rate': 0.05,
                    }
            
            self.logger.info("Configuration changes applied")
            
        except Exception as e:
            self.logger.error(f"Error applying config changes: {e}")
    
    # Runtime Strategy Management
    
    def enable_strategy(self, strategy_name: str) -> bool:
        """
        Enable a strategy at runtime.
        
        Args:
            strategy_name: Name of the strategy to enable
            
        Returns:
            True if successful, False otherwise
        """
        if not self.strategy_manager:
            self.logger.error("Strategy manager not initialized")
            return False
        
        success = self.strategy_manager.enable_strategy(strategy_name)
        if success:
            self.logger.info(f"Strategy enabled: {strategy_name}")
        else:
            self.logger.warning(f"Failed to enable strategy: {strategy_name}")
        
        return success
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """
        Disable a strategy at runtime.
        
        Args:
            strategy_name: Name of the strategy to disable
            
        Returns:
            True if successful, False otherwise
        """
        if not self.strategy_manager:
            self.logger.error("Strategy manager not initialized")
            return False
        
        success = self.strategy_manager.disable_strategy(strategy_name)
        if success:
            self.logger.info(f"Strategy disabled: {strategy_name}")
        else:
            self.logger.warning(f"Failed to disable strategy: {strategy_name}")
        
        return success
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """
        Get status of all strategies.
        
        Returns:
            Dictionary with strategy status information
        """
        if not self.strategy_manager:
            return {}
        
        return self.strategy_manager.get_strategy_stats()
    
    def list_strategies(self) -> List[str]:
        """
        List all registered strategies.
        
        Returns:
            List of strategy names
        """
        if not self.strategy_manager:
            return []
        
        return list(self.strategy_manager.strategies.keys())
    
    # Administrative Interface
    
    def get_application_status(self) -> Dict[str, Any]:
        """
        Get comprehensive application status.
        
        Returns:
            Dictionary with application status
        """
        status = {
            'running': self.running,
            'dry_run': self.dry_run,
            'config_path': self.config_path,
            'components': {
                'api_client': self.api_client is not None,
                'market_data_feed': self.market_data_feed is not None,
                'risk_manager': self.risk_manager is not None,
                'order_manager': self.order_manager is not None,
                'portfolio_manager': self.portfolio_manager is not None,
                'strategy_manager': self.strategy_manager is not None,
                'monitoring_service': self.monitoring_service is not None,
            },
            'strategies': self.get_strategy_status() if self.strategy_manager else {},
            'portfolio': self.portfolio_manager.get_portfolio_summary() if self.portfolio_manager else {},
            'risk': self.risk_manager.get_risk_status() if self.risk_manager else {},
        }
        
        # Add market data feed status
        if self.market_data_feed:
            status['market_data'] = self.market_data_feed.get_stats()
        
        # Add order manager stats
        if self.order_manager:
            status['orders'] = {
                'pending': len(self.order_manager.get_pending_orders()),
                'open': len(self.order_manager.get_open_orders()),
            }
        
        return status
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get current performance report.
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.monitoring_service:
            return {}
        
        return self.monitoring_service.generate_monitoring_report()
    
    def trigger_emergency_stop(self, reason: str = "Manual trigger"):
        """
        Manually trigger emergency stop.
        
        Args:
            reason: Reason for emergency stop
        """
        from kite_auto_trading.services.risk_manager import EmergencyStopReason
        
        self.logger.critical(f"Manual emergency stop triggered: {reason}")
        
        if self.risk_manager:
            self.risk_manager.trigger_emergency_stop(EmergencyStopReason.MANUAL_TRIGGER)
        else:
            # Fallback if risk manager not available
            self._handle_emergency_stop(EmergencyStopReason.MANUAL_TRIGGER)
    
    def clear_emergency_stop(self) -> bool:
        """
        Clear emergency stop and resume trading.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        if not self.risk_manager:
            self.logger.error("Risk manager not initialized")
            return False
        
        success = self.risk_manager.clear_emergency_stop()
        if success:
            self.logger.info("Emergency stop cleared, trading resumed")
            self.running = True
            self._stop_event.clear()
        else:
            self.logger.warning("No active emergency stop to clear")
        
        return success
    
    def shutdown(self):
        """Shutdown the application gracefully."""
        if self.logger:
            self.logger.info("Shutting down application...")
            
            try:
                # Stop config watcher
                if self._config_watch_enabled:
                    self.disable_config_hot_reload()
                
                # Stop monitoring service
                if self.monitoring_service:
                    self.monitoring_service.stop_monitoring()
                    self.logger.info("Monitoring service stopped")
                
                # Stop market data feed
                if self.market_data_feed:
                    self.market_data_feed.disconnect()
                    self.logger.info("Market data feed disconnected")
                
                # Stop order manager
                if self.order_manager:
                    self.order_manager.stop_queue_processing()
                    self.order_manager.stop_execution_monitoring()
                    self.logger.info("Order manager stopped")
                
                # Cancel pending orders
                if self.order_manager and not self.dry_run:
                    pending_orders = self.order_manager.get_pending_orders()
                    if pending_orders:
                        self.logger.info(f"Cancelling {len(pending_orders)} pending orders...")
                        for order in pending_orders:
                            try:
                                self.order_manager.cancel_order(order.order_id)
                            except Exception as e:
                                self.logger.error(f"Failed to cancel order: {e}")
                
                # Generate final portfolio report
                if self.portfolio_manager:
                    summary = self.portfolio_manager.get_portfolio_summary()
                    self.logger.info(f"Final Portfolio Summary:")
                    self.logger.info(f"  Total Value: {summary['total_value']:.2f}")
                    self.logger.info(f"  Total P&L: {summary['total_pnl']:.2f}")
                    self.logger.info(f"  Total Trades: {summary['total_trades']}")
                
                self.logger.info("Application shutdown completed successfully")
                
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}", exc_info=True)


def main(args: Optional[list] = None) -> int:
    """
    Main entry point for the application.
    
    Args:
        args: Command line arguments (optional, defaults to sys.argv)
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description="Kite Auto-Trading Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m kite_auto_trading.main --config config.yaml
  python -m kite_auto_trading.main --dry-run --config test_config.yaml
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in simulation mode without executing real trades"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}"
    )
    
    parsed_args = parser.parse_args(args)
    
    app = KiteAutoTradingApp(
        config_path=parsed_args.config,
        dry_run=parsed_args.dry_run,
        log_level=parsed_args.log_level
    )
    
    try:
        app.initialize()
        app.run()
        return 0
        
    except KeyboardInterrupt:
        if app.logger:
            app.logger.info("Received keyboard interrupt")
        return 0
        
    except Exception as e:
        if app.logger:
            app.logger.error(f"Application error: {e}", exc_info=True)
        else:
            print(f"Application error: {e}")
        return 1
        
    finally:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())