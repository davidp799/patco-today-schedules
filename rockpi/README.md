# Rock Pi 4B+ Setup for PATCO Schedule Processing

This directory contains the scripts and configuration needed to run the PATCO schedule processing workflow on your Rock Pi 4B+ device.

## Overview

The Rock Pi will handle the heavy lifting operations that were previously done in AWS Lambda:
- Scraping PATCO website for schedule information
- Converting PDF schedules to CSV format
- Downloading and processing GTFS data
- Uploading results directly to S3

The lightweight GetScheduleFiles API remains in AWS Lambda to serve presigned URLs.

## Setup Instructions

### 1. Prerequisites

Your Rock Pi should have:
- Armbian OS installed
- Python 3.8+ installed
- Internet connectivity
- SSH access configured

### 2. Installation

1. Copy the `rockpi/` directory to your Rock Pi:
   ```bash
   scp -r rockpi/ user@your-rockpi-ip:/home/user/patco-schedules/
   ```

2. SSH into your Rock Pi and install dependencies:
   ```bash
   ssh user@your-rockpi-ip
   cd /home/user/patco-schedules
   chmod +x setup.sh
   ./setup.sh
   ```

3. Configure AWS credentials:
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and region (us-east-1)
   ```

4. Set up the cron job:
   ```bash
   crontab -e
   # Add this line to run daily at 2 AM:
   0 2 * * * /home/user/patco-schedules/run_daily_check.sh >> /home/user/patco-schedules/logs/cron.log 2>&1
   ```

### 3. Configuration

Edit `config.json` to match your AWS setup:
- S3 bucket name
- AWS region
- Any other environment-specific settings

### 4. Testing

Run a test execution:
```bash
./run_daily_check.sh
```

Check the logs in `logs/` directory for any issues.

## File Structure

- `setup.sh` - Installation script
- `run_daily_check.sh` - Main execution script (called by cron)
- `src/` - Python modules (converted from Lambda functions)
- `config.json` - Configuration file
- `requirements.txt` - Python dependencies
- `logs/` - Log files directory
