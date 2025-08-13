#!/bin/bash

# Test script to verify the Rock Pi setup
# Run this on the Rock Pi after deployment

set -e

cd "$(dirname "$0")"

echo "Testing PATCO Schedule Processing setup..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check Python dependencies
echo "Checking Python dependencies..."
python3 -c "
import boto3, requests, fitz, bs4
print('✓ All Python dependencies are available')
"

# Check AWS credentials
echo "Checking AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "✓ AWS credentials are configured"
else
    echo "❌ AWS credentials not configured. Please run 'aws configure'"
    exit 1
fi

# Check config file
if [ ! -f "config.json" ]; then
    echo "❌ config.json not found"
    exit 1
else
    echo "✓ Configuration file found"
fi

# Test S3 access
echo "Testing S3 access..."
BUCKET=$(python3 -c "import json; print(json.load(open('config.json'))['s3_bucket'])")
if aws s3 ls s3://$BUCKET/ > /dev/null 2>&1; then
    echo "✓ S3 access working"
else
    echo "❌ Cannot access S3 bucket: $BUCKET"
    exit 1
fi

# Check if systemd timer is active
if systemctl is-active --quiet patco-scheduler.timer; then
    echo "✓ Systemd timer is active"
else
    echo "⚠️  Systemd timer is not active. You may need to start it manually."
fi

echo ""
echo "✓ All tests passed! The system is ready."
echo ""
echo "To run a test execution: ./run_daily_check.sh"
echo "To check timer status: sudo systemctl status patco-scheduler.timer"
echo "To view logs: ls -la logs/"
