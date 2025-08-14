# Rock Pi Heartbeat Monitoring Setup Script
# Usage: .\setup-heartbeat-monitoring.ps1 [-DeviceId "your-device-name"] [-EmailAddress "your@email.com"]

param(
    [string]$DeviceId = "rockpi-4b-plus-home",
    [string]$AlarmName = "RockPi-Heartbeat-Missing",
    [double]$ThresholdHours = 6.5,
    [string]$MetricNamespace = "RockPi/Heartbeat",
    [string]$MetricName = "DeviceUptime"
)

# Email addresses (reuse from existing setup)
$EmailAddresses = @("papdav12@gmail.com", "david.r.pape@gmail.com")

Write-Host "Setting up Rock Pi heartbeat monitoring..." -ForegroundColor Green
Write-Host "   Device ID: $DeviceId" -ForegroundColor Cyan
Write-Host "   Alarm: $AlarmName" -ForegroundColor Cyan
Write-Host "   Threshold: $ThresholdHours hours" -ForegroundColor Cyan
Write-Host "   Namespace: $MetricNamespace" -ForegroundColor Cyan
Write-Host "   Email Recipients: $($EmailAddresses -join ', ')" -ForegroundColor Cyan

$topicArn = ""

# Check if SNS topic already exists
Write-Host "Checking for existing SNS topic..." -ForegroundColor Yellow
$existingTopicArn = aws sns list-topics --query "Topics[?contains(TopicArn, 'patco-s3-monitoring-alerts')].TopicArn" --output text

if ($existingTopicArn -and $existingTopicArn.Trim() -ne "") {
    $topicArn = $existingTopicArn.Trim()
    Write-Host "   Using existing SNS topic: $topicArn" -ForegroundColor Green
} else {
    # Create new SNS topic
    Write-Host "   Creating new SNS topic..." -ForegroundColor Yellow
    $topicName = "patco-s3-monitoring-alerts"
    $topicArn = aws sns create-topic --name $topicName --query 'TopicArn' --output text
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Created topic: $topicArn" -ForegroundColor Green
        
        # Set topic display name
        aws sns set-topic-attributes --topic-arn $topicArn --attribute-name DisplayName --attribute-value "PATCO & RockPi Monitoring Alerts" | Out-Null
        
        # Subscribe each email address
        foreach ($email in $EmailAddresses) {
            Write-Host "   Subscribing: $email" -ForegroundColor Gray
            aws sns subscribe --topic-arn $topicArn --protocol email --notification-endpoint $email | Out-Null
        }
        
        Write-Host "   Please check email inboxes and confirm subscriptions" -ForegroundColor Yellow
    } else {
        Write-Host "   Failed to create SNS topic" -ForegroundColor Red
        exit 1
    }
}

# Create CloudWatch Alarm for missing heartbeat
Write-Host "Creating CloudWatch alarm..." -ForegroundColor Yellow

$alarmDescription = "Alert when Rock Pi $DeviceId hasn't sent heartbeat for more than $ThresholdHours hours"

# Convert hours to seconds for the period
$periodSeconds = [int]($ThresholdHours * 3600)

# Create the alarm
$alarmCommand = @"
aws cloudwatch put-metric-alarm \
  --alarm-name "$AlarmName" \
  --alarm-description "$alarmDescription" \
  --metric-name "$MetricName" \
  --namespace "$MetricNamespace" \
  --statistic "Sum" \
  --period $periodSeconds \
  --threshold 1 \
  --comparison-operator "LessThanThreshold" \
  --evaluation-periods 1 \
  --alarm-actions "$topicArn" \
  --treat-missing-data "breaching" \
  --dimensions "Name=DeviceId,Value=$DeviceId"
"@

# Execute the command
Invoke-Expression $alarmCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ CloudWatch alarm created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "    Next Steps:" -ForegroundColor Yellow
    Write-Host "   1. Copy the heartbeat files to your Rock Pi:" -ForegroundColor White
    Write-Host "      scp -r rockpi/ user@your-rockpi-ip:/home/user/patco-schedules/" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   2. SSH to Rock Pi and set up the cron job:" -ForegroundColor White
    Write-Host "      ssh user@your-rockpi-ip" -ForegroundColor Gray
    Write-Host "      cd /home/user/patco-schedules" -ForegroundColor Gray
    Write-Host "      chmod +x run_heartbeat.sh" -ForegroundColor Gray
    Write-Host "      crontab -e" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   3. Add this line to crontab (runs every 6 hours):" -ForegroundColor White
    Write-Host "      0 */6 * * * /home/user/patco-schedules/run_heartbeat.sh >> /home/user/patco-schedules/logs/heartbeat.log 2>&1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   4. Test the heartbeat manually:" -ForegroundColor White
    Write-Host "      python3 src/heartbeat_monitor.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    Cost Estimate: ~`$0.50-1.00/month" -ForegroundColor Green
    Write-Host "   - CloudWatch custom metrics: ~$0.30/month" -ForegroundColor Gray
    Write-Host "   - CloudWatch alarms: ~$0.10/month" -ForegroundColor Gray
    Write-Host "   - SNS notifications: ~$0.10/month" -ForegroundColor Gray
} else {
    Write-Host "   ❌ Failed to create CloudWatch alarm" -ForegroundColor Red
    exit 1
}

# Optional: Create a second alarm for high system load
Write-Host ""
Write-Host "Creating optional system load alarm..." -ForegroundColor Yellow

$loadAlarmName = "RockPi-High-Load-Warning"
$loadAlarmDescription = "Warning when Rock Pi $DeviceId has high system load"

$loadAlarmCommand = @"
aws cloudwatch put-metric-alarm \
  --alarm-name "$loadAlarmName" \
  --alarm-description "$loadAlarmDescription" \
  --metric-name "LoadAverage" \
  --namespace "$MetricNamespace" \
  --statistic "Average" \
  --period 3600 \
  --threshold 2.0 \
  --comparison-operator "GreaterThanThreshold" \
  --evaluation-periods 2 \
  --alarm-actions "$topicArn" \
  --treat-missing-data "notBreaching" \
  --dimensions "Name=DeviceId,Value=$DeviceId"
"@

Invoke-Expression $loadAlarmCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ System load alarm created successfully!" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  System load alarm creation failed (optional)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete! Your Rock Pi will now be monitored every 6 hours." -ForegroundColor Green
