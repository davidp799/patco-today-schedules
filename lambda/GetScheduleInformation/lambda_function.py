import logging
import os
import re
from datetime import datetime, timezone

import boto3
import requests
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())

# Initialize S3 client
s3_client = boto3.client('s3')

# Environment variables
PATCO_DEVELOPERS_URL = os.environ['PATCO_DEVELOPERS_URL']
PATCO_GTFS_URL = os.environ['PATCO_GTFS_URL']
PATCO_SCHEDULES_URL = os.environ['PATCO_SCHEDULES_URL']
REGULAR_SCHEDULE_BUCKET = os.environ['REGULAR_SCHEDULE_BUCKET']
REGULAR_SCHEDULE_KEY = os.environ['REGULAR_SCHEDULE_KEY']

def lambda_handler(event, context):
    has_special_schedule = False
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    pdf_url = None
    regular_schedule_effective_date = None
    special_schedule_text = None
    today = datetime.now(timezone.utc)
    url = event.get('url', PATCO_SCHEDULES_URL)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Find "Effective xx/xx/xx"
        regular_schedule_effective_date = None
        for b in soup.find_all('b'):
            text = b.get_text(strip=True)
            if text.startswith("Effective "):
                match = re.search(r'Effective\s+(\d{1,2}/\d{1,2}/\d{2,4})', text)
                if match:
                    regular_schedule_effective_date = match.group(1)
                break

        # 2. Find special schedule PDF for today, only after H2 "Special Schedule(s)"
        special_h2 = None
        for h2 in soup.find_all('h2'):
            if "Special Schedule" in h2.get_text():
                special_h2 = h2
                break

        if special_h2:
            ul = special_h2.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    a = li.find('a', href=True)
                    if a and a['href'].lower().endswith('.pdf'):
                        href = a['href']
                        link_text = a.get_text(strip=True)
                        # Try to parse the link text as a date
                        try:
                            # Accept formats like "Monday, July 15, 2025" or "July 15, 2025"
                            date_match = re.search(r'([A-Za-z]+,\s*)?([A-Za-z]+ \d{1,2}, \d{4})', link_text)
                            if date_match:
                                date_str = date_match.group(2)
                                link_date = datetime.strptime(date_str, "%B %d, %Y").date()
                                if link_date == today.date():
                                    pdf_url = href
                                    special_schedule_text = link_text
                                    has_special_schedule = True
                                    break
                        except Exception as e:
                            continue  # If parsing fails, skip this link

        response_payload = {
            'regular_schedule_effective_date': regular_schedule_effective_date,
            'has_new_regular_schedule': has_new_regular_schedule if 'has_new_regular_schedule' in locals() else False,
            'has_special_schedule': has_special_schedule,
            'special_schedule_pdf_url': pdf_url if has_special_schedule else None,
            'special_schedule_text': special_schedule_text if has_special_schedule else None,
            "currentTimestamp": datetime.now(timezone.utc).isoformat() # Useful for logging/tracking
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {
            'statusCode': 500,
            'body': f"Error scraping {url}: {e}"
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {
            'statusCode': 500,
            'body': f"An unexpected error occurred: {e}"
        }

    try:
        # Get metadata of the existing regular schedule file from S3
        response = s3_client.head_object(Bucket=REGULAR_SCHEDULE_BUCKET, Key=REGULAR_SCHEDULE_KEY)
        s3_last_modified_str = response.get('Metadata', {}).get('last-modified-date')

        if s3_last_modified_str:
            # Convert dates to datetime object (ensure it's UTC)
            s3_last_modified_dt = datetime.fromisoformat(s3_last_modified_str.replace('Z', '+00:00'))
            regular_schedule_last_modified_dt = datetime.strptime(regular_schedule_effective_date, "%m/%d/%y").replace(tzinfo=timezone.utc)

            # Compare dates: If webpage is more recent, it's new
            if regular_schedule_last_modified_dt > s3_last_modified_dt:
                has_new_regular_schedule = True
        else:
            has_new_regular_schedule = True

    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NotFound':
            # File doesn't exist in S3, so it's definitely a new schedule to save
            has_new_regular_schedule = True
            # logger.info("Regular schedule file not found in S3, considering new regular schedule.")
        else:
            logger.error(f"Error accessing S3 for regular schedule metadata: {e}")
            # Depending on your error handling, you might want to fail the lambda or force update
            has_new_regular_schedule = False # Or True to attempt saving anyway

    # This output will be passed to the 'Parallel' state's branches.
    response_payload = {
        'regular_schedule_effective_date': regular_schedule_effective_date,
        'has_new_regular_schedule': has_new_regular_schedule if 'has_new_regular_schedule' in locals() else False,
        'has_special_schedule': has_special_schedule,
        'special_schedule_pdf_url': pdf_url if has_special_schedule else None,
        'special_schedule_text': special_schedule_text if has_special_schedule else None,
        "currentTimestamp": datetime.now(timezone.utc).isoformat() # Useful for logging/tracking
    }

    return response_payload
