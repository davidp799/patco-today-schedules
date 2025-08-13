# Deployment Scripts

This directory contains scripts for setting up the hybrid PATCO schedule processing system.

## Scripts Overview

### `deploy_to_rockpi.ps1` / `deploy_to_rockpi.sh`
Automated deployment to Rock Pi device:
- Creates directory structure
- Transfers source files via SCP
- Sets up Python virtual environment
- Installs dependencies
- Configures cron jobs

**Usage (Windows)**:
```powershell
.\deploy_to_rockpi.ps1
```

**Usage (Linux/macOS)**:
```bash
./deploy_to_rockpi.sh
```

### `deploy_manual.sh`
Step-by-step manual deployment instructions for Rock Pi setup.

### `setup_lambda_trigger.sh`
Configures AWS EventBridge to trigger Lambda function daily at midnight UTC.

**Requirements**:
- AWS CLI configured
- IAM permissions for EventBridge and Lambda

### `setup_rockpi_cron.sh`
Configures cron job on Rock Pi to process Lambda outputs at 12:05 AM UTC.

**Note**: Run this on the Rock Pi device after initial deployment.

## Prerequisites

- Rock Pi 4B+ with SSH access
- AWS CLI configured with appropriate permissions
- Python 3.x on Rock Pi
- Network connectivity between deployment machine and Rock Pi

## Deployment Order

1. `setup_lambda_trigger.sh` - Configure AWS automation
2. `deploy_to_rockpi.ps1/.sh` - Deploy Rock Pi components  
3. `setup_rockpi_cron.sh` - Configure Rock Pi automation

## Configuration

Update these variables in deployment scripts:
- `ROCKPI_IP`: Rock Pi device IP address
- `ROCKPI_USER`: SSH username for Rock Pi
- `AWS_REGION`: AWS region for resources
