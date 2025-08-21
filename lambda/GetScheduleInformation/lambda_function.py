import boto3
import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# Use a requests session for connection reuse
requests_session = requests.Session()

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())

# Initialize S3 client with connection pooling
s3_client = boto3.client('s3', config=boto3.session.Config(
    max_pool_connections=10,
    retries={'max_attempts': 2}
))

# Instantiate variables
GTFS_REFERENCE_OBJECT = os.environ.get('GTFS_REFERENCE_OBJECT')
PATCO_SCHEDULES_URL = os.environ.get('PATCO_SCHEDULES_URL')
REGULAR_SCHEDULE_BUCKET = os.environ.get('REGULAR_SCHEDULE_BUCKET')
REGULAR_SCHEDULE_KEY = os.environ.get('REGULAR_SCHEDULE_KEY')
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/91.0.4472.124 Safari/537.36'
)

def lambda_handler(event, context):
    """
    AWS Lambda handler to scrape PATCO schedule info and check for updates.
    """
    today = datetime.now(timezone.utc)
    url = event.get('url', PATCO_SCHEDULES_URL)
    headers = {'User-Agent': USER_AGENT}

    try:
        response = requests_session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Parse all <b> and <h2> tags once for reuse
        b_tags = soup.find_all('b')
        h2_tags = soup.find_all('h2')

        regular_schedule_effective_date, regular_schedule_pdf_url = get_regular_schedule_effective_date_and_pdf(soup, url, b_tags)
        pdf_url, special_schedule_text = get_today_special_schedule(soup, today, h2_tags)
        has_special_schedule = pdf_url is not None

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {'statusCode': 500, 'body': f"Error scraping {url}: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {'statusCode': 500, 'body': f"Unexpected error: {e}"}

    has_new_regular_schedule = False
    if regular_schedule_effective_date:
        has_new_regular_schedule = check_new_regular_schedule(
            s3_client, REGULAR_SCHEDULE_BUCKET, GTFS_REFERENCE_OBJECT, regular_schedule_effective_date
        )

    response_payload = {
        'regular_schedule_effective_date': regular_schedule_effective_date,
        'regular_schedule_pdf_url': regular_schedule_pdf_url,
        'has_new_regular_schedule': has_new_regular_schedule,
        'has_special_schedule': has_special_schedule,
        'special_schedule_pdf_url': pdf_url,
        'special_schedule_text': special_schedule_text,
        "currentTimestamp": today.isoformat()
    }
    
    # Save the response to S3 for Rock Pi to process
    try:
        s3_key = f'lambda-outputs/schedule-info/{today.strftime("%Y-%m-%d")}/schedule_info.json'
        s3_client.put_object(
            Bucket='patco-today',
            Key=s3_key,
            Body=json.dumps(response_payload, indent=2).encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'execution_time': today.isoformat(),
                'has_special_schedule': str(has_special_schedule),
                'has_new_regular_schedule': str(has_new_regular_schedule)
            }
        )
        logger.info(f"Schedule info saved to S3: {s3_key}")
    except Exception as e:
        logger.error(f"Failed to save schedule info to S3: {e}")
        # Don't fail the Lambda if S3 save fails
    
    return response_payload

def get_regular_schedule_effective_date_and_pdf(soup, base_url, b_tags=None):
    """Extracts the effective date and PDF link of the regular schedule from the page."""
    b_tags = b_tags if b_tags is not None else soup.find_all('b')
    for b in b_tags:
        text = b.get_text(strip=True)
        if text.startswith("Effective "):
            match = re.search(r'Effective\s+(\d{1,2}/\d{1,2}/\d{2,4})', text)
            effective_date = match.group(1) if match else None
            # Look for PDF link in the same parent <p> tag
            parent = b.find_parent('p')
            pdf_url = None
            if parent:
                a_tag = parent.find('a', href=True)
                if a_tag and a_tag['href'].lower().endswith('.pdf'):
                    href = a_tag['href']
                    # Remove leading ".." and join with base url
                    href = re.sub(r'^\.\./', '/', href)
                    pdf_url = f"http://www.ridepatco.org{href}" if href.startswith('/') else f"http://www.ridepatco.org/{href}"
            return effective_date, pdf_url
    return None, None

