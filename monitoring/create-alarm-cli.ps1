# Direct AWS CLI commands to create S3 upload monitoring alarm
# Usage: .\create-alarm-cli.ps1 [-BucketName "patco-today"] [-EmailAddress "your@email.com"]

param(
    [string]$BucketName = "patco-today",
    [string]$AlarmName = "PATCO-S3-No-Upload-Activity",
    [int]$HoursWithoutActivity = 24
)

# Pre-configured email addresses
$EmailAddresses = @("papdav12@gmail.com", "david.r.pape@gmail.com")

Write-Host "Creating S3 upload monitoring alarm using AWS CLI..." -ForegroundColor Green
Write-Host "   Bucket: $BucketName" -ForegroundColor Cyan
Write-Host "   Alarm: $AlarmName" -ForegroundColor Cyan
Write-Host "   Threshold: $HoursWithoutActivity hours" -ForegroundColor Cyan
Write-Host "   Email Recipients: $($EmailAddresses -join ', ')" -ForegroundColor Cyan

$topicArn = ""

# Setup SNS with email subscriptions
Write-Host "Setting up SNS notifications..." -ForegroundColor Yellow

# Create SNS topic
$topicName = "patco-s3-monitoring-alerts"
$topicArn = aws sns create-topic --name $topicName --query 'TopicArn' --output text

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Created topic: $topicArn" -ForegroundColor Green
    
    # Set topic display name
    aws sns set-topic-attributes --topic-arn $topicArn --attribute-name DisplayName --attribute-value "PATCO S3 Monitoring Alerts" | Out-Null
    
    # Subscribe each email address
    foreach ($email in $EmailAddresses) {
        Write-Host "   Subscribing: $email" -ForegroundColor Gray
        aws sns subscribe --topic-arn $topicArn --protocol email --notification-endpoint $email | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     Subscription created for $email" -ForegroundColor Green
        } else {
            Write-Host "     Failed to subscribe $email" -ForegroundColor Red
        }
    }
    
    Write-Host "   Please check all email inboxes and confirm the subscriptions" -ForegroundColor Yellow
} else {
    Write-Host "   Failed to create SNS topic" -ForegroundColor Red
    $topicArn = ""
}

# Create the CloudWatch alarm
Write-Host "Creating CloudWatch alarm..." -ForegroundColor Yellow

# Build alarm parameters
$alarmArgs = @(
    "--alarm-name", $AlarmName,
    "--alarm-description", "Triggers when no S3 uploads have occurred in $BucketName for $HoursWithoutActivity+ hours",
    "--metric-name", "NumberOfObjects",
    "--namespace", "AWS/S3",
    "--statistic", "Maximum",
    "--dimensions", "Name=BucketName,Value=$BucketName", "Name=StorageType,Value=AllStorageTypes",
    "--period", "3600",
    "--evaluation-periods", $HoursWithoutActivity.ToString(),
    "--threshold", "0",
    "--comparison-operator", "LessThanOrEqualToThreshold",
    "--treat-missing-data", "breaching"
)

# Add alarm actions if SNS topic exists
if ($topicArn -ne "") {
    $alarmArgs += "--alarm-actions", $topicArn
    $alarmArgs += "--ok-actions", $topicArn
}

try {
    # Create the alarm using parameter expansion
    & aws cloudwatch put-metric-alarm @alarmArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Alarm created successfully!" -ForegroundColor Green
        
        # Get alarm details
        $alarmDetails = aws cloudwatch describe-alarms --alarm-names $AlarmName | ConvertFrom-Json
        $alarm = $alarmDetails.MetricAlarms[0]
        
        Write-Host ""
        Write-Host "Alarm Details:" -ForegroundColor Cyan
        Write-Host "   Name: $($alarm.AlarmName)" -ForegroundColor Gray
        Write-Host "   State: $($alarm.StateValue)" -ForegroundColor Gray
        Write-Host "   Reason: $($alarm.StateReason)" -ForegroundColor Gray
        
        if ($topicArn -ne "") {
            Write-Host "   Notifications: Enabled ($($EmailAddresses.Count) recipients)" -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Host "Monitor the alarm:" -ForegroundColor Yellow
        Write-Host "   aws cloudwatch describe-alarms --alarm-names $AlarmName" -ForegroundColor Gray
        Write-Host ""
        Write-Host "View in AWS Console:" -ForegroundColor Yellow
        Write-Host "   https://console.aws.amazon.com/cloudwatch/home#alarmsV2:alarm/$AlarmName" -ForegroundColor Gray
        
    } else {
        throw "Failed to create alarm"
    }
    
} catch {
    Write-Host "Failed to create alarm: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Testing the alarm:" -ForegroundColor Yellow
Write-Host "   1. The alarm will trigger after $HoursWithoutActivity hours without S3 uploads" -ForegroundColor Gray
Write-Host "   2. Upload a file to test: aws s3 cp testfile.txt s3://$BucketName/" -ForegroundColor Gray
Write-Host "   3. Check alarm state changes in CloudWatch console" -ForegroundColor Gray
