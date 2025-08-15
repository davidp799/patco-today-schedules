#!/bin/bash

# Deployment script for Rock Pi
# Run this on your local machine to deploy to Rock Pi

set -e

# Configuration
ROCK_PI_USER="your_username"
ROCK_PI_IP="your_rockpi_ip"
REMOTE_PATH="/home/$ROCK_PI_USER/patco-schedules"

echo "Deploying PATCO Schedule Processing to Rock Pi..."

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "Warning: No SSH key found. You may be prompted for passwords."
fi

# Create remote directory
echo "Creating remote directory..."
ssh $ROCK_PI_USER@$ROCK_PI_IP "mkdir -p $REMOTE_PATH"

# Copy files to Rock Pi
echo "Copying files to Rock Pi..."
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    rockpi/ $ROCK_PI_USER@$ROCK_PI_IP:$REMOTE_PATH/

# Run setup script on Rock Pi
echo "Running setup script on Rock Pi..."
ssh $ROCK_PI_USER@$ROCK_PI_IP "cd $REMOTE_PATH && chmod +x setup.sh && ./setup.sh"

echo ""
echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. SSH into your Rock Pi: ssh $ROCK_PI_USER@$ROCK_PI_IP"
echo "2. Configure AWS credentials: cd $REMOTE_PATH && aws configure"
echo "3. Edit config.json if needed"
echo "4. Test the setup: cd $REMOTE_PATH && ./run_daily_check.sh"
echo ""
echo "The service will run automatically every day."
