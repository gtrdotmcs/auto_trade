"""
Performance monitoring and alerting service for the Kite Auto-Trading application.

This module provides real-time performance metrics tracking, notification system for
critical errors and alerts, and system health monitoring capabilities.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from collections import deque
import threading

from kite_auto_trading.services.portfolio_metrics import (
    PortfolioMetricsCalculator,
    PerformanceMetrics,
    RiskMetrics,
)


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Types of alerts."""
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    LEVERAGE_BREACH = "LEVERAGE_BREACH"
    CONCENTRATION_BREACH = "CONCENTRATION_BREACH"
    DAILY_LOSS_BREACH = "DAILY_LOSS_BREACH"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    API_ERROR = "API_ERROR"
    STRATEGY_ERROR = "STRATEGY_ERROR"
    RISK_VIOLATION = "RISK_VIOLATION"
    CONNECTION_LOST = "CONNECTION_LOST"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"


@dataclass
class Alert:
    """Alert data structure."""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class SystemHealthMetrics:
    """System health metrics."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    api_latency_ms: float
    data_feed_latency_ms: float
    order_processing_latency_ms: float
    active_connections: int
    error_count: int
    warning_count: int
    is_healthy: bool
    health_score: float  # 0-100


@dataclass
class PerformanceSnapshot:
    """Real-time performance snapshot."""
    timestamp: datetime
    portfolio_value: float
    total_pnl: float
    total_pnl_pct: float
    realized_pnl: float
    unrealized_pnl: float
    num_positions: int
    num_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    current_drawdown_pct: float


class NotificationChannel(Enum):
    """Notification delivery channels."""
    LOG = "LOG"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"
    CONSOLE = "CONSOLE"


class MonitoringService:
    """
    Performance monitoring and alerting service.
    
    Features:
    - Real-time performance metrics tracking
    - Alert generation and notification
    - System health monitoring
    - Performance degradation detection
    - Configurable alert thresholds
    """
    
    def __init__(
        self,
        metrics_calculator: PortfolioMetricsCalculator,
        alert_thresholds: Optional[Dict[str, float]] = None,
        notification_channels: Optional[List[NotificationChannel]] = None,
        metrics_update_interval: int = 60,  # seconds
        health_check_interval: int = 30,  # seconds
    ):
        """
        Initialize MonitoringService.
        
        Args:
            metrics_calculator: PortfolioMetricsCalculator instance
            alert_thresholds: Dictionary of alert thresholds
            notification_channels: List of notification channels to use
            metrics_update_interval: Interval for metrics updates in seconds
            health_check_interval: Interval for health checks in seconds
        """
        self.metrics_calculator = metrics_calculator
        self.metrics_update_interval = metrics_update_interval
        self.health_check_interval = health_check_interval
        
        # Alert thresholds with defaults
        self.alert_thresholds = alert_thresholds or {
            'max_drawdown_pct': 10.0,
            'max_leverage': 2.0,
            'max_concentration_pct': 20.0,
            'max_daily_loss_pct': 5.0,
            'min_health_score': 70.0,
            'max_api_latency_ms': 1000.0,
            'max_error_rate': 0.05,  # 5% error rate
        }
        
        # Notification channels
        self.notification_channels = notification_channels or [
            NotificationChannel.LOG,
            NotificationChannel.CONSOLE
        ]
        
        # Alert storage
        self._alerts: List[Alert] = []
        self._alert_history: deque = deque(maxlen=1000)
        
        # Performance snapshots
        self._performance_snapshots: deque = deque(maxlen=1000)
        
        # System health tracking
        self._health_metrics: deque = deque(maxlen=100)
        self._error_count = 0
        self._warning_count = 0
        self._api_latencies: deque = deque(maxlen=100)
        self._data_feed_latencies: deque = deque(maxlen=100)
        self._order_processing_latencies: deque = deque(maxlen=100)
        
        # Notification callbacks
        self._notification_callbacks: Dict[NotificationChannel, Callable] = {}
        
        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        
        logger.info("MonitoringService initialized")

    
    def start_monitoring(self):
        """Start real-time monitoring."""
        if self._is_monitoring:
            logger.warning("Monitoring already started")
            return
        
        self._is_monitoring = True
        
        # Start metrics monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        
        # Start health check thread
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self._health_thread.start()
        
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring."""
        self._is_monitoring = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        if self._health_thread:
            self._health_thread.join(timeout=5)
        
        logger.info("Monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._is_monitoring:
            try:
                # Update performance metrics
                self._update_performance_metrics()
                
                # Check for alerts
                self._check_alerts()
                
                # Sleep until next update
                time.sleep(self.metrics_update_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                self._record_error("monitoring_loop", str(e))
    
    def _health_check_loop(self):
        """Health check loop."""
        while self._is_monitoring:
            try:
                # Update system health
                self._update_system_health()
                
                # Sleep until next check
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                self._record_error("health_check_loop", str(e))

    
    def _update_performance_metrics(self):
        """Update real-time performance metrics."""
        try:
            # Get current performance metrics
            perf_metrics = self.metrics_calculator.calculate_performance_metrics()
            portfolio_summary = self.metrics_calculator.portfolio.get_portfolio_summary()
            
            # Create performance snapshot
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now(),
                portfolio_value=portfolio_summary['portfolio_value'],
                total_pnl=portfolio_summary['total_pnl'],
                total_pnl_pct=portfolio_summary['total_return_pct'],
                realized_pnl=portfolio_summary['realized_pnl'],
                unrealized_pnl=portfolio_summary['unrealized_pnl'],
                num_positions=portfolio_summary['num_positions'],
                num_trades=portfolio_summary['total_trades'],
                win_rate=perf_metrics.win_rate,
                sharpe_ratio=perf_metrics.sharpe_ratio,
                max_drawdown_pct=perf_metrics.max_drawdown_pct,
                current_drawdown_pct=perf_metrics.current_drawdown_pct
            )
            
            self._performance_snapshots.append(snapshot)
            
            logger.debug(f"Performance metrics updated: PnL={snapshot.total_pnl:.2f}, "
                        f"Positions={snapshot.num_positions}, WinRate={snapshot.win_rate:.2f}%")
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}", exc_info=True)
            self._record_error("performance_metrics", str(e))

    
    def _update_system_health(self):
        """Update system health metrics."""
        try:
            # Calculate average latencies
            avg_api_latency = (
                sum(self._api_latencies) / len(self._api_latencies)
                if self._api_latencies else 0.0
            )
            
            avg_data_feed_latency = (
                sum(self._data_feed_latencies) / len(self._data_feed_latencies)
                if self._data_feed_latencies else 0.0
            )
            
            avg_order_latency = (
                sum(self._order_processing_latencies) / len(self._order_processing_latencies)
                if self._order_processing_latencies else 0.0
            )
            
            # Calculate health score (0-100)
            health_score = self._calculate_health_score(
                avg_api_latency,
                avg_data_feed_latency,
                avg_order_latency
            )
            
            # Determine if system is healthy
            is_healthy = health_score >= self.alert_thresholds['min_health_score']
            
            # Create health metrics
            health_metrics = SystemHealthMetrics(
                timestamp=datetime.now(),
                cpu_usage=0.0,  # Placeholder - would use psutil in production
                memory_usage=0.0,  # Placeholder - would use psutil in production
                api_latency_ms=avg_api_latency,
                data_feed_latency_ms=avg_data_feed_latency,
                order_processing_latency_ms=avg_order_latency,
                active_connections=1,  # Placeholder
                error_count=self._error_count,
                warning_count=self._warning_count,
                is_healthy=is_healthy,
                health_score=health_score
            )
            
            self._health_metrics.append(health_metrics)
            
            # Check for performance degradation
            if not is_healthy:
                self._create_alert(
                    AlertType.PERFORMANCE_DEGRADATION,
                    AlertSeverity.HIGH,
                    f"System health score {health_score:.1f} below threshold "
                    f"{self.alert_thresholds['min_health_score']:.1f}",
                    {
                        'health_score': health_score,
                        'api_latency_ms': avg_api_latency,
                        'error_count': self._error_count
                    }
                )
            
            logger.debug(f"System health updated: Score={health_score:.1f}, "
                        f"Healthy={is_healthy}, Errors={self._error_count}")
            
        except Exception as e:
            logger.error(f"Error updating system health: {e}", exc_info=True)
            self._record_error("system_health", str(e))

    
    def _calculate_health_score(
        self,
        api_latency: float,
        data_feed_latency: float,
        order_latency: float
    ) -> float:
        """
        Calculate system health score (0-100).
        
        Args:
            api_latency: API latency in milliseconds
            data_feed_latency: Data feed latency in milliseconds
            order_latency: Order processing latency in milliseconds
            
        Returns:
            Health score between 0 and 100
        """
        score = 100.0
        
        # Deduct points for high latency
        max_latency = self.alert_thresholds['max_api_latency_ms']
        if api_latency > max_latency:
            score -= min(30, (api_latency - max_latency) / max_latency * 30)
        
        if data_feed_latency > max_latency:
            score -= min(20, (data_feed_latency - max_latency) / max_latency * 20)
        
        if order_latency > max_latency:
            score -= min(20, (order_latency - max_latency) / max_latency * 20)
        
        # Deduct points for errors
        if self._error_count > 0:
            score -= min(30, self._error_count * 5)
        
        return max(0.0, score)
    
    def _check_alerts(self):
        """Check for alert conditions."""
        try:
            # Check risk alerts from metrics calculator
            risk_alerts = self.metrics_calculator.check_risk_alerts(
                max_drawdown_pct=self.alert_thresholds['max_drawdown_pct'],
                max_leverage=self.alert_thresholds['max_leverage'],
                max_concentration_pct=self.alert_thresholds['max_concentration_pct'],
                max_daily_loss_pct=self.alert_thresholds['max_daily_loss_pct']
            )
            
            # Create alerts for each risk breach
            for risk_alert in risk_alerts:
                alert_type = AlertType[risk_alert['type']]
                severity = AlertSeverity[risk_alert['severity']]
                
                self._create_alert(
                    alert_type,
                    severity,
                    risk_alert['message'],
                    {
                        'value': risk_alert['value'],
                        'threshold': risk_alert['threshold']
                    }
                )
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}", exc_info=True)
            self._record_error("alert_check", str(e))

    
    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Create and send an alert.
        
        Args:
            alert_type: Type of alert
            severity: Alert severity
            message: Alert message
            details: Additional details
        """
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            details=details or {}
        )
        
        # Add to active alerts
        self._alerts.append(alert)
        self._alert_history.append(alert)
        
        # Send notifications
        self._send_notification(alert)
        
        logger.warning(f"Alert created: [{severity.value}] {alert_type.value} - {message}")
    
    def _send_notification(self, alert: Alert):
        """
        Send alert notification through configured channels.
        
        Args:
            alert: Alert to send
        """
        for channel in self.notification_channels:
            try:
                if channel == NotificationChannel.LOG:
                    self._send_log_notification(alert)
                elif channel == NotificationChannel.CONSOLE:
                    self._send_console_notification(alert)
                elif channel in self._notification_callbacks:
                    # Call custom callback
                    self._notification_callbacks[channel](alert)
                
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
    
    def _send_log_notification(self, alert: Alert):
        """Send notification to log file."""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        
        logger.log(
            log_level,
            f"ALERT [{alert.severity.value}] {alert.alert_type.value}: {alert.message}",
            extra={'alert_details': alert.details}
        )
    
    def _send_console_notification(self, alert: Alert):
        """Send notification to console."""
        severity_colors = {
            AlertSeverity.LOW: "",
            AlertSeverity.MEDIUM: "⚠️ ",
            AlertSeverity.HIGH: "🔴 ",
            AlertSeverity.CRITICAL: "🚨 "
        }
        
        prefix = severity_colors.get(alert.severity, "")
        print(f"\n{prefix}ALERT [{alert.severity.value}] {alert.alert_type.value}")
        print(f"  {alert.message}")
        print(f"  Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if alert.details:
            print(f"  Details: {alert.details}")
        print()

    
    def register_notification_callback(
        self,
        channel: NotificationChannel,
        callback: Callable[[Alert], None]
    ):
        """
        Register a custom notification callback.
        
        Args:
            channel: Notification channel
            callback: Callback function that takes an Alert
        """
        self._notification_callbacks[channel] = callback
        logger.info(f"Registered notification callback for {channel.value}")
    
    def record_api_latency(self, latency_ms: float):
        """Record API call latency."""
        self._api_latencies.append(latency_ms)
        
        if latency_ms > self.alert_thresholds['max_api_latency_ms']:
            self._create_alert(
                AlertType.PERFORMANCE_DEGRADATION,
                AlertSeverity.MEDIUM,
                f"High API latency: {latency_ms:.2f}ms",
                {'latency_ms': latency_ms}
            )
    
    def record_data_feed_latency(self, latency_ms: float):
        """Record data feed latency."""
        self._data_feed_latencies.append(latency_ms)
    
    def record_order_processing_latency(self, latency_ms: float):
        """Record order processing latency."""
        self._order_processing_latencies.append(latency_ms)
    
    def _record_error(self, component: str, error_message: str):
        """Record an error occurrence."""
        self._error_count += 1
        
        # Create error alert for critical components
        if component in ['api', 'strategy', 'risk_manager']:
            self._create_alert(
                AlertType.SYSTEM_ERROR,
                AlertSeverity.HIGH,
                f"Error in {component}: {error_message}",
                {'component': component, 'error': error_message}
            )
    
    def record_warning(self):
        """Record a warning occurrence."""
        self._warning_count += 1

    
    def get_current_performance(self) -> Optional[PerformanceSnapshot]:
        """
        Get current performance snapshot.
        
        Returns:
            Latest PerformanceSnapshot or None
        """
        return self._performance_snapshots[-1] if self._performance_snapshots else None
    
    def get_performance_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[PerformanceSnapshot]:
        """
        Get performance history with optional time filters.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of PerformanceSnapshot objects
        """
        snapshots = list(self._performance_snapshots)
        
        if start_time:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]
        
        if end_time:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]
        
        return snapshots
    
    def get_system_health(self) -> Optional[SystemHealthMetrics]:
        """
        Get current system health metrics.
        
        Returns:
            Latest SystemHealthMetrics or None
        """
        return self._health_metrics[-1] if self._health_metrics else None
    
    def get_health_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[SystemHealthMetrics]:
        """
        Get system health history with optional time filters.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of SystemHealthMetrics objects
        """
        metrics = list(self._health_metrics)
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return metrics

    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """
        Get active (unacknowledged) alerts.
        
        Args:
            severity: Optional severity filter
            
        Returns:
            List of active Alert objects
        """
        alerts = [a for a in self._alerts if not a.acknowledged]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts
    
    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alert_type: Optional[AlertType] = None
    ) -> List[Alert]:
        """
        Get alert history with optional filters.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            alert_type: Optional alert type filter
            
        Returns:
            List of Alert objects
        """
        alerts = list(self._alert_history)
        
        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]
        
        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]
        
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        return alerts
    
    def acknowledge_alert(self, alert: Alert):
        """
        Acknowledge an alert.
        
        Args:
            alert: Alert to acknowledge
        """
        alert.acknowledged = True
        logger.info(f"Alert acknowledged: {alert.alert_type.value}")
    
    def acknowledge_all_alerts(self):
        """Acknowledge all active alerts."""
        for alert in self._alerts:
            alert.acknowledged = True
        logger.info(f"All {len(self._alerts)} alerts acknowledged")
    
    def clear_acknowledged_alerts(self):
        """Remove acknowledged alerts from active list."""
        self._alerts = [a for a in self._alerts if not a.acknowledged]
        logger.info("Acknowledged alerts cleared")

    
    def generate_monitoring_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive monitoring report.
        
        Returns:
            Dictionary containing monitoring report
        """
        current_perf = self.get_current_performance()
        current_health = self.get_system_health()
        active_alerts = self.get_active_alerts()
        
        return {
            'timestamp': datetime.now(),
            'performance': {
                'portfolio_value': current_perf.portfolio_value if current_perf else 0.0,
                'total_pnl': current_perf.total_pnl if current_perf else 0.0,
                'total_pnl_pct': current_perf.total_pnl_pct if current_perf else 0.0,
                'win_rate': current_perf.win_rate if current_perf else 0.0,
                'sharpe_ratio': current_perf.sharpe_ratio if current_perf else 0.0,
                'max_drawdown_pct': current_perf.max_drawdown_pct if current_perf else 0.0,
                'current_drawdown_pct': current_perf.current_drawdown_pct if current_perf else 0.0,
            },
            'system_health': {
                'is_healthy': current_health.is_healthy if current_health else True,
                'health_score': current_health.health_score if current_health else 100.0,
                'api_latency_ms': current_health.api_latency_ms if current_health else 0.0,
                'error_count': current_health.error_count if current_health else 0,
                'warning_count': current_health.warning_count if current_health else 0,
            },
            'alerts': {
                'active_count': len(active_alerts),
                'critical_count': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                'high_count': len([a for a in active_alerts if a.severity == AlertSeverity.HIGH]),
                'medium_count': len([a for a in active_alerts if a.severity == AlertSeverity.MEDIUM]),
                'low_count': len([a for a in active_alerts if a.severity == AlertSeverity.LOW]),
                'recent_alerts': [
                    {
                        'type': a.alert_type.value,
                        'severity': a.severity.value,
                        'message': a.message,
                        'timestamp': a.timestamp.isoformat()
                    }
                    for a in active_alerts[:10]
                ]
            },
            'thresholds': self.alert_thresholds
        }
