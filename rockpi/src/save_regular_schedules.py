"""
Regular Schedule Saver
Converted from SaveNewRegularSchedules Lambda function
"""

import json
import logging
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import boto3
import requests

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import load_config
from utils.logger import setup_logging

def main():
    """Main function to download and save regular schedules."""
    config = load_config()
    setup_logging(config['log_level'])
    
    # Load schedule info
    with open('temp/schedule_info.json', 'r') as f:
        schedule_info = json.load(f)
    
    if not schedule_info.get('has_new_regular_schedule'):
        logging.info("No new regular schedule to process")
        return
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=config['aws_region'])
    bucket = config['s3_bucket']
    prefix = "gtfs/"
    zip_url = config['gtfs_zip_url']
    
    try:
        # Download the zip file
        logging.info(f'Downloading GTFS zip file from {zip_url}')
        headers = {
            'User-Agent': config['user_agent'],
            'Accept': 'application/zip,application/octet-stream,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        response = requests.get(zip_url, headers=headers, timeout=config['timeout_seconds'])
        response.raise_for_status()
        zip_bytes = BytesIO(response.content)

        # Extract and upload each file to S3
        logging.info('Extracting and uploading files to S3')
        files_uploaded = 0
        
        with zipfile.ZipFile(zip_bytes) as z:
            for file_info in z.infolist():
                if file_info.is_dir():
                    continue
                
                file_data = z.read(file_info.filename)
                s3_key = os.path.join(prefix, file_info.filename).replace('\\', '/')
                
                s3_client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=file_data
                )
                
                logging.info(f'Uploaded {file_info.filename} to {s3_key}')
                files_uploaded += 1
        
        # Update metadata to mark as processed
        effective_date = schedule_info.get('regular_schedule_effective_date', 'unknown')
        metadata_key = 'schedules/regular/current_schedule_metadata'
        
        s3_client.put_object(
            Bucket=bucket,
            Key=metadata_key,
            Body=json.dumps({
                'effective_date': effective_date,
                'processed_at': schedule_info.get('currentTimestamp') or schedule_info.get('current_timestamp', 'unknown'),
                'files_count': files_uploaded
            }).encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'effective-date': effective_date
            }
        )
        
        logging.info(f'Successfully uploaded {files_uploaded} files and updated metadata')
        
    except Exception as e:
        logging.error(f'Error processing regular schedules: {e}')
        sys.exit(1)

if __name__ == "__main__":
    main()
