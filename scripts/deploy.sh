#!/bin/bash
# Deployment script for Kite Auto Trading application
# This script sets up the environment and deploys the application

set -e  # Exit on error

echo "========================================="
echo "Kite Auto Trading - Deployment Script"
echo "========================================="

# Configuration
APP_DIR="/opt/kite-auto-trading"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
DATA_DIR="$APP_DIR/data"
CONFIG_FILE="$APP_DIR/config.yaml"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

# Step 1: Create application directory
echo "Step 1: Creating application directory..."
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$DATA_DIR"

# Step 2: Install system dependencies
echo "Step 2: Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Step 3: Create virtual environment
echo "Step 3: Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 4: Install Python dependencies
echo "Step 4: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Copy application files
echo "Step 5: Copying application files..."
cp -r kite_auto_trading "$APP_DIR/"
cp -r config "$APP_DIR/"
cp -r strategies "$APP_DIR/"
cp config.yaml "$APP_DIR/"
cp .env.example "$APP_DIR/.env"

# Step 6: Set permissions
echo "Step 6: Setting permissions..."
chown -R $SUDO_USER:$SUDO_USER "$APP_DIR"
chmod +x "$APP_DIR/kite_auto_trading/main.py"

# Step 7: Create systemd service
echo "Step 7: Creating systemd service..."
cat > /etc/systemd/system/kite-trading.service <<EOF
[Unit]
Description=Kite Auto Trading Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python -m kite_auto_trading.main
Restart=on-failure
RestartSec=10
StandardOutput=append:$LOG_DIR/service.log
StandardError=append:$LOG_DIR/service_error.log

[Install]
WantedBy=multi-user.target
EOF

# Step 8: Reload systemd and enable service
echo "Step 8: Enabling service..."
systemctl daemon-reload
systemctl enable kite-trading.service

echo ""
echo "========================================="
echo "Deployment completed successfully!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env with your Kite API credentials"
echo "2. Review and customize $CONFIG_FILE"
echo "3. Start the service: sudo systemctl start kite-trading"
echo "4. Check status: sudo systemctl status kite-trading"
echo "5. View logs: tail -f $LOG_DIR/trading.log"
echo ""
