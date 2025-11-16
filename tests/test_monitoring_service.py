"""
Tests for the monitoring service.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from kite_auto_trading.services.monitoring_service import (
    MonitoringService,
    Alert,
    AlertType,
    AlertSeverity,
    NotificationChannel,
    SystemHealthMetrics,
    PerformanceSnapshot,
)
from kite_auto_trading.services.portfolio_metrics import (
    PortfolioMetricsCalculator,
    PerformanceMetrics,
    RiskMetrics,
)


@pytest.fixture
def mock_metrics_calculator():
    """Create mock metrics calculator."""
    calculator = Mock(spec=PortfolioMetricsCalculator)
    
    # Mock portfolio
    calculator.portfolio = Mock()
    calculator.portfolio.get_portfolio_summary.return_value = {
        'portfolio_value': 100000.0,
        'total_pnl': 5000.0,
        'total_return_pct': 5.0,
        'realized_pnl': 3000.0,
        'unrealized_pnl': 2000.0,
        'num_positions': 3,
        'total_trades': 10,
    }
    
    # Mock performance metrics
    calculator.calculate_performance_metrics.return_value = PerformanceMetrics(
        total_return=5000.0,
        total_return_pct=5.0,
        annualized_return=15.0,
        sharpe_ratio=1.5,
        sortino_ratio=1.8,
        max_drawdown=2000.0,
        max_drawdown_pct=2.0,
        current_drawdown=500.0,
        current_drawdown_pct=0.5,
        win_rate=60.0,
        profit_factor=2.0,
        average_win=800.0,
        average_loss=400.0,
        largest_win=2000.0,
        largest_loss=1000.0,
        total_trades=10,
        winning_trades=6,
        losing_trades=4,
        average_trade_duration=4.5,
        volatility=15.0,
        calmar_ratio=7.5
    )
    
    # Mock risk alerts
    calculator.check_risk_alerts.return_value = []
    
    return calculator


@pytest.fixture
def monitoring_service(mock_metrics_calculator):
    """Create monitoring service instance."""
    return MonitoringService(
        metrics_calculator=mock_metrics_calculator,
        metrics_update_interval=1,  # Short interval for testing
        health_check_interval=1
    )


class TestMonitoringService:
    """Test MonitoringService class."""
    
    def test_initialization(self, monitoring_service):
        """Test monitoring service initialization."""
        assert monitoring_service is not None
        assert not monitoring_service._is_monitoring
        assert len(monitoring_service._alerts) == 0
        assert len(monitoring_service._performance_snapshots) == 0
    
    def test_alert_thresholds(self, monitoring_service):
        """Test default alert thresholds."""
        assert monitoring_service.alert_thresholds['max_drawdown_pct'] == 10.0
        assert monitoring_service.alert_thresholds['max_leverage'] == 2.0
        assert monitoring_service.alert_thresholds['max_concentration_pct'] == 20.0
        assert monitoring_service.alert_thresholds['max_daily_loss_pct'] == 5.0
    
    def test_custom_alert_thresholds(self, mock_metrics_calculator):
        """Test custom alert thresholds."""
        custom_thresholds = {
            'max_drawdown_pct': 15.0,
            'max_leverage': 3.0,
        }
        
        service = MonitoringService(
            metrics_calculator=mock_metrics_calculator,
            alert_thresholds=custom_thresholds
        )
        
        assert service.alert_thresholds['max_drawdown_pct'] == 15.0
        assert service.alert_thresholds['max_leverage'] == 3.0
    
    def test_update_performance_metrics(self, monitoring_service):
        """Test performance metrics update."""
        monitoring_service._update_performance_metrics()
        
        assert len(monitoring_service._performance_snapshots) == 1
        snapshot = monitoring_service._performance_snapshots[0]
        
        assert isinstance(snapshot, PerformanceSnapshot)
        assert snapshot.portfolio_value == 100000.0
        assert snapshot.total_pnl == 5000.0
        assert snapshot.win_rate == 60.0
    
    def test_get_current_performance(self, monitoring_service):
        """Test getting current performance."""
        # Initially no performance data
        assert monitoring_service.get_current_performance() is None
        
        # Update metrics
        monitoring_service._update_performance_metrics()
        
        # Now should have performance data
        perf = monitoring_service.get_current_performance()
        assert perf is not None
        assert perf.portfolio_value == 100000.0
    
    def test_get_performance_history(self, monitoring_service):
        """Test getting performance history."""
        # Add multiple snapshots
        for _ in range(5):
            monitoring_service._update_performance_metrics()
            time.sleep(0.01)
        
        history = monitoring_service.get_performance_history()
        assert len(history) == 5
    
    def test_get_performance_history_with_time_filter(self, monitoring_service):
        """Test getting performance history with time filters."""
        now = datetime.now()
        
        # Add snapshots
        for i in range(5):
            monitoring_service._update_performance_metrics()
            time.sleep(0.01)
        
        # Filter by start time
        start_time = now + timedelta(seconds=0.02)
        history = monitoring_service.get_performance_history(start_time=start_time)
        assert len(history) < 5
    
    def test_update_system_health(self, monitoring_service):
        """Test system health update."""
        monitoring_service._update_system_health()
        
        assert len(monitoring_service._health_metrics) == 1
        health = monitoring_service._health_metrics[0]
        
        assert isinstance(health, SystemHealthMetrics)
        assert health.is_healthy
        assert health.health_score > 0
    
    def test_get_system_health(self, monitoring_service):
        """Test getting system health."""
        # Initially no health data
        assert monitoring_service.get_system_health() is None
        
        # Update health
        monitoring_service._update_system_health()
        
        # Now should have health data
        health = monitoring_service.get_system_health()
        assert health is not None
        assert health.is_healthy
    
    def test_calculate_health_score(self, monitoring_service):
        """Test health score calculation."""
        # Perfect health
        score = monitoring_service._calculate_health_score(100, 100, 100)
        assert score == 100.0
        
        # High latency
        score = monitoring_service._calculate_health_score(2000, 100, 100)
        assert score < 100.0
        
        # With errors
        monitoring_service._error_count = 5
        score = monitoring_service._calculate_health_score(100, 100, 100)
        assert score < 100.0
    
    def test_record_api_latency(self, monitoring_service):
        """Test recording API latency."""
        monitoring_service.record_api_latency(500.0)
        
        assert len(monitoring_service._api_latencies) == 1
        assert monitoring_service._api_latencies[0] == 500.0
    
    def test_record_high_api_latency_creates_alert(self, monitoring_service):
        """Test that high API latency creates an alert."""
        # Record high latency
        monitoring_service.record_api_latency(2000.0)
        
        # Should create an alert
        assert len(monitoring_service._alerts) == 1
        alert = monitoring_service._alerts[0]
        assert alert.alert_type == AlertType.PERFORMANCE_DEGRADATION
        assert alert.severity == AlertSeverity.MEDIUM
    
    def test_record_data_feed_latency(self, monitoring_service):
        """Test recording data feed latency."""
        monitoring_service.record_data_feed_latency(300.0)
        
        assert len(monitoring_service._data_feed_latencies) == 1
        assert monitoring_service._data_feed_latencies[0] == 300.0
    
    def test_record_order_processing_latency(self, monitoring_service):
        """Test recording order processing latency."""
        monitoring_service.record_order_processing_latency(200.0)
        
        assert len(monitoring_service._order_processing_latencies) == 1
        assert monitoring_service._order_processing_latencies[0] == 200.0
    
    def test_create_alert(self, monitoring_service):
        """Test alert creation."""
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Test alert",
            {'value': 15.0, 'threshold': 10.0}
        )
        
        assert len(monitoring_service._alerts) == 1
        alert = monitoring_service._alerts[0]
        
        assert alert.alert_type == AlertType.DRAWDOWN_BREACH
        assert alert.severity == AlertSeverity.HIGH
        assert alert.message == "Test alert"
        assert alert.details['value'] == 15.0
        assert not alert.acknowledged
    
    def test_get_active_alerts(self, monitoring_service):
        """Test getting active alerts."""
        # Create multiple alerts
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Alert 1"
        )
        monitoring_service._create_alert(
            AlertType.LEVERAGE_BREACH,
            AlertSeverity.MEDIUM,
            "Alert 2"
        )
        
        # All should be active
        active = monitoring_service.get_active_alerts()
        assert len(active) == 2
        
        # Acknowledge one
        monitoring_service._alerts[0].acknowledged = True
        
        # Should have one active
        active = monitoring_service.get_active_alerts()
        assert len(active) == 1
    
    def test_get_active_alerts_with_severity_filter(self, monitoring_service):
        """Test getting active alerts with severity filter."""
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "High alert"
        )
        monitoring_service._create_alert(
            AlertType.LEVERAGE_BREACH,
            AlertSeverity.MEDIUM,
            "Medium alert"
        )
        
        high_alerts = monitoring_service.get_active_alerts(severity=AlertSeverity.HIGH)
        assert len(high_alerts) == 1
        assert high_alerts[0].severity == AlertSeverity.HIGH
    
    def test_acknowledge_alert(self, monitoring_service):
        """Test acknowledging an alert."""
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Test alert"
        )
        
        alert = monitoring_service._alerts[0]
        assert not alert.acknowledged
        
        monitoring_service.acknowledge_alert(alert)
        assert alert.acknowledged
    
    def test_acknowledge_all_alerts(self, monitoring_service):
        """Test acknowledging all alerts."""
        # Create multiple alerts
        for i in range(3):
            monitoring_service._create_alert(
                AlertType.DRAWDOWN_BREACH,
                AlertSeverity.HIGH,
                f"Alert {i}"
            )
        
        # All should be unacknowledged
        assert all(not a.acknowledged for a in monitoring_service._alerts)
        
        # Acknowledge all
        monitoring_service.acknowledge_all_alerts()
        
        # All should be acknowledged
        assert all(a.acknowledged for a in monitoring_service._alerts)
    
    def test_clear_acknowledged_alerts(self, monitoring_service):
        """Test clearing acknowledged alerts."""
        # Create and acknowledge some alerts
        for i in range(3):
            monitoring_service._create_alert(
                AlertType.DRAWDOWN_BREACH,
                AlertSeverity.HIGH,
                f"Alert {i}"
            )
        
        monitoring_service._alerts[0].acknowledged = True
        monitoring_service._alerts[1].acknowledged = True
        
        assert len(monitoring_service._alerts) == 3
        
        # Clear acknowledged
        monitoring_service.clear_acknowledged_alerts()
        
        # Should have one remaining
        assert len(monitoring_service._alerts) == 1
        assert not monitoring_service._alerts[0].acknowledged
    
    def test_get_alert_history(self, monitoring_service):
        """Test getting alert history."""
        # Create alerts
        for i in range(5):
            monitoring_service._create_alert(
                AlertType.DRAWDOWN_BREACH,
                AlertSeverity.HIGH,
                f"Alert {i}"
            )
            time.sleep(0.01)
        
        history = monitoring_service.get_alert_history()
        assert len(history) == 5
    
    def test_get_alert_history_with_filters(self, monitoring_service):
        """Test getting alert history with filters."""
        now = datetime.now()
        
        # Create different types of alerts
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Drawdown alert"
        )
        time.sleep(0.01)
        monitoring_service._create_alert(
            AlertType.LEVERAGE_BREACH,
            AlertSeverity.MEDIUM,
            "Leverage alert"
        )
        
        # Filter by type
        drawdown_alerts = monitoring_service.get_alert_history(
            alert_type=AlertType.DRAWDOWN_BREACH
        )
        assert len(drawdown_alerts) == 1
        assert drawdown_alerts[0].alert_type == AlertType.DRAWDOWN_BREACH
    
    def test_check_alerts_with_risk_breaches(self, monitoring_service, mock_metrics_calculator):
        """Test alert checking with risk breaches."""
        # Mock risk alerts
        mock_metrics_calculator.check_risk_alerts.return_value = [
            {
                'type': 'DRAWDOWN_BREACH',
                'severity': 'HIGH',
                'message': 'Drawdown exceeded',
                'value': 15.0,
                'threshold': 10.0
            }
        ]
        
        monitoring_service._check_alerts()
        
        # Should create an alert
        assert len(monitoring_service._alerts) == 1
        alert = monitoring_service._alerts[0]
        assert alert.alert_type == AlertType.DRAWDOWN_BREACH
        assert alert.severity == AlertSeverity.HIGH
    
    def test_notification_channels(self, monitoring_service):
        """Test notification channels."""
        assert NotificationChannel.LOG in monitoring_service.notification_channels
        assert NotificationChannel.CONSOLE in monitoring_service.notification_channels
    
    def test_register_notification_callback(self, monitoring_service):
        """Test registering notification callback."""
        callback_called = []
        
        def custom_callback(alert: Alert):
            callback_called.append(alert)
        
        monitoring_service.register_notification_callback(
            NotificationChannel.EMAIL,
            custom_callback
        )
        
        # Add EMAIL to channels
        monitoring_service.notification_channels.append(NotificationChannel.EMAIL)
        
        # Create alert
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Test alert"
        )
        
        # Callback should be called
        assert len(callback_called) == 1
        assert callback_called[0].message == "Test alert"
    
    def test_generate_monitoring_report(self, monitoring_service):
        """Test generating monitoring report."""
        # Update metrics
        monitoring_service._update_performance_metrics()
        monitoring_service._update_system_health()
        
        # Create some alerts
        monitoring_service._create_alert(
            AlertType.DRAWDOWN_BREACH,
            AlertSeverity.HIGH,
            "Test alert"
        )
        
        # Generate report
        report = monitoring_service.generate_monitoring_report()
        
        assert 'timestamp' in report
        assert 'performance' in report
        assert 'system_health' in report
        assert 'alerts' in report
        assert 'thresholds' in report
        
        assert report['performance']['portfolio_value'] == 100000.0
        assert report['system_health']['is_healthy']
        assert report['alerts']['active_count'] == 1
    
    def test_start_stop_monitoring(self, monitoring_service):
        """Test starting and stopping monitoring."""
        assert not monitoring_service._is_monitoring
        
        # Start monitoring
        monitoring_service.start_monitoring()
        assert monitoring_service._is_monitoring
        assert monitoring_service._monitor_thread is not None
        assert monitoring_service._health_thread is not None
        
        # Give threads time to start
        time.sleep(0.1)
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
        assert not monitoring_service._is_monitoring
    
    def test_monitoring_loop_updates_metrics(self, monitoring_service):
        """Test that monitoring loop updates metrics."""
        # Start monitoring
        monitoring_service.start_monitoring()
        
        # Wait for updates
        time.sleep(2)
        
        # Should have performance snapshots
        assert len(monitoring_service._performance_snapshots) > 0
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
    
    def test_health_check_loop_updates_health(self, monitoring_service):
        """Test that health check loop updates health."""
        # Start monitoring
        monitoring_service.start_monitoring()
        
        # Wait for updates
        time.sleep(2)
        
        # Should have health metrics
        assert len(monitoring_service._health_metrics) > 0
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
    
    def test_performance_degradation_alert(self, monitoring_service):
        """Test performance degradation alert."""
        # Set low health score threshold
        monitoring_service.alert_thresholds['min_health_score'] = 90.0
        
        # Add errors to lower health score
        monitoring_service._error_count = 10
        
        # Update health
        monitoring_service._update_system_health()
        
        # Should create alert
        alerts = [a for a in monitoring_service._alerts 
                 if a.alert_type == AlertType.PERFORMANCE_DEGRADATION]
        assert len(alerts) > 0
    
    def test_record_error(self, monitoring_service):
        """Test recording errors."""
        initial_count = monitoring_service._error_count
        
        monitoring_service._record_error("test_component", "Test error")
        
        assert monitoring_service._error_count == initial_count + 1
    
    def test_record_warning(self, monitoring_service):
        """Test recording warnings."""
        initial_count = monitoring_service._warning_count
        
        monitoring_service.record_warning()
        
        assert monitoring_service._warning_count == initial_count + 1


class TestAlertDataStructure:
    """Test Alert data structure."""
    
    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            alert_type=AlertType.DRAWDOWN_BREACH,
            severity=AlertSeverity.HIGH,
            message="Test alert",
            timestamp=datetime.now(),
            details={'value': 15.0}
        )
        
        assert alert.alert_type == AlertType.DRAWDOWN_BREACH
        assert alert.severity == AlertSeverity.HIGH
        assert alert.message == "Test alert"
        assert not alert.acknowledged
        assert alert.details['value'] == 15.0


class TestSystemHealthMetrics:
    """Test SystemHealthMetrics data structure."""
    
    def test_health_metrics_creation(self):
        """Test creating health metrics."""
        metrics = SystemHealthMetrics(
            timestamp=datetime.now(),
            cpu_usage=50.0,
            memory_usage=60.0,
            api_latency_ms=100.0,
            data_feed_latency_ms=50.0,
            order_processing_latency_ms=75.0,
            active_connections=2,
            error_count=0,
            warning_count=1,
            is_healthy=True,
            health_score=95.0
        )
        
        assert metrics.cpu_usage == 50.0
        assert metrics.is_healthy
        assert metrics.health_score == 95.0


class TestPerformanceSnapshot:
    """Test PerformanceSnapshot data structure."""
    
    def test_performance_snapshot_creation(self):
        """Test creating performance snapshot."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            portfolio_value=100000.0,
            total_pnl=5000.0,
            total_pnl_pct=5.0,
            realized_pnl=3000.0,
            unrealized_pnl=2000.0,
            num_positions=3,
            num_trades=10,
            win_rate=60.0,
            sharpe_ratio=1.5,
            max_drawdown_pct=2.0,
            current_drawdown_pct=0.5
        )
        
        assert snapshot.portfolio_value == 100000.0
        assert snapshot.total_pnl == 5000.0
        assert snapshot.win_rate == 60.0
