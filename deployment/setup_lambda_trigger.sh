#!/bin/bash

# Script to set up daily EventBridge trigger for GetScheduleInformation Lambda
# This replaces the Step Function for the scraping part

echo "Setting up daily EventBridge trigger for GetScheduleInformation Lambda..."

# Create the EventBridge rule for daily execution at 12:00 AM UTC (midnight)
aws events put-rule \
    --region us-east-1 \
    --name "daily-patco-schedule-check" \
    --schedule-expression "cron(0 0 * * ? *)" \
    --description "Daily trigger for PATCO schedule information collection at midnight UTC" \
    --state ENABLED

# Add Lambda as target for the rule
aws events put-targets \
    --region us-east-1 \
    --rule "daily-patco-schedule-check" \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:905418476603:function:GetScheduleInformation"

# Grant EventBridge permission to invoke the Lambda
aws lambda add-permission \
    --region us-east-1 \
    --function-name GetScheduleInformation \
    --statement-id "allow-eventbridge-daily-trigger" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:us-east-1:905418476603:rule/daily-patco-schedule-check"

echo "EventBridge rule created successfully!"
echo ""
echo "Schedule:"
echo "- Lambda runs at 12:00 AM UTC (midnight)"
echo "- Rock Pi should run at 12:05 AM UTC (5 minutes later)"
echo ""
echo "To check the rule:"
echo "aws events describe-rule --region us-east-1 --name daily-patco-schedule-check"
