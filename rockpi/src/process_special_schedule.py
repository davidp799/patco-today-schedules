"""
Special Schedule Processor
Downloads and processes special schedule PDFs identified by Lambda
"""
import sys
import boto3
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import load_config
from utils.logger import setup_logging

def process_special_schedule(date_str, s3_client, config):
    """Downloads and saves special schedule PDF to S3."""
    logger = logging.getLogger('process_special_schedule')
    bucket = config['s3_bucket']
    
    try:
        # Get special schedule info from Lambda output
        info_key = f'lambda-outputs/schedule-info/{date_str}/special_schedule_info.json'
        try:
            response = s3_client.get_object(Bucket=bucket, Key=info_key)
            schedule_info = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            logger.info(f"No special schedule info found for {date_str}")
            return True
        
        pdf_url = schedule_info['pdf_url']
        file_name = 'special_schedule.pdf'
        s3_key = f"schedules/special/{date_str}/{file_name}"
        
        # Check if file already exists in S3
        try:
            s3_client.head_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Special schedule PDF already exists for {date_str}")
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] not in ['404', 'NotFound']:
                logger.error(f"S3 access error: {e}")
                return False
        
        # Download the PDF
        headers = {'User-Agent': config['user_agent']}
        response = requests.get(pdf_url, headers=headers, timeout=config['timeout_seconds'])
        response.raise_for_status()
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=response.content,
            ContentType='application/pdf',
            Metadata={
                'download-date': datetime.now().isoformat(),
                'source-url': pdf_url
            }
        )
        logger.info(f"Successfully processed special schedule for {date_str}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download PDF: {e}")
        return False
    except Exception as e:
        logger.error(f"Error processing special schedule: {e}")
        return False

def main():
    """Main function to process special schedules."""
    config = load_config()
    setup_logging(config.get('log_level', 'INFO'))
    logger = logging.getLogger('process_special_schedule')
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    s3_client = boto3.client('s3', region_name=config['aws_region'])
    
    success = process_special_schedule(date_str, s3_client, config)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
