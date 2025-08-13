# CloudWatch Alarm for S3 Upload Activity Monitoring

Simple AWS CLI-based CloudWatch alarm to monitor S3 upload activity for the patco-today bucket.

## Files

- `create-alarm-cli.ps1`: PowerShell script to create the alarm using AWS CLI
- `README.md`: This documentation

## Alarm Details

The alarm monitors S3 upload activity and triggers when:
- No file uploads have occurred to the `patco-today` bucket for 24+ consecutive hours
- Uses S3 metrics from CloudWatch to detect activity
- Automatically sends email notifications to:
  - papdav12@gmail.com
  - david.r.pape@gmail.com

## Quick Start

### Prerequisites
- AWS CLI installed and configured
- PowerShell (Windows) or equivalent permissions

### Deploy the Alarm

```powershell
# Simple deployment - creates alarm + SNS topic + email subscriptions
.\create-alarm-cli.ps1
```

### Custom Configuration

```powershell
# Custom bucket name and threshold
.\create-alarm-cli.ps1 -BucketName "my-bucket" -HoursWithoutActivity 48
```

## What Gets Created

1. **SNS Topic**: `patco-s3-monitoring-alerts`
2. **Email Subscriptions**: Both email addresses automatically subscribed
3. **CloudWatch Alarm**: `PATCO-S3-No-Upload-Activity`

## Alarm Configuration

- **Metric**: S3 NumberOfObjects for AllStorageTypes
- **Period**: 1 hour intervals
- **Evaluation**: 24 consecutive periods (24 hours total)
- **Threshold**: 0 objects (triggers when no new uploads)
- **Action**: Send notification via SNS when alarm state changes

## Post-Deployment

1. **Check your email** - You'll receive subscription confirmation emails for both addresses
2. **Confirm subscriptions** - Click the confirmation links in both emails
3. **Monitor alarm status** in AWS CloudWatch console

## Testing

To test the alarm:
1. Wait for 24+ hours without uploading files to S3 (alarm will trigger)
2. Upload a test file: `aws s3 cp testfile.txt s3://patco-today/`
3. Alarm should return to OK state
4. Check that you receive email notifications for both state changes

## Monitoring Commands

```powershell
# Check alarm status
aws cloudwatch describe-alarms --alarm-names PATCO-S3-No-Upload-Activity

# View alarm history
aws cloudwatch describe-alarm-history --alarm-name PATCO-S3-No-Upload-Activity

# Test SNS topic
aws sns publish --topic-arn "arn:aws:sns:region:account:patco-s3-monitoring-alerts" --message "Test message"
```

## Cleanup

To remove the alarm and SNS resources:

```powershell
# Delete the alarm
aws cloudwatch delete-alarms --alarm-names PATCO-S3-No-Upload-Activity

# Delete SNS subscriptions and topic
aws sns list-subscriptions-by-topic --topic-arn "your-topic-arn"
aws sns unsubscribe --subscription-arn "subscription-arn"
aws sns delete-topic --topic-arn "your-topic-arn"
```

## Integration with PATCO System

This alarm integrates with your PATCO schedule system:
- **Daily uploads** occur around midnight UTC via Lambda → Rock Pi workflow
- **24-hour threshold** catches missed daily processing cycles
- **Email alerts** notify you immediately when the system fails
- **Recovery monitoring** confirms when uploads resume
