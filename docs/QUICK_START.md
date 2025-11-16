# Kite Auto-Trading - Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure API Credentials

Create `.env` file:
```bash
KITE_API_KEY=your_api_key
KITE_ACCESS_TOKEN=your_access_token
KITE_API_SECRET=your_api_secret
```

### Step 3: Configure Application

Edit `config.yaml`:
```yaml
risk_management:
  max_daily_loss: 1000.0
  max_position_size_percent: 2.0

portfolio:
  initial_capital: 100000.0
```

### Step 4: Run in Dry-Run Mode

```bash
python -m kite_auto_trading.main --dry-run
```

### Step 5: Monitor and Manage

```python
from kite_auto_trading.main import KiteAutoTradingApp

app = KiteAutoTradingApp(dry_run=True)
app.initialize()

# Check status
status = app.get_application_status()
print(f"Running: {status['running']}")

# Enable hot-reload
app.enable_config_hot_reload()

# Run
app.run()
```

## Common Commands

### Start Application
```bash
# Production mode
python -m kite_auto_trading.main

# Dry-run mode
python -m kite_auto_trading.main --dry-run

# Debug mode
python -m kite_auto_trading.main --log-level DEBUG
```

### Runtime Management

```python
# Enable/disable strategies
app.enable_strategy("MA_Crossover")
app.disable_strategy("RSI_MeanReversion")

# Emergency stop
app.trigger_emergency_stop("Manual stop")

# Resume trading
app.clear_emergency_stop()

# Get status
status = app.get_application_status()
report = app.get_performance_report()
```

## Configuration Quick Reference

### Risk Management
```yaml
risk_management:
  max_daily_loss: 10000.0          # Max daily loss (INR)
  max_position_size_percent: 2.0   # Max position size (%)
  stop_loss_percent: 2.0           # Default stop loss (%)
  emergency_stop_enabled: true     # Enable emergency stop
```

### Strategies
```yaml
strategies:
  enabled: ["MA_Crossover", "RSI_MeanReversion"]
```

### Monitoring
```yaml
monitoring:
  performance_metrics_interval: 300  # Update every 5 min
  alert_thresholds:
    daily_loss_percent: 5.0
    drawdown_percent: 10.0
```

## Troubleshooting

### Authentication Failed
```bash
# Check credentials
cat .env

# Verify API key is correct
# Ensure access token is valid (expires after 8 hours)
```

### Configuration Error
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Check logs
tail -f logs/trading.log
```

### Strategy Not Working
```python
# Check strategy status
status = app.get_strategy_status()
print(status)

# Enable strategy
app.enable_strategy("MA_Crossover")

# Check for errors in logs
```

## Next Steps

1. **Read Full Documentation**: See [APPLICATION_GUIDE.md](APPLICATION_GUIDE.md)
2. **Understand Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Review Examples**: Check `examples/` directory
4. **Test Strategies**: Use dry-run mode extensively
5. **Monitor Performance**: Review metrics regularly

## Safety Checklist

- [ ] Tested in dry-run mode
- [ ] Set appropriate risk limits
- [ ] Configured stop losses
- [ ] Enabled emergency stop
- [ ] Monitoring alerts configured
- [ ] Logs being reviewed
- [ ] Backup configuration saved

## Support

- Documentation: `docs/`
- Issues: GitHub Issues
- API Docs: https://kite.trade/docs/connect/v3/

---

**Quick Start Version**: 1.0.0
**Last Updated**: November 16, 2025
