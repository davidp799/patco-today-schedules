"""
S3 Schedule Information Reader
Reads schedule information saved by AWS Lambda instead of direct scraping
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import load_config
from utils.logger import setup_logging

def get_latest_schedule_info_from_s3(s3_client, bucket, date_str):
    """Get the latest schedule information from S3 saved by Lambda."""
    s3_key = f'lambda-outputs/schedule-info/{date_str}/schedule_info.json'
    
    try:
        logging.info(f"Reading schedule information from S3: {s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        
        schedule_info = json.loads(response['Body'].read().decode('utf-8'))
        
        logging.info("Successfully loaded schedule information from Lambda output")
        logging.info(f"Lambda execution time: {schedule_info.get('currentTimestamp')}")
        logging.info(f"Has special schedule: {schedule_info.get('has_special_schedule')}")
        logging.info(f"Has new regular schedule: {schedule_info.get('has_new_regular_schedule')}")
        
        return schedule_info
        
    except s3_client.exceptions.NoSuchKey:
        logging.error(f"No schedule information found in S3 for {date_str}")
        logging.error("Make sure the Lambda function ran successfully first")
        return None
    except Exception as e:
        logging.error(f"Error reading schedule information from S3: {e}")
        return None

def check_lambda_execution_status(s3_client, bucket, date_str):
    """Check if Lambda has run for today and when."""
    try:
        # List objects in the lambda outputs directory for today
        prefix = f'lambda-outputs/schedule-info/{date_str}/'
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        
        if 'Contents' in response:
            latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
            logging.info(f"Lambda last ran at: {latest_file['LastModified']}")
            return True
        else:
            logging.warning(f"No Lambda outputs found for {date_str}")
            return False
            
    except Exception as e:
        logging.error(f"Error checking Lambda execution status: {e}")
        return False

def main():
    """Main function to get schedule information from Lambda outputs."""
    config = load_config()
    setup_logging(config['log_level'])
    
    # Create temp directory for output
    os.makedirs('temp', exist_ok=True)
    
    today = datetime.now(timezone.utc)
    date_str = today.strftime('%Y-%m-%d')
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=config['aws_region'])
    bucket = config['s3_bucket']
    
    try:
        # Check if Lambda has run today
        if not check_lambda_execution_status(s3_client, bucket, date_str):
            logging.error("Lambda hasn't run today. Attempting to trigger it...")
            
            # Try to invoke Lambda manually
            lambda_client = boto3.client('lambda', region_name=config['aws_region'])
            try:
                lambda_response = lambda_client.invoke(
                    FunctionName='GetScheduleInformation',
                    InvocationType='RequestResponse',
                    Payload='{}'
                )
                
                if lambda_response['StatusCode'] == 200:
                    logging.info("Successfully triggered Lambda execution")
                    # Wait a moment for S3 to be consistent
                    import time
                    time.sleep(5)
                else:
                    logging.error(f"Lambda invocation failed with status: {lambda_response['StatusCode']}")
                    sys.exit(1)
                    
            except Exception as e:
                logging.error(f"Failed to invoke Lambda: {e}")
                sys.exit(1)
        
        # Get schedule information from S3
        schedule_info = get_latest_schedule_info_from_s3(s3_client, bucket, date_str)
        
        if not schedule_info:
            logging.error("Failed to get schedule information")
            sys.exit(1)
        
        # Save to temp file for other scripts to use
        with open('temp/schedule_info.json', 'w') as f:
            json.dump(schedule_info, f, indent=2)
        
        logging.info("Schedule information saved to temp/schedule_info.json")
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
