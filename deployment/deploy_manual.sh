#!/bin/bash

# Simple manual deployment script
# Run this if the PowerShell script has issues

# Configuration - UPDATE THESE
ROCK_PI_USER="david"
ROCK_PI_IP="192.168.1.247"
REMOTE_PATH="/home/$ROCK_PI_USER/patco-schedules"

echo "Manual deployment to Rock Pi..."

# Create zip of rockpi directory
echo "Creating deployment package..."
cd "$(dirname "$0")"
zip -r patco-deploy.zip rockpi/ -x "*.git*" "*__pycache__*" "*.pyc"

echo "Copying to Rock Pi..."
scp patco-deploy.zip $ROCK_PI_USER@$ROCK_PI_IP:/tmp/

echo "Extracting and setting up on Rock Pi..."
ssh $ROCK_PI_USER@$ROCK_PI_IP << 'EOF'
mkdir -p /home/david/patco-schedules
cd /home/david/patco-schedules
unzip -o /tmp/patco-deploy.zip
mv rockpi/* .
rmdir rockpi
rm /tmp/patco-deploy.zip
chmod +x *.sh
ls -la
EOF

# Clean up local zip
rm patco-deploy.zip

echo ""
echo "Deployment complete!"
echo "Next steps:"
echo "1. SSH to Rock Pi: ssh $ROCK_PI_USER@$ROCK_PI_IP"
echo "2. Run setup: cd $REMOTE_PATH && ./setup.sh"
