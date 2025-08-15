#!/bin/bash

# Setup script for Rock Pi 4B+ PATCO Schedule Processing
# Run this script after copying files to your Rock Pi

set -e

echo "Setting up PATCO Schedule Processing on Rock Pi 4B+..."

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv curl unzip cron

# Install AWS CLI
echo "Installing AWS CLI..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
fi

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Make scripts executable
chmod +x run_daily_check.sh

# Create systemd service (optional - for better process management)
echo "Creating systemd service..."
sudo tee /etc/systemd/system/patco-scheduler.service > /dev/null <<EOF
[Unit]
Description=PATCO Schedule Processing Service
After=network.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/run_daily_check.sh
StandardOutput=append:$(pwd)/logs/service.log
StandardError=append:$(pwd)/logs/service.log

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer for daily execution
sudo tee /etc/systemd/system/patco-scheduler.timer > /dev/null <<EOF
[Unit]
Description=Run PATCO Schedule Processing Daily
Requires=patco-scheduler.service

[Timer]
OnCalendar=daily
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
sudo systemctl daemon-reload
sudo systemctl enable patco-scheduler.timer
sudo systemctl start patco-scheduler.timer

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure AWS credentials: aws configure"
echo "2. Edit config.json with your settings"
echo "3. Test the setup: ./run_daily_check.sh"
echo "4. Check timer status: sudo systemctl status patco-scheduler.timer"
echo ""
echo "The service will run daily at a random time between 00:00 and 00:05."
echo "Logs will be written to the logs/ directory."
