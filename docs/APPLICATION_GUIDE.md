# Kite Auto-Trading Application Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Runtime Management](#runtime-management)
7. [Monitoring and Alerts](#monitoring-and-alerts)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Overview

The Kite Auto-Trading Application is a production-ready automated trading system that integrates with Zerodha's Kite Connect API. It provides:

- **Automated Trading**: Execute trading strategies automatically based on market conditions
- **Risk Management**: Built-in risk controls and position sizing
- **Real-time Monitoring**: Performance tracking and system health monitoring
- **Configuration Hot-Reload**: Update settings without restarting
- **Runtime Management**: Enable/disable strategies on the fly
- **Dry-Run Mode**: Test strategies without real trades

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  KiteAutoTradingApp                         │
│                   (Main Orchestrator)                       │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Config       │    │ API Client   │    │ Market Data  │
│ Loader       │    │              │    │ Feed         │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Strategy     │    │ Risk         │    │ Order        │
│ Manager      │    │ Manager      │    │ Manager      │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────┐                        ┌──────────────┐
│ Portfolio    │                        │ Monitoring   │
│ Manager      │                        │ Service      │
└──────────────┘                        └──────────────┘
```

### Key Components

1. **Configuration Loader**: Manages application configuration with hot-reload support
2. **API Client**: Handles authentication and communication with Kite Connect API
3. **Market Data Feed**: Real-time market data streaming with WebSocket
4. **Strategy Manager**: Orchestrates multiple trading strategies
5. **Risk Manager**: Enforces risk limits and position sizing
6. **Order Manager**: Handles order lifecycle and execution
7. **Portfolio Manager**: Tracks positions and P&L
8. **Monitoring Service**: Performance metrics and alerting

## Installation

### Prerequisites

- Python 3.8 or higher
- Zerodha Kite Connect API credentials
- Required Python packages (see requirements.txt)

### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd kite_auto_trading
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API credentials
```

4. **Create configuration file**
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

## Configuration

### Configuration File Structure

The application uses a YAML configuration file (`config.yaml`) with the following sections:

#### Application Settings
```yaml
app:
  name: "Kite Auto Trading"
  version: "1.0.0"
  environment: "production"  # or "development", "test"
  debug: false
```

#### API Configuration
```yaml
api:
  base_url: "https://api.kite.trade"
  timeout: 30
  max_retries: 3
  retry_delay: 1.0
  rate_limit_delay: 0.5
```

#### Risk Management
```yaml
risk_management:
  max_daily_loss: 10000.0          # Maximum daily loss in INR
  max_position_size_percent: 2.0   # Max position size as % of portfolio
  max_positions_per_instrument: 1  # Max positions per instrument
  stop_loss_percent: 2.0           # Default stop loss %
  target_profit_percent: 4.0       # Default target profit %
  emergency_stop_enabled: true     # Enable emergency stop
```

#### Strategy Configuration
```yaml
strategies:
  enabled: ["MA_Crossover", "RSI_MeanReversion"]
  config_path: "strategies/"
```

#### Portfolio Settings
```yaml
portfolio:
  initial_capital: 100000.0
  currency: "INR"
  brokerage_per_trade: 20.0
  tax_rate: 0.15
```

#### Monitoring Configuration
```yaml
monitoring:
  performance_metrics_interval: 300  # seconds
  health_check_interval: 60          # seconds
  alert_thresholds:
    daily_loss_percent: 5.0
    drawdown_percent: 10.0
    connection_failures: 3
```

### Environment Variables

Create a `.env` file with your API credentials:

```bash
# Kite Connect API Configuration
KITE_API_KEY=your_api_key_here
KITE_ACCESS_TOKEN=your_access_token_here
KITE_API_SECRET=your_api_secret_here

# Application Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# Risk Management Settings
MAX_DAILY_LOSS=10000
DEFAULT_POSITION_SIZE_PERCENT=2.0
```

## Running the Application

### Command Line Interface

#### Basic Usage
```bash
# Run with default configuration
python -m kite_auto_trading.main

# Specify configuration file
python -m kite_auto_trading.main --config config.yaml

# Run in dry-run mode (no real trades)
python -m kite_auto_trading.main --config config.yaml --dry-run

# Set log level
python -m kite_auto_trading.main --log-level DEBUG

# Show version
python -m kite_auto_trading.main --version
```

#### Command Line Arguments

- `--config PATH`: Path to configuration file (default: config.yaml)
- `--dry-run`: Run in simulation mode without executing real trades
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--version`: Show application version

### Programmatic Usage

```python
from kite_auto_trading.main import KiteAutoTradingApp

# Create application instance
app = KiteAutoTradingApp(
    config_path="config.yaml",
    dry_run=False,
    log_level="INFO"
)

# Initialize all components
app.initialize()

# Enable configuration hot-reload
app.enable_config_hot_reload()

# Run the application
try:
    app.run()
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    app.shutdown()
```

### Startup Sequence

When the application starts, it performs the following initialization:

1. **Logging Setup**: Configures logging with file and console output
2. **Directory Creation**: Creates necessary directories (logs, data, strategies, config)
3. **Configuration Loading**: Loads and validates configuration
4. **API Authentication**: Authenticates with Kite Connect API
5. **Component Initialization**: Initializes all trading components
6. **Strategy Loading**: Loads and registers trading strategies
7. **Monitoring Start**: Starts performance monitoring
8. **Trading Loop**: Begins main trading loop

## Runtime Management

### Configuration Hot-Reload

The application supports hot-reloading of configuration without restart:

```python
# Enable hot-reload (checks every 5 seconds)
app.enable_config_hot_reload()

# Disable hot-reload
app.disable_config_hot_reload()

# Manual reload
app._reload_configuration()
```

**Supported Configuration Changes:**
- Risk management parameters
- Monitoring thresholds
- Strategy settings
- Logging levels

**Note**: Some changes (like API credentials) require a restart.

### Strategy Management

#### Enable/Disable Strategies

```python
# Enable a strategy
app.enable_strategy("MA_Crossover")

# Disable a strategy
app.disable_strategy("RSI_MeanReversion")

# List all strategies
strategies = app.list_strategies()
print(f"Available strategies: {strategies}")

# Get strategy status
status = app.get_strategy_status()
for name, stats in status.items():
    print(f"{name}: Enabled={stats['enabled']}, "
          f"Evaluations={stats['evaluations']}, "
          f"Errors={stats['errors']}")
```

#### Strategy Status

Each strategy tracks:
- **Enabled**: Whether the strategy is active
- **Evaluations**: Number of times evaluated
- **Errors**: Number of errors encountered
- **Last Evaluation**: Timestamp of last evaluation

### Emergency Stop

#### Trigger Emergency Stop

```python
# Manual emergency stop
app.trigger_emergency_stop("Market conditions unfavorable")

# Check if emergency stop is active
if app.risk_manager.is_emergency_stop_active():
    print("Emergency stop is active")
```

#### Clear Emergency Stop

```python
# Resume trading after emergency stop
success = app.clear_emergency_stop()
if success:
    print("Trading resumed")
```

**Emergency Stop Actions:**
1. Stops all trading activities
2. Cancels pending orders
3. Prevents new order submissions
4. Maintains existing positions
5. Continues monitoring

### Application Status

#### Get Comprehensive Status

```python
status = app.get_application_status()

print(f"Running: {status['running']}")
print(f"Dry Run: {status['dry_run']}")
print(f"Components: {status['components']}")
print(f"Strategies: {status['strategies']}")
print(f"Portfolio Value: {status['portfolio']['total_value']}")
print(f"Total P&L: {status['portfolio']['total_pnl']}")
```

#### Get Performance Report

```python
report = app.get_performance_report()

print(f"Portfolio Value: {report['performance']['portfolio_value']}")
print(f"Total P&L: {report['performance']['total_pnl']}")
print(f"Win Rate: {report['performance']['win_rate']}")
print(f"Sharpe Ratio: {report['performance']['sharpe_ratio']}")
print(f"Max Drawdown: {report['performance']['max_drawdown_pct']}")
```

## Monitoring and Alerts

### Performance Metrics

The application tracks:
- **Portfolio Value**: Current total portfolio value
- **P&L**: Realized and unrealized profit/loss
- **Win Rate**: Percentage of winning trades
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown**: Maximum portfolio decline
- **Position Count**: Number of open positions
- **Trade Count**: Total number of trades

### System Health

Health monitoring includes:
- **API Latency**: Response time from Kite API
- **Data Feed Latency**: Market data delay
- **Order Processing Latency**: Order execution time
- **Error Count**: Number of errors encountered
- **Connection Status**: API and WebSocket connections
- **Health Score**: Overall system health (0-100)

### Alert Types

The system generates alerts for:
- **Drawdown Breach**: Portfolio drawdown exceeds threshold
- **Daily Loss Breach**: Daily loss exceeds limit
- **Leverage Breach**: Leverage exceeds maximum
- **Concentration Breach**: Position concentration too high
- **System Error**: Critical system errors
- **API Error**: API communication errors
- **Strategy Error**: Strategy execution errors
- **Connection Lost**: Lost connection to market data
- **Performance Degradation**: System performance issues

### Alert Severity Levels

- **LOW**: Informational alerts
- **MEDIUM**: Warning conditions
- **HIGH**: Serious issues requiring attention
- **CRITICAL**: Emergency conditions requiring immediate action

## API Reference

### Main Application Class

#### `KiteAutoTradingApp`

**Constructor:**
```python
KiteAutoTradingApp(
    config_path: str = "config.yaml",
    dry_run: bool = False,
    log_level: str = "INFO"
)
```

**Methods:**

##### Lifecycle Management
- `initialize()`: Initialize all components
- `run()`: Start the main trading loop
- `shutdown()`: Gracefully shutdown the application

##### Configuration Management
- `enable_config_hot_reload()`: Enable configuration hot-reloading
- `disable_config_hot_reload()`: Disable configuration hot-reloading

##### Strategy Management
- `enable_strategy(strategy_name: str) -> bool`: Enable a strategy
- `disable_strategy(strategy_name: str) -> bool`: Disable a strategy
- `list_strategies() -> List[str]`: List all strategies
- `get_strategy_status() -> Dict[str, Any]`: Get strategy statistics

##### Administrative Interface
- `get_application_status() -> Dict[str, Any]`: Get application status
- `get_performance_report() -> Dict[str, Any]`: Get performance report
- `trigger_emergency_stop(reason: str)`: Trigger emergency stop
- `clear_emergency_stop() -> bool`: Clear emergency stop

## Troubleshooting

### Common Issues

#### 1. Authentication Failures

**Problem**: Application fails to authenticate with Kite API

**Solutions:**
- Verify API credentials in `.env` file
- Check if access token is valid (tokens expire after 8 hours)
- Ensure API key and secret are correct
- Check network connectivity

#### 2. Configuration Errors

**Problem**: Application fails to start due to configuration errors

**Solutions:**
- Validate YAML syntax in `config.yaml`
- Check all required fields are present
- Verify data types match expected values
- Review error messages in logs

#### 3. Strategy Errors

**Problem**: Strategies fail to execute or generate errors

**Solutions:**
- Check strategy configuration
- Verify market data is available
- Review strategy logs for specific errors
- Disable problematic strategies temporarily

#### 4. Order Execution Failures

**Problem**: Orders fail to execute

**Solutions:**
- Check available funds
- Verify risk limits are not exceeded
- Ensure market is open
- Check order parameters are valid
- Review order manager logs

#### 5. Performance Issues

**Problem**: Application runs slowly or uses excessive resources

**Solutions:**
- Reduce number of active strategies
- Increase trading loop interval
- Reduce market data buffer size
- Check for memory leaks
- Review system resource usage

### Log Files

Logs are stored in the `logs/` directory:
- `trading.log`: Main application log
- Rotated automatically when size exceeds limit
- Configurable retention (default: 5 backup files)

### Debug Mode

Enable debug mode for detailed logging:

```bash
python -m kite_auto_trading.main --log-level DEBUG
```

Or in configuration:
```yaml
logging:
  level: "DEBUG"
```

## Best Practices

### 1. Start with Dry-Run Mode

Always test strategies in dry-run mode before live trading:

```bash
python -m kite_auto_trading.main --dry-run
```

### 2. Set Appropriate Risk Limits

Configure conservative risk limits initially:
- Start with small position sizes (1-2% of portfolio)
- Set tight stop losses (1-2%)
- Limit daily loss to acceptable amount
- Enable emergency stop

### 3. Monitor Regularly

- Check application status frequently
- Review performance metrics daily
- Monitor alert notifications
- Track system health score

### 4. Use Configuration Hot-Reload

Take advantage of hot-reload for:
- Adjusting risk parameters
- Tuning strategy settings
- Modifying alert thresholds
- No downtime required

### 5. Maintain Logs

- Review logs regularly for errors
- Archive old logs periodically
- Monitor log file sizes
- Set up log rotation

### 6. Test Strategy Changes

Before enabling new strategies:
- Backtest thoroughly
- Test in dry-run mode
- Start with small position sizes
- Monitor closely initially

### 7. Handle Emergency Stops

When emergency stop triggers:
- Review the reason
- Check system status
- Verify market conditions
- Clear only when safe to resume

### 8. Keep Configuration Backed Up

- Version control configuration files
- Backup before making changes
- Document configuration changes
- Test configuration changes in dev environment

### 9. Monitor System Resources

- Check CPU and memory usage
- Monitor disk space for logs
- Watch network bandwidth
- Set up resource alerts

### 10. Stay Updated

- Keep dependencies updated
- Review release notes
- Test updates in staging
- Maintain rollback capability

## Security Considerations

### API Credentials

- Store credentials in environment variables
- Never commit credentials to version control
- Use encrypted storage for session files
- Rotate credentials regularly

### Configuration Files

- Protect with appropriate file permissions
- Restrict access to authorized users only
- Encrypt sensitive configuration data
- Audit configuration changes

### Logging

- Avoid logging sensitive data (tokens, keys)
- Secure log files with proper permissions
- Implement log retention policies
- Monitor logs for security events

### Network Security

- Use HTTPS for all API communications
- Validate SSL certificates
- Implement rate limiting
- Monitor for unusual activity

## Support and Resources

### Documentation

- [Kite Connect API Documentation](https://kite.trade/docs/connect/v3/)
- [Application Architecture](docs/ARCHITECTURE.md)
- [Task Completion Summaries](docs/)

### Getting Help

- Review troubleshooting section
- Check log files for errors
- Consult API documentation
- Contact support team

### Contributing

- Follow coding standards
- Write tests for new features
- Document changes
- Submit pull requests

## Appendix

### Configuration Reference

See `config.yaml.example` for complete configuration reference.

### API Endpoints

The application uses the following Kite Connect API endpoints:
- Authentication: `/session/token`
- Orders: `/orders`
- Positions: `/portfolio/positions`
- Market Data: `/quote`
- Historical Data: `/instruments/historical`

### Performance Benchmarks

Typical performance characteristics:
- Initialization: 2-3 seconds
- Trading loop: 5 seconds per cycle
- Order execution: <1 second
- Config reload: <1 second
- Memory usage: 50-100 MB
- CPU usage: <5%

### Version History

- **v1.0.0**: Initial release with full integration
  - Main application orchestrator
  - Configuration hot-reload
  - Runtime management
  - Comprehensive monitoring

---

**Last Updated**: November 16, 2025
**Version**: 1.0.0