def get_today_special_schedule(soup, today, h2_tags=None):
    """Finds today's special schedule PDF and description, if any."""
    h2_tags = h2_tags if h2_tags is not None else soup.find_all('h2')
    special_h2 = next((h2 for h2 in h2_tags if "Special Schedule" in h2.get_text()), None)
    if not special_h2:
        return None, None

    ul = special_h2.find_next('ul')
    if not ul:
        return None, None

    # First try: Look for date in link text (existing logic)
    for li in ul.find_all('li'):
        a = li.find('a', href=True)
        if a and a['href'].lower().endswith('.pdf'):
            link_text = a.get_text(strip=True)
            date_match = re.search(r'([A-Za-z]+,\s*)?([A-Za-z]+ \d{1,2}, \d{4})', link_text)
            if date_match:
                try:
                    date_str = date_match.group(2)
                    link_date = datetime.strptime(date_str, "%B %d, %Y").date()
                    if link_date == today.date():
                        pdf_url = a['href']
                        if save_special_schedule_to_s3(pdf_url, today, check_exists=True):
                            return pdf_url, link_text
                        else:
                            logger.warning(f"Failed to save special schedule PDF: {pdf_url}")
                            return pdf_url, link_text
                except Exception:
                    continue

    # Second try: Look for TW_yyyy-mm-dd.pdf format in href
    target_date_str = today.strftime('%Y-%m-%d')
    for li in ul.find_all('li'):
        a = li.find('a', href=True)
        if a and a['href'].lower().endswith('.pdf'):
            href = a['href']
            tw_match = re.search(r'TW_(\d{4}-\d{2}-\d{2})\.pdf', href)
            if tw_match and tw_match.group(1) == target_date_str:
                pdf_url = href
                link_text = a.get_text(strip=True)
                if save_special_schedule_to_s3(pdf_url, today, check_exists=True):
                    return pdf_url, link_text
                else:
                    logger.warning(f"Failed to save special schedule PDF: {pdf_url}")
                    return pdf_url, link_text

    # Third try: Look for any PDF containing today's date in various formats
    date_patterns = [
        today.strftime('%Y-%m-%d'),
        today.strftime('%Y_%m_%d'),
        today.strftime('%m-%d-%Y'),
        today.strftime('%m_%d_%Y'),
        today.strftime('%d-%m-%Y'),
        today.strftime('%d_%m_%Y'),
    ]

    for li in ul.find_all('li'):
        a = li.find('a', href=True)
        if a and a['href'].lower().endswith('.pdf'):
            href = a['href']
            for pattern in date_patterns:
                if pattern in href:
                    pdf_url = href
                    link_text = a.get_text(strip=True)
                    if save_special_schedule_to_s3(pdf_url, today, check_exists=True):
                        return pdf_url, link_text
                    else:
                        logger.warning(f"Failed to save special schedule PDF: {pdf_url}")
                        return pdf_url, link_text

    return None, None

def save_special_schedule_to_s3(pdf_url, date, check_exists=False):
    """Downloads and saves special schedule PDF to S3, skipping upload if already present."""
    try:
        # Construct full URL if needed
        if not pdf_url.startswith('http'):
            if pdf_url.startswith('..'):
                pdf_url = pdf_url.replace('..', '', 1)
            if not pdf_url.startswith('/'):
                pdf_url = '/' + pdf_url
            pdf_url = f"http://www.ridepatco.org{pdf_url}"

        file_name = 'special_schedule.pdf'
        date_str = date.strftime('%Y-%m-%d')
        s3_key = f"schedules/special/{date_str}/{file_name}"

        # Check if file already exists in S3
        if check_exists:
            try:
                s3_client.head_object(Bucket=REGULAR_SCHEDULE_BUCKET, Key=s3_key)
                # File exists, skip upload
                return True
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] != '404' and e.response['Error']['Code'] != 'NotFound':
                    logger.error(f"S3 access error: {e}")
                    return False
                # File does not exist, continue to download/upload

        # Download the PDF
        headers = {'User-Agent': USER_AGENT}
        response = requests_session.get(pdf_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Upload to S3
        s3_client.put_object(
            Bucket=REGULAR_SCHEDULE_BUCKET,
            Key=s3_key,
            Body=response.content,
            ContentType='application/pdf',
            Metadata={
                'download-date': date.isoformat(),
                'source-url': pdf_url
            }
        )
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download special schedule PDF from {pdf_url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to save special schedule PDF to S3: {e}")
        return False

def check_new_regular_schedule(s3_client, bucket, key, effective_date):
    """Checks if the regular schedule is new compared to S3 last modified date."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        s3_last_modified_dt = response['LastModified']  # This is a datetime object (UTC)
        print(f"S3 last modified: {s3_last_modified_dt}")

        # Try both 2-digit and 4-digit year parsing
        for fmt in ("%m/%d/%y", "%m/%d/%Y"):
            try:
                effective_dt = datetime.strptime(effective_date, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            logger.warning(f"Could not parse effective date: {effective_date}")
            return False
        return effective_dt > s3_last_modified_dt
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NotFound':
            return True
        logger.error(f"S3 access error: {e}")
        return False
