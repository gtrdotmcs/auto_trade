# User Guide

Complete guide for using the Kite Auto Trading application.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Running the Application](#running-the-application)
4. [Trading Strategies](#trading-strategies)
5. [Risk Management](#risk-management)
6. [Monitoring and Alerts](#monitoring-and-alerts)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Getting Started

### Prerequisites

Before using the application, ensure you have:

1. **Zerodha Trading Account**: Active account with trading enabled
2. **Kite Connect API Access**: 
   - Register at https://developers.kite.trade/
   - Create an app to get API key and secret
   - Generate access token daily

3. **System Requirements**:
   - Python 3.8 or higher
   - Stable internet connection
   - Minimum 2GB RAM

### Initial Setup

1. **Install the Application**:
   ```bash
   # Clone or download the application
   cd kite-auto-trading
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Configure API Credentials**:
   Edit `.env` file:
   ```env
   KITE_API_KEY=your_api_key_here
   KITE_ACCESS_TOKEN=your_access_token_here
   KITE_API_SECRET=your_api_secret_here
   ```

3. **Choose Configuration Profile**:
   Select a pre-configured profile or customize `config.yaml`:
   - `conservative_trading.yaml` - Low risk, suitable for beginners
   - `aggressive_trading.yaml` - Higher risk, for experienced traders
   - `day_trading.yaml` - Intraday trading focus
   - `swing_trading.yaml` - Multi-day position holding

4. **Test Connection**:
   ```bash
   python -m kite_auto_trading.main --test-connection
   ```

---

## Configuration

### Understanding Configuration Files

The application uses YAML configuration files for all settings.

#### Main Configuration Sections

**1. API Configuration**
```yaml
api:
  base_url: "https://api.kite.trade"
  timeout: 30
  max_retries: 3
  retry_delay: 1.0
```

**2. Risk Management**
```yaml
risk_management:
  max_daily_loss: 5000.0  # Stop trading if daily loss exceeds this
  max_position_size_percent: 2.0  # Max % of capital per trade
  max_positions_per_instrument: 1  # Max positions in same instrument
  stop_loss_percent: 2.0  # Stop loss percentage
  target_profit_percent: 4.0  # Profit target percentage
```

**3. Strategy Configuration**
```yaml
strategies:
  enabled:
    - "moving_average_crossover"
    - "rsi_mean_reversion"
  config_path: "strategies/"
```

**4. Market Data**
```yaml
market_data:
  instruments:
    - "RELIANCE"
    - "TCS"
    - "HDFCBANK"
  timeframes:
    - "5minute"
    - "15minute"
```

### Customizing Configuration

#### Setting Risk Limits

Adjust risk parameters based on your risk tolerance:

```yaml
risk_management:
  # Conservative: 1-2% position size, 1-2% stop loss
  # Moderate: 2-3% position size, 2-3% stop loss
  # Aggressive: 3-5% position size, 3-5% stop loss
  
  max_daily_loss: 5000.0  # Adjust based on account size
  max_position_size_percent: 2.0
  stop_loss_percent: 2.0
  target_profit_percent: 4.0  # 2:1 risk-reward ratio
```

#### Selecting Instruments

Choose instruments to trade:

```yaml
market_data:
  instruments:
    # Blue-chip stocks (lower volatility)
    - "RELIANCE"
    - "TCS"
    - "HDFCBANK"
    - "INFY"
    
    # Mid-cap stocks (higher volatility)
    - "TATAMOTORS"
    - "BAJFINANCE"
    
    # Indices
    - "NIFTY50"
    - "BANKNIFTY"
```

#### Configuring Logging

Adjust logging settings:

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file_path: "logs/trading.log"
  max_file_size: "10MB"
  backup_count: 5
  console_output: true
```

---

## Running the Application

### Starting the Application

**Basic Start**:
```bash
python -m kite_auto_trading.main
```

**With Custom Config**:
```bash
python -m kite_auto_trading.main --config config/day_trading.yaml
```

**Dry Run Mode** (no actual orders):
```bash
python -m kite_auto_trading.main --dry-run
```

### Application Lifecycle

1. **Startup**:
   - Loads configuration
   - Authenticates with Kite API
   - Initializes all components
   - Connects to market data feed
   - Starts strategy evaluation

2. **Running**:
   - Continuously monitors market data
   - Evaluates strategy conditions
   - Generates trading signals
   - Validates against risk limits
   - Places orders when conditions met
   - Tracks positions and P&L

3. **Shutdown**:
   - Closes market data connections
   - Saves state and logs
   - Generates end-of-day report

### Monitoring the Application

**View Logs**:
```bash
# Real-time log monitoring
tail -f logs/trading.log

# Search for errors
grep "ERROR" logs/trading.log

# View order activity
grep "ORDER" logs/trading.log
```

**Check Status**:
The application logs status updates every 5 minutes:
- Active strategies
- Current positions
- Daily P&L
- Risk limit status

---

## Trading Strategies

### Available Strategies

#### 1. Moving Average Crossover

**Description**: Generates buy signals when short-term MA crosses above long-term MA, and sell signals on the opposite.

**Configuration**:
```yaml
strategies:
  moving_average_crossover:
    short_period: 10
    long_period: 20
    instruments:
      - "RELIANCE"
      - "TCS"
```

**Best For**: Trending markets, swing trading

**Risk Level**: Low to Medium

#### 2. RSI Mean Reversion

**Description**: Buys when RSI indicates oversold conditions, sells when overbought.

**Configuration**:
```yaml
strategies:
  rsi_mean_reversion:
    rsi_period: 14
    oversold_threshold: 30
    overbought_threshold: 70
    instruments:
      - "INFY"
      - "WIPRO"
```

**Best For**: Range-bound markets, day trading

**Risk Level**: Medium

### Enabling/Disabling Strategies

Edit `config.yaml`:

```yaml
strategies:
  enabled:
    - "moving_average_crossover"  # Enabled
    # - "rsi_mean_reversion"  # Disabled (commented out)
```

### Creating Custom Strategies

See `docs/API_REFERENCE.md` for details on implementing custom strategies.

Basic template:

```python
from kite_auto_trading.strategies.base import StrategyBase
from kite_auto_trading.models.signals import Signal, SignalType

class MyStrategy(StrategyBase):
    def evaluate(self, market_data):
        signals = []
        # Your strategy logic here
        return signals
```

---

## Risk Management

### Understanding Risk Parameters

#### Maximum Daily Loss

**Purpose**: Stops all trading when daily loss limit is reached

**Setting**: Based on account size and risk tolerance
- Conservative: 1-2% of account
- Moderate: 2-5% of account
- Aggressive: 5-10% of account

**Example**:
```yaml
risk_management:
  max_daily_loss: 5000.0  # For ₹2,50,000 account (2%)
```

#### Position Sizing

**Purpose**: Limits capital allocated to each trade

**Setting**: Percentage of total capital
- Conservative: 1-2%
- Moderate: 2-3%
- Aggressive: 3-5%

**Example**:
```yaml
risk_management:
  max_position_size_percent: 2.0  # 2% of capital per trade
```

#### Stop Loss

**Purpose**: Limits loss on individual trades

**Setting**: Percentage below entry price
- Tight: 1-2% (day trading)
- Moderate: 2-3% (swing trading)
- Wide: 3-5% (position trading)

**Example**:
```yaml
risk_management:
  stop_loss_percent: 2.0  # 2% stop loss
```

#### Profit Target

**Purpose**: Defines profit-taking level

**Setting**: Typically 2-3x stop loss (risk-reward ratio)

**Example**:
```yaml
risk_management:
  target_profit_percent: 4.0  # 4% profit target (2:1 ratio)
```

### Risk Limit Enforcement

The application automatically:
1. **Validates every order** against risk limits
2. **Rejects orders** that exceed limits
3. **Stops trading** when daily loss limit reached
4. **Prevents over-concentration** in single instrument
5. **Logs all risk decisions** for review

### Emergency Stop

Manual emergency stop:
```bash
# Create emergency stop file
touch EMERGENCY_STOP

# Application will stop all trading and close positions
```

---

## Monitoring and Alerts

### Performance Metrics

The application tracks:

1. **Daily Metrics**:
   - Total P&L
   - Win rate
   - Number of trades
   - Average profit/loss

2. **Position Metrics**:
   - Current positions
   - Unrealized P&L
   - Position exposure

3. **Risk Metrics**:
   - Daily loss vs limit
   - Position sizes
   - Drawdown

### Viewing Metrics

**In Logs**:
```bash
grep "METRICS" logs/trading.log
```

**End-of-Day Report**:
Generated automatically at market close in `logs/eod_report_YYYYMMDD.json`

### Alert Configuration

Configure alert thresholds:

```yaml
monitoring:
  alert_thresholds:
    daily_loss_percent: 5.0  # Alert at 5% daily loss
    drawdown_percent: 10.0  # Alert at 10% drawdown
    connection_failures: 3  # Alert after 3 connection failures
```

### Email Alerts (Optional)

Configure email notifications:

```env
NOTIFICATION_EMAIL=your_email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
```

---

## Troubleshooting

### Common Issues

#### Authentication Failures

**Symptom**: "Invalid API credentials" error

**Solutions**:
1. Verify API key and access token in `.env`
2. Generate new access token (tokens expire daily)
3. Check API subscription status on Kite Connect

#### No Orders Being Placed

**Symptom**: Application runs but no orders placed

**Possible Causes**:
1. **Strategy conditions not met**: Check market data and strategy parameters
2. **Risk limits blocking orders**: Review risk configuration
3. **Insufficient funds**: Check available balance
4. **Market closed**: Verify trading hours

**Debugging**:
```bash
# Check strategy signals
grep "SIGNAL" logs/trading.log

# Check risk validation
grep "RISK" logs/trading.log

# Check order attempts
grep "ORDER" logs/trading.log
```

#### Connection Issues

**Symptom**: "Failed to connect to market data feed"

**Solutions**:
1. Check internet connection
2. Verify Kite API status: https://kite.trade/status
3. Check firewall settings
4. Increase timeout in configuration

#### High Memory Usage

**Symptom**: Application consuming excessive memory

**Solutions**:
1. Reduce `buffer_size` in config.yaml
2. Limit number of instruments
3. Restart application daily
4. Check for memory leaks in custom strategies

### Getting Help

1. **Check Logs**: Most issues are logged with details
2. **Review Documentation**: Check docs/ directory
3. **Kite Connect Support**: https://kite.trade/support
4. **Community Forums**: Zerodha TradingQ&A

---

## Best Practices

### Before Going Live

1. **Test with Paper Trading**:
   - Use Kite Connect sandbox environment
   - Run for at least 1 week
   - Verify strategy performance

2. **Start Small**:
   - Begin with conservative risk limits
   - Trade small position sizes
   - Monitor closely for first few days

3. **Understand Your Strategies**:
   - Know entry and exit conditions
   - Understand market conditions where strategy works
   - Be aware of strategy limitations

### Daily Routine

**Morning (Before Market Open)**:
1. Generate new access token
2. Review previous day's performance
3. Check system status
4. Verify configuration

**During Market Hours**:
1. Monitor application logs
2. Check position status
3. Watch for alerts
4. Be ready to intervene if needed

**Evening (After Market Close)**:
1. Review end-of-day report
2. Analyze trade performance
3. Adjust strategies if needed
4. Backup logs and data

### Risk Management

1. **Never Risk More Than You Can Afford to Lose**
2. **Use Stop Losses on Every Trade**
3. **Diversify Across Instruments**
4. **Don't Override Risk Limits**
5. **Review and Adjust Limits Regularly**

### System Maintenance

1. **Daily**:
   - Check application status
   - Review logs for errors
   - Monitor performance

2. **Weekly**:
   - Review strategy performance
   - Adjust parameters if needed
   - Archive old logs

3. **Monthly**:
   - Update dependencies
   - Review and optimize strategies
   - Backup configuration and data

### Security

1. **Protect API Credentials**:
   - Never share API keys
   - Don't commit `.env` to version control
   - Rotate tokens regularly

2. **Secure Your System**:
   - Use strong passwords
   - Enable firewall
   - Keep system updated

3. **Monitor Access**:
   - Review login attempts
   - Check API usage
   - Set up alerts for unusual activity

---

## Advanced Topics

### Backtesting Strategies

Test strategies with historical data:

```python
from kite_auto_trading.strategies.backtesting import Backtester

backtester = Backtester(strategy, historical_data)
results = backtester.run()

print(f"Total Return: {results['total_return']}")
print(f"Win Rate: {results['win_rate']}")
print(f"Max Drawdown: {results['max_drawdown']}")
```

### Hot-Reloading Configuration

Update configuration without restart:

```bash
# Modify config.yaml
nano config.yaml

# Send reload signal
kill -HUP $(pgrep -f kite_auto_trading)
```

### Multiple Strategy Portfolios

Run multiple strategies simultaneously:

```yaml
strategies:
  enabled:
    - "moving_average_crossover"
    - "rsi_mean_reversion"
    - "custom_strategy"
```

Each strategy operates independently with its own risk limits.

---

## Appendix

### Glossary

- **P&L**: Profit and Loss
- **Stop Loss**: Order to limit losses
- **Take Profit**: Order to lock in profits
- **Position**: Open trade
- **Signal**: Trading opportunity identified by strategy
- **Drawdown**: Peak-to-trough decline in account value

### Useful Commands

```bash
# Start application
python -m kite_auto_trading.main

# Test connection
python -m kite_auto_trading.main --test-connection

# Dry run mode
python -m kite_auto_trading.main --dry-run

# View logs
tail -f logs/trading.log

# Check errors
grep "ERROR" logs/trading.log

# Monitor orders
grep "ORDER" logs/trading.log

# View performance
grep "METRICS" logs/trading.log
```

### Configuration Templates

See `config/` directory for example configurations:
- `conservative_trading.yaml`
- `aggressive_trading.yaml`
- `day_trading.yaml`
- `swing_trading.yaml`

### Further Reading

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Kite Connect API Docs](https://kite.trade/docs/connect/v3/)

---

## Support

For questions or issues:
- Email: support@example.com
- Documentation: docs/ directory
- Kite Connect: https://kite.trade/support
