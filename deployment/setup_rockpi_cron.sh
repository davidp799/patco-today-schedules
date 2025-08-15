#!/bin/bash

# Set up cron job for 12:05 AM daily execution on Rock Pi

echo "Setting up cron job for daily PATCO schedule processing at 12:05 AM UTC..."

# Create the cron job entry for 12:05 AM UTC
CRON_JOB="5 0 * * * /home/david/patco-schedules/run_daily_check.sh >> /home/david/patco-schedules/logs/cron.log 2>&1"

# Add to crontab
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job added successfully!"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Schedule:"
echo "- Lambda runs at 12:00 AM UTC (AWS EventBridge)"
echo "- Rock Pi runs at 12:05 AM UTC (5 minutes later)"
echo ""
echo "This gives the Lambda enough time to complete and save results to S3"
echo "before the Rock Pi starts processing."
