# Rock Pi Heartbeat Monitoring

This directory contains scripts to monitor your Rock Pi 4B+ uptime using AWS CloudWatch and SNS notifications.

## Overview

The heartbeat monitoring system:
- **Rock Pi**: Sends heartbeat every 6 hours to CloudWatch
- **CloudWatch Alarm**: Triggers if no heartbeat for >6 hours  
- **SNS**: Sends email alerts using existing notification setup
- **Cost**: ~$0.50-1.00/month

## Files

- `heartbeat_monitor.py`: Python script that sends heartbeat metrics
- `run_heartbeat.sh`: Cron job wrapper script
- `config_heartbeat.json`: Configuration file
- `setup-heartbeat-monitoring.ps1`: AWS setup script

## Quick Setup

### 1. Deploy AWS Infrastructure

```powershell
# Run from your Windows machine
cd monitoring
.\setup-heartbeat-monitoring.ps1
```

This creates:
- CloudWatch alarm for missing heartbeats (>6 hours)
- SNS notifications (reuses existing topic if available)
- Optional system load monitoring

### 2. Deploy to Rock Pi

```bash
# Copy files to Rock Pi
scp -r rockpi/ user@your-rockpi-ip:/home/user/patco-schedules/

# SSH to Rock Pi
ssh user@your-rockpi-ip
cd /home/user/patco-schedules

# Make scripts executable
chmod +x run_heartbeat.sh

# Install Python dependencies (if not already done)
pip3 install boto3 botocore

# Test heartbeat manually
python3 src/heartbeat_monitor.py
```

### 3. Set Up Cron Job

```bash
# Edit crontab
crontab -e

# Add this line (runs every 6 hours: 12AM, 6AM, 12PM, 6PM)
0 */6 * * * /home/user/patco-schedules/run_heartbeat.sh >> /home/user/patco-schedules/logs/heartbeat.log 2>&1
```

### 4. Verify Setup

```bash
# Check if heartbeat is working
tail -f logs/heartbeat.log

# Check AWS CloudWatch metrics (from any machine with AWS CLI)
aws cloudwatch get-metric-statistics \
  --namespace "RockPi/Heartbeat" \
  --metric-name "DeviceUptime" \
  --dimensions Name=DeviceId,Value=rockpi-4b-plus-home \
  --start-time 2025-08-14T00:00:00Z \
  --end-time 2025-08-14T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

## How It Works

### Heartbeat Process
1. **Every 6 hours**: Cron runs `run_heartbeat.sh`
2. **Script executes**: `heartbeat_monitor.py` sends metrics to CloudWatch
3. **Metrics sent**: Device uptime, system load, memory usage
4. **CloudWatch stores**: Metrics with 6-hour retention for monitoring

### Alert Process
1. **CloudWatch monitors**: Looks for heartbeat metrics every 6.5 hours
2. **Missing data**: Treated as "breaching" (device is down)
3. **Alarm triggers**: If no heartbeat received within threshold
4. **SNS notification**: Sends email to configured addresses

### Metrics Collected

- **DeviceUptime**: Simple alive signal (1.0 = alive)
- **SystemUptime**: Hours since system boot
- **LoadAverage**: 1-minute system load average
- **MemoryUsagePercent**: Percentage of memory in use

## Cost Breakdown

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| CloudWatch Custom Metrics | ~120 metrics/month | ~$0.30 |
| CloudWatch Alarms | 2 alarms | ~$0.20 |
| SNS Notifications | ~10 emails/month | ~$0.10 |
| **Total** | | **~$0.60/month** |

## Troubleshooting

### Common Issues

**Heartbeat not sending:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check network connectivity
curl -I https://cloudwatch.us-east-1.amazonaws.com

# Test heartbeat manually
python3 src/heartbeat_monitor.py
```

**No email alerts:**
```bash
# Check SNS topic subscriptions
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:ACCOUNT:patco-s3-monitoring-alerts

# Test SNS directly
aws sns publish --topic-arn arn:aws:sns:us-east-1:ACCOUNT:patco-s3-monitoring-alerts --message "Test message"
```

**Cron job not running:**
```bash
# Check cron service
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Verify crontab entry
crontab -l
```

### Monitoring Commands

```bash
# View recent heartbeat logs
tail -20 logs/heartbeat.log

# Check last heartbeat time
aws cloudwatch get-metric-statistics \
  --namespace "RockPi/Heartbeat" \
  --metric-name "DeviceUptime" \
  --dimensions Name=DeviceId,Value=rockpi-4b-plus-home \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 21600 \
  --statistics Sum

# Check alarm state
aws cloudwatch describe-alarms --alarm-names "RockPi-Heartbeat-Missing"
```

## Alternative Solutions Considered

1. **Simple HTTP ping service** ($2-5/month)
   - Lambda + API Gateway + EventBridge
   - More complex, higher cost

2. **Third-party monitoring** ($5-20/month)
   - UptimeRobot, Pingdom, etc.
   - External dependency, higher cost

3. **AWS IoT Device Management** ($1-3/month)
   - Overkill for simple heartbeat
   - More setup complexity

The chosen CloudWatch solution provides the best balance of **cost, simplicity, and integration** with your existing AWS infrastructure.
