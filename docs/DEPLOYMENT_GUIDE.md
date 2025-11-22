# Deployment Guide

This guide provides detailed instructions for deploying the Kite Auto Trading application in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Linux Deployment](#linux-deployment)
3. [Windows Deployment](#windows-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Configuration](#configuration)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+), Windows 10+, or macOS 10.15+
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 2GB RAM (4GB recommended)
- **Storage**: Minimum 1GB free space
- **Network**: Stable internet connection for API access

### Required Accounts

- **Zerodha Kite Account**: Active trading account with API access
- **Kite Connect API**: API key and secret from Zerodha Developer Console

### Python Dependencies

All dependencies are listed in `requirements.txt`:
- kiteconnect
- pyyaml
- python-dotenv
- pandas
- numpy

## Linux Deployment

### Automated Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/kite-auto-trading.git
   cd kite-auto-trading
   ```

2. **Run the deployment script**:
   ```bash
   sudo bash scripts/deploy.sh
   ```

3. **Configure credentials**:
   ```bash
   sudo nano /opt/kite-auto-trading/.env
   ```
   Update with your Kite API credentials.

4. **Start the service**:
   ```bash
   sudo systemctl start kite-trading
   sudo systemctl status kite-trading
   ```

### Manual Deployment

1. **Create application directory**:
   ```bash
   sudo mkdir -p /opt/kite-auto-trading
   cd /opt/kite-auto-trading
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Copy application files**:
   ```bash
   cp -r kite_auto_trading /opt/kite-auto-trading/
   cp -r config /opt/kite-auto-trading/
   cp config.yaml /opt/kite-auto-trading/
   cp .env.example /opt/kite-auto-trading/.env
   ```

5. **Configure environment**:
   ```bash
   nano .env
   ```

6. **Run the application**:
   ```bash
   python -m kite_auto_trading.main
   ```

## Windows Deployment

### Automated Deployment

1. **Open PowerShell as Administrator**

2. **Navigate to project directory**:
   ```powershell
   cd C:\path\to\kite-auto-trading
   ```

3. **Run deployment script**:
   ```powershell
   .\scripts\deploy.ps1 -InstallPath "C:\KiteAutoTrading" -ConfigType "conservative"
   ```

4. **Configure credentials**:
   Edit `C:\KiteAutoTrading\.env` with your API credentials

5. **Start the application**:
   ```powershell
   & "C:\KiteAutoTrading\start_trading.ps1"
   ```

### Manual Deployment

1. **Create installation directory**:
   ```powershell
   New-Item -ItemType Directory -Path "C:\KiteAutoTrading"
   cd C:\KiteAutoTrading
   ```

2. **Create virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Copy files and configure**:
   Copy application files to installation directory and edit `.env`

5. **Run application**:
   ```powershell
   python -m kite_auto_trading.main
   ```

### Windows Service Setup

For running as a Windows Service, use NSSM (Non-Sucking Service Manager):

1. **Download NSSM**: https://nssm.cc/download

2. **Install service**:
   ```powershell
   nssm install KiteTrading "C:\KiteAutoTrading\venv\Scripts\python.exe" "-m kite_auto_trading.main"
   ```

3. **Configure service**:
   ```powershell
   nssm set KiteTrading AppDirectory "C:\KiteAutoTrading"
   nssm set KiteTrading AppStdout "C:\KiteAutoTrading\logs\service.log"
   nssm set KiteTrading AppStderr "C:\KiteAutoTrading\logs\service_error.log"
   ```

4. **Start service**:
   ```powershell
   nssm start KiteTrading
   ```

## Docker Deployment

### Using Docker Compose

1. **Create `docker-compose.yml`**:
   ```yaml
   version: '3.8'
   
   services:
     kite-trading:
       build: .
       container_name: kite-auto-trading
       restart: unless-stopped
       env_file:
         - .env
       volumes:
         - ./logs:/app/logs
         - ./data:/app/data
         - ./config.yaml:/app/config.yaml
       networks:
         - trading-network
   
   networks:
     trading-network:
       driver: bridge
   ```

2. **Create `Dockerfile`**:
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY kite_auto_trading ./kite_auto_trading
   COPY config ./config
   COPY config.yaml .
   
   CMD ["python", "-m", "kite_auto_trading.main"]
   ```

3. **Build and run**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f
   ```

## Configuration

### Choosing a Configuration Profile

The application includes several pre-configured profiles:

1. **Conservative Trading** (`config/conservative_trading.yaml`):
   - Low risk, tight stop losses
   - 1% position sizing
   - Suitable for beginners

2. **Aggressive Trading** (`config/aggressive_trading.yaml`):
   - Higher risk tolerance
   - 5% position sizing
   - Multiple strategies enabled

3. **Day Trading** (`config/day_trading.yaml`):
   - Intraday focus
   - Positions closed before market close
   - Quick profit targets

4. **Swing Trading** (`config/swing_trading.yaml`):
   - Multi-day positions
   - Wider stop losses
   - Higher profit targets

### Customizing Configuration

Edit `config.yaml` to customize:

```yaml
risk_management:
  max_daily_loss: 5000.0  # Maximum loss per day
  max_position_size_percent: 2.0  # % of capital per trade
  stop_loss_percent: 2.0  # Stop loss percentage
  target_profit_percent: 4.0  # Profit target percentage
```

### Environment Variables

Configure `.env` file:

```env
KITE_API_KEY=your_api_key
KITE_ACCESS_TOKEN=your_access_token
KITE_API_SECRET=your_api_secret
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_DAILY_LOSS=5000
```

## Post-Deployment

### Verification Steps

1. **Check application status**:
   ```bash
   # Linux
   sudo systemctl status kite-trading
   
   # Windows
   Get-Service KiteTrading
   ```

2. **Monitor logs**:
   ```bash
   # Linux
   tail -f /opt/kite-auto-trading/logs/trading.log
   
   # Windows
   Get-Content C:\KiteAutoTrading\logs\trading.log -Wait
   ```

3. **Verify API connection**:
   Check logs for successful authentication messages

4. **Test with paper trading**:
   Use Kite Connect sandbox environment first

### Monitoring Setup

1. **Log Rotation**:
   - Logs automatically rotate at 10MB
   - 5 backup files retained

2. **Performance Metrics**:
   - Tracked every 5 minutes
   - Available in logs and database

3. **Alerts**:
   - Configure email alerts in config.yaml
   - Set thresholds for daily loss and drawdown

### Backup Strategy

1. **Database Backups**:
   - Automatic backups every hour
   - Stored in `data/backups/`

2. **Configuration Backups**:
   ```bash
   cp config.yaml config.yaml.backup.$(date +%Y%m%d)
   ```

3. **Log Archival**:
   - Archive old logs monthly
   - Compress and store for compliance

## Troubleshooting

### Common Issues

#### Authentication Failures

**Problem**: "Invalid API credentials" error

**Solution**:
1. Verify API key and access token in `.env`
2. Check token expiration (tokens expire daily)
3. Generate new access token from Kite Connect

#### Connection Issues

**Problem**: "Failed to connect to market data feed"

**Solution**:
1. Check internet connection
2. Verify firewall settings
3. Check Kite API status: https://kite.trade/status

#### Order Placement Failures

**Problem**: Orders not being placed

**Solution**:
1. Check available funds in trading account
2. Verify risk limits in configuration
3. Check order logs for rejection reasons
4. Ensure market is open

#### High Memory Usage

**Problem**: Application consuming excessive memory

**Solution**:
1. Reduce `buffer_size` in config.yaml
2. Limit number of instruments
3. Restart application daily

### Log Analysis

**Check for errors**:
```bash
grep "ERROR" logs/trading.log
```

**Monitor order activity**:
```bash
grep "ORDER" logs/trading.log
```

**View performance metrics**:
```bash
grep "METRICS" logs/trading.log
```

### Getting Help

1. **Documentation**: Check docs/ directory
2. **Logs**: Review application logs
3. **Kite Connect Support**: https://kite.trade/support
4. **GitHub Issues**: Report bugs and request features

## Security Best Practices

1. **Protect Credentials**:
   - Never commit `.env` file to version control
   - Use environment-specific credentials
   - Rotate API tokens regularly

2. **Secure Server**:
   - Use firewall to restrict access
   - Keep system updated
   - Use SSH keys for remote access

3. **Monitor Access**:
   - Review login attempts
   - Monitor API usage
   - Set up alerts for unusual activity

4. **Data Protection**:
   - Encrypt sensitive data
   - Regular backups
   - Secure backup storage

## Maintenance

### Daily Tasks

- Check application status
- Review trading logs
- Monitor P&L and performance

### Weekly Tasks

- Review strategy performance
- Adjust risk parameters if needed
- Check for software updates

### Monthly Tasks

- Archive old logs
- Review and optimize strategies
- Update dependencies
- Backup configuration and data

## Upgrading

### Application Updates

1. **Backup current installation**:
   ```bash
   cp -r /opt/kite-auto-trading /opt/kite-auto-trading.backup
   ```

2. **Pull latest changes**:
   ```bash
   git pull origin main
   ```

3. **Update dependencies**:
   ```bash
   source venv/bin/activate
   pip install --upgrade -r requirements.txt
   ```

4. **Restart service**:
   ```bash
   sudo systemctl restart kite-trading
   ```

### Rollback Procedure

If issues occur after upgrade:

```bash
sudo systemctl stop kite-trading
rm -rf /opt/kite-auto-trading
mv /opt/kite-auto-trading.backup /opt/kite-auto-trading
sudo systemctl start kite-trading
```

## Support and Resources

- **Documentation**: `docs/` directory
- **Configuration Examples**: `config/` directory
- **Kite Connect API**: https://kite.trade/docs/connect/v3/
- **Python kiteconnect**: https://github.com/zerodhatech/pykiteconnect
