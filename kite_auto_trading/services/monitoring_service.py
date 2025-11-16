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
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
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
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class SystemHealthMetrics:
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
    health_score: float


@dataclass
class PerformanceSnapshot:
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
    LOG = "LOG"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"
    CONSOLE = "CONSOLE"


class MonitoringService:
    def __init__(
        self,
        metrics_calculator: PortfolioMetricsCalculator,
        alert_thresholds: Optional[Dict[str, float]] = None,
        notification_channels: Optional[List[NotificationChannel]] = None,
        metrics_update_interval: int = 60,
        health_check_interval: int = 30,
    ):
        self.metrics_calculator = metrics_calculator
        self.metrics_update_interval = metrics_update_interval
        self.health_check_interval = health_check_interval
        
        self.alert_thresholds = alert_thresholds or {
            'max_drawdown_pct': 10.0,
            'max_leverage': 2.0,
            'max_concentration_pct': 20.0,
            'max_daily_loss_pct': 5.0,
            'min_health_score': 70.0,
            'max_api_latency_ms': 1000.0,
            'max_error_rate': 0.05,
        }
        
        self.notification_channels = notification_channels or [
            NotificationChannel.LOG,
            NotificationChannel.CONSOLE
        ]
        
        self._alerts: List[Alert] = []
        self._alert_history: deque = deque(maxlen=1000)
        self._performance_snapshots: deque = deque(maxlen=1000)
        self._health_metrics: deque = deque(maxlen=100)
        self._error_count = 0
        self._warning_count = 0
        self._api_latencies: deque = deque(maxlen=100)
        self._data_feed_latencies: deque = deque(maxlen=100)
        self._order_processing_latencies: deque = deque(maxlen=100)
        self._notification_callbacks: Dict[NotificationChannel, Callable] = {}
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        
        logger.info("MonitoringService initialized")

    
    def start_monitoring(self):
        if self._is_monitoring:
            logger.warning("Monitoring already started")
            return
        
        self._is_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        self._is_monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        if self._health_thread:
            self._health_thread.join(timeout=5)
        logger.info("Monitoring stopped")
    
    def _monitor_loop(self):
        while self._is_monitoring:
            try:
                self._update_performance_metrics()
                self._check_alerts()
                time.sleep(self.metrics_update_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                self._record_error("monitoring_loop", str(e))
    
    def _health_check_loop(self):
        while self._is_monitoring:
            try:
                self._update_system_health()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                self._record_error("health_check_loop", str(e))
    
    def _update_performance_metrics(self):
        try:
            perf_metrics = self.metrics_calculator.calculate_performance_metrics()
            portfolio_summary = self.metrics_calculator.portfolio.get_portfolio_summary()
            
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
            logger.debug(f"Performance metrics updated: PnL={snapshot.total_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}", exc_info=True)
            self._record_error("performance_metrics", str(e))
    
    def _update_system_health(self):
        try:
            avg_api_latency = sum(self._api_latencies) / len(self._api_latencies) if self._api_latencies else 0.0
            avg_data_feed_latency = sum(self._data_feed_latencies) / len(self._data_feed_latencies) if self._data_feed_latencies else 0.0
            avg_order_latency = sum(self._order_processing_latencies) / len(self._order_processing_latencies) if self._order_processing_latencies else 0.0
            
            health_score = self._calculate_health_score(avg_api_latency, avg_data_feed_latency, avg_order_latency)
            is_healthy = health_score >= self.alert_thresholds['min_health_score']
            
            health_metrics = SystemHealthMetrics(
                timestamp=datetime.now(),
                cpu_usage=0.0,
                memory_usage=0.0,
                api_latency_ms=avg_api_latency,
                data_feed_latency_ms=avg_data_feed_latency,
                order_processing_latency_ms=avg_order_latency,
                active_connections=1,
                error_count=self._error_count,
                warning_count=self._warning_count,
                is_healthy=is_healthy,
                health_score=health_score
            )
            
            self._health_metrics.append(health_metrics)
            
            if not is_healthy:
                self._create_alert(
                    AlertType.PERFORMANCE_DEGRADATION,
                    AlertSeverity.HIGH,
                    f"System health score {health_score:.1f} below threshold {self.alert_thresholds['min_health_score']:.1f}",
                    {'health_score': health_score, 'api_latency_ms': avg_api_latency, 'error_count': self._error_count}
                )
            
            logger.debug(f"System health updated: Score={health_score:.1f}, Healthy={is_healthy}")
            
        except Exception as e:
            logger.error(f"Error updating system health: {e}", exc_info=True)
            self._record_error("system_health", str(e))
    
    def _calculate_health_score(self, api_latency: float, data_feed_latency: float, order_latency: float) -> float:
        score = 100.0
        max_latency = self.alert_thresholds['max_api_latency_ms']
        if api_latency > max_latency:
            score -= min(30, (api_latency - max_latency) / max_latency * 30)
        if data_feed_latency > max_latency:
            score -= min(20, (data_feed_latency - max_latency) / max_latency * 20)
        if order_latency > max_latency:
            score -= min(20, (order_latency - max_latency) / max_latency * 20)
        if self._error_count > 0:
            score -= min(30, self._error_count * 5)
        return max(0.0, score)
    
    def _check_alerts(self):
        try:
            risk_alerts = self.metrics_calculator.check_risk_alerts(
                max_drawdown_pct=self.alert_thresholds['max_drawdown_pct'],
                max_leverage=self.alert_thresholds['max_leverage'],
                max_concentration_pct=self.alert_thresholds['max_concentration_pct'],
                max_daily_loss_pct=self.alert_thresholds['max_daily_loss_pct']
            )
            
            for risk_alert in risk_alerts:
                alert_type = AlertType[risk_alert['type']]
                severity = AlertSeverity[risk_alert['severity']]
                self._create_alert(alert_type, severity, risk_alert['message'], {'value': risk_alert['value'], 'threshold': risk_alert['threshold']})
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}", exc_info=True)
            self._record_error("alert_check", str(e))
    
    def _create_alert(self, alert_type: AlertType, severity: AlertSeverity, message: str, details: Optional[Dict[str, Any]] = None):
        alert = Alert(alert_type=alert_type, severity=severity, message=message, timestamp=datetime.now(), details=details or {})
        self._alerts.append(alert)
        self._alert_history.append(alert)
        self._send_notification(alert)
        logger.warning(f"Alert created: [{severity.value}] {alert_type.value} - {message}")
    
    def _send_notification(self, alert: Alert):
        for channel in self.notification_channels:
            try:
                if channel == NotificationChannel.LOG:
                    self._send_log_notification(alert)
                elif channel == NotificationChannel.CONSOLE:
                    self._send_console_notification(alert)
                elif channel in self._notification_callbacks:
                    self._notification_callbacks[channel](alert)
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
    
    def _send_log_notification(self, alert: Alert):
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        logger.log(log_level, f"ALERT [{alert.severity.value}] {alert.alert_type.value}: {alert.message}", extra={'alert_details': alert.details})
    
    def _send_console_notification(self, alert: Alert):
        severity_colors = {AlertSeverity.LOW: "", AlertSeverity.MEDIUM: "⚠️ ", AlertSeverity.HIGH: "🔴 ", AlertSeverity.CRITICAL: "🚨 "}
        prefix = severity_colors.get(alert.severity, "")
        print(f"\n{prefix}ALERT [{alert.severity.value}] {alert.alert_type.value}")
        print(f"  {alert.message}")
        print(f"  Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if alert.details:
            print(f"  Details: {alert.details}")
        print()
    
    def register_notification_callback(self, channel: NotificationChannel, callback: Callable[[Alert], None]):
        self._notification_callbacks[channel] = callback
        logger.info(f"Registered notification callback for {channel.value}")
    
    def record_api_latency(self, latency_ms: float):
        self._api_latencies.append(latency_ms)
        if latency_ms > self.alert_thresholds['max_api_latency_ms']:
            self._create_alert(AlertType.PERFORMANCE_DEGRADATION, AlertSeverity.MEDIUM, f"High API latency: {latency_ms:.2f}ms", {'latency_ms': latency_ms})
    
    def record_data_feed_latency(self, latency_ms: float):
        self._data_feed_latencies.append(latency_ms)
    
    def record_order_processing_latency(self, latency_ms: float):
        self._order_processing_latencies.append(latency_ms)
    
    def _record_error(self, component: str, error_message: str):
        self._error_count += 1
        if component in ['api', 'strategy', 'risk_manager']:
            self._create_alert(AlertType.SYSTEM_ERROR, AlertSeverity.HIGH, f"Error in {component}: {error_message}", {'component': component, 'error': error_message})
    
    def record_warning(self):
        self._warning_count += 1
    
    def get_current_performance(self) -> Optional[PerformanceSnapshot]:
        return self._performance_snapshots[-1] if self._performance_snapshots else None
    
    def get_performance_history(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[PerformanceSnapshot]:
        snapshots = list(self._performance_snapshots)
        if start_time:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]
        if end_time:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]
        return snapshots
    
    def get_system_health(self) -> Optional[SystemHealthMetrics]:
        return self._health_metrics[-1] if self._health_metrics else None
    
    def get_health_history(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[SystemHealthMetrics]:
        metrics = list(self._health_metrics)
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        return metrics
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        alerts = [a for a in self._alerts if not a.acknowledged]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts
    
    def get_alert_history(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, alert_type: Optional[AlertType] = None) -> List[Alert]:
        alerts = list(self._alert_history)
        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        return alerts
    
    def acknowledge_alert(self, alert: Alert):
        alert.acknowledged = True
        logger.info(f"Alert acknowledged: {alert.alert_type.value}")
    
    def acknowledge_all_alerts(self):
        for alert in self._alerts:
            alert.acknowledged = True
        logger.info(f"All {len(self._alerts)} alerts acknowledged")
    
    def clear_acknowledged_alerts(self):
        self._alerts = [a for a in self._alerts if not a.acknowledged]
        logger.info("Acknowledged alerts cleared")
    
    def generate_monitoring_report(self) -> Dict[str, Any]:
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
                    {'type': a.alert_type.value, 'severity': a.severity.value, 'message': a.message, 'timestamp': a.timestamp.isoformat()}
                    for a in active_alerts[:10]
                ]
            },
            'thresholds': self.alert_thresholds
        }
