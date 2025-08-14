#!/bin/bash
# Rock Pi Heartbeat Cron Job
# Runs every 6 hours to send heartbeat to AWS CloudWatch
# Add to crontab: 0 */6 * * * /home/user/patco-schedules/run_heartbeat.sh >> /home/user/patco-schedules/logs/heartbeat.log 2>&1

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Log timestamp
echo "=== Heartbeat Check Started: $(date) ==="

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Run the heartbeat monitor
python3 src/heartbeat_monitor.py

# Check exit status
if [ $? -eq 0 ]; then
    echo "✅ Heartbeat sent successfully"
else
    echo "❌ Heartbeat failed"
fi

echo "=== Heartbeat Check Completed: $(date) ==="
echo ""
