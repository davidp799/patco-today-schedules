import json
import os
import boto3
from datetime import datetime, timezone
import logging
import requests
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())

# Initialize S3 client for checking existing schedule metadata
s3_client = boto3.client('s3')

# Define your S3 bucket and key for the regular schedule file
REGULAR_SCHEDULE_BUCKET = os.environ['REGULAR_SCHEDULE_BUCKET']
REGULAR_SCHEDULE_KEY = os.environ['REGULAR_SCHEDULE_KEY']
PATCO_SCHEDULES_URL = os.environ['PATCO_SCHEDULES_URL']
PATCO_GTFS_URL = os.environ['PATCO_GTFS_URL']
PATCO_DEVELOPERS_URL = os.environ['PATCO_DEVELOPERS_URL']

def lambda_handler(event, context):
    logger.info(f"Starting GetScheduleInformation Lambda. Event: {json.dumps(event)}")

    has_special_schedule = False
    pdf_url = ""
    webpage_regular_schedule_content = ""

    # IMPORTANT: Ensure this date is in a parseable format (e.g., ISO 8601).
    webpage_regular_schedule_last_modified_str = "2025-07-15T09:00:00Z" # Example: July 15, 2025, 9:00 AM UTC
    
    # This involves comparing the webpage's last modified date with the one stored in S3.
    # If no file exists in S3, consider it new.
    has_new_regular_schedule = False


    url = event.get('url', PATCO_SCHEDULES_URL)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # connect to webpage and check for regular and special schedule changes
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').get_text() if soup.find('h1') else "No H1 Found"

        return {
            'statusCode': 200,
            'body': {
                'url': url,
                'title': title,
                'content_length': len(response.text),
                'status_code': response.status_code
            }
        }

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {
            'statusCode': 500,
            'body': f"Error scraping {url}: {e}"
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            'statusCode': 500,
            'body': f"An unexpected error occurred: {e}"
        }

    try:
        # Get metadata of the existing regular schedule file from S3
        response = s3_client.head_object(Bucket=REGULAR_SCHEDULE_BUCKET, Key=REGULAR_SCHEDULE_KEY)
        s3_last_modified_str = response.get('Metadata', {}).get('last-modified-date')

        if s3_last_modified_str:
            # Convert S3 metadata date to datetime object (ensure it's UTC)
            s3_last_modified_dt = datetime.fromisoformat(s3_last_modified_str.replace('Z', '+00:00'))
            
            # Convert webpage date to datetime object (ensure it's UTC)
            webpage_last_modified_dt = datetime.fromisoformat(webpage_regular_schedule_last_modified_str.replace('Z', '+00:00'))

            logger.info(f"S3 Last Modified: {s3_last_modified_dt}")
            logger.info(f"Webpage Last Modified: {webpage_last_modified_dt}")

            # Compare dates: If webpage is more recent, it's new
            if webpage_last_modified_dt > s3_last_modified_dt:
                has_new_regular_schedule = True
                logger.info("New regular schedule detected: Webpage is more recent than S3.")
            else:
                logger.info("No new regular schedule: Webpage is not more recent than S3.")
        else:
            # No 'last_modified_date' metadata found on S3 object, consider it new if content differs, or force update
            # For simplicity here, we'll assume if metadata is missing, it's new.
            has_new_regular_schedule = True
            logger.info("No 'x-amz-meta-last-modified-date' metadata on S3 object, considering new regular schedule.")

    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NotFound':
            # File doesn't exist in S3, so it's definitely a new schedule to save
            has_new_regular_schedule = True
            logger.info("Regular schedule file not found in S3, considering new regular schedule.")
        else:
            logger.error(f"Error accessing S3 for regular schedule metadata: {e}")
            # Depending on your error handling, you might want to fail the lambda or force update
            has_new_regular_schedule = False # Or True to attempt saving anyway

    # --- Constructing the Output for Step Functions ---
    # This output will be passed to the 'Parallel' state's branches.
    response_payload = {
        "hasSpecialSchedule": has_special_schedule,
        "hasNewRegularSchedule": has_new_regular_schedule,
        "pdfUrl": pdf_url if has_special_schedule else None, # Only include if a special schedule is expected
        "regularScheduleContent": webpage_regular_schedule_content if has_new_regular_schedule else None,
        "regularScheduleLastModified": webpage_regular_schedule_last_modified_str if has_new_regular_schedule else None,
        "currentTimestamp": datetime.now(timezone.utc).isoformat() # Useful for logging/tracking
    }

    logger.info(f"GetScheduleInformation Lambda completed. Output: {json.dumps(response_payload)}")

    return response_payload
