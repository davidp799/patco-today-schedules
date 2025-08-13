# Migration Guide: AWS Lambda to Rock Pi 4B+

## Overview

This guide will help you migrate your PATCO schedule processing from expensive AWS Lambda functions to your Rock Pi 4B+ device running 24/7.

## Architecture Changes

### Before (AWS-only)
```
Step Function → GetScheduleInformation → Parallel Processing
                                       ├── ConvertPdfToTxt (expensive!)
                                       └── SaveNewRegularSchedules
```

### After (Hybrid)
```
Rock Pi (nightly cron) → Rock Pi Processing → Direct S3 Upload
                         ├── Schedule scraping
                         ├── PDF conversion
                         └── GTFS processing

AWS Lambda → GetScheduleFiles (API only)
```

## Benefits

1. **Cost Savings**: PDF processing on Rock Pi vs Lambda
2. **Better Resource Utilization**: Your 24/7 device vs per-execution Lambda
3. **Simpler Architecture**: Fewer moving parts in AWS
4. **More Control**: Full control over processing environment

## Migration Steps

### Step 1: Prepare Your Rock Pi

Ensure your Rock Pi 4B+ has:
- Armbian OS installed and updated
- SSH access configured
- Internet connectivity
- At least 2GB free storage

### Step 2: Deploy the Code

#### Option A: Using PowerShell (Windows)
```powershell
.\deploy_to_rockpi.ps1 -RockPiUser "your_username" -RockPiIP "192.168.1.100"
```

#### Option B: Using Bash (Linux/WSL/macOS)
```bash
# Edit the script first to set your Rock Pi details
nano deploy_to_rockpi.sh
# Update ROCK_PI_USER and ROCK_PI_IP variables

chmod +x deploy_to_rockpi.sh
./deploy_to_rockpi.sh
```

#### Option C: Manual Deployment
```bash
# Copy files to Rock Pi
scp -r rockpi/ user@your-rockpi-ip:/home/user/patco-schedules/

# SSH into Rock Pi and run setup
ssh user@your-rockpi-ip
cd /home/user/patco-schedules
chmod +x setup.sh
./setup.sh
```

### Step 3: Configure AWS Access

SSH into your Rock Pi and configure AWS credentials:

```bash
ssh user@your-rockpi-ip
cd /home/user/patco-schedules
aws configure
```

Enter your AWS credentials:
- AWS Access Key ID
- AWS Secret Access Key  
- Default region: `us-east-1`
- Default output format: `json`

### Step 4: Test the Setup

```bash
# Test all components
./test_setup.sh

# Run a manual test
./run_daily_check.sh
```

### Step 5: Verify S3 Uploads

Check your S3 bucket to ensure files are being uploaded correctly:
- Special schedules: `schedules/special/YYYY-MM-DD/`
- Regular schedules: `PortAuthorityTransitCorporation/`

### Step 6: Update Your AWS Infrastructure (Optional)

You can now simplify your AWS setup:

1. **Keep**: GetScheduleFiles Lambda (lightweight API)
2. **Remove**: Step Function, GetScheduleInformation, ConvertPdfToTxt, SaveNewRegularSchedules

This will reduce your AWS costs significantly.

## Monitoring and Maintenance

### Checking Status

```bash
# Check if the timer is running
sudo systemctl status patco-scheduler.timer

# View recent logs
ls -la logs/
tail -f logs/daily_run_*.log
```

### Troubleshooting

1. **Check logs**: All output goes to `logs/` directory
2. **Test components individually**:
   ```bash
   source venv/bin/activate
   python3 src/get_schedule_information.py
   python3 src/convert_pdf_to_csv.py
   python3 src/save_regular_schedules.py
   ```
3. **Verify AWS access**: `aws s3 ls s3://your-bucket-name/`

### Updating Code

To update the code on your Rock Pi:

```bash
# Re-run the deployment script
.\deploy_to_rockpi.ps1 -RockPiUser "your_username" -RockPiIP "192.168.1.100"
```

## Cost Comparison

### Before (Lambda)
- PDF processing: ~$0.05 per execution
- Daily execution: ~$18/month
- Plus Step Function costs

### After (Rock Pi)
- Electricity: ~$2/month for 24/7 operation
- AWS costs: Only for lightweight API calls

**Estimated savings: ~$16/month or $192/year**

## Security Considerations

1. **AWS Credentials**: Stored securely on Rock Pi
2. **Network**: Rock Pi only makes outbound connections
3. **SSH**: Consider key-based authentication
4. **Firewall**: Rock Pi doesn't need incoming connections for this use case

## Backup and Recovery

1. **Code**: Backed up in your Git repository
2. **Logs**: Automatically rotated (30 days)
3. **Configuration**: `config.json` should be backed up
4. **AWS Credentials**: Can be reconfigured if needed

The Rock Pi approach gives you much better cost efficiency while maintaining the same functionality!
