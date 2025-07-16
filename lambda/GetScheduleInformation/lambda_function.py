import boto3
import logging
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())

# Initialize S3 client
s3_client = boto3.client('s3')

# Instantiate variables
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
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        regular_schedule_effective_date, regular_schedule_pdf_url = get_regular_schedule_effective_date_and_pdf(soup, url)
        pdf_url, special_schedule_text = get_today_special_schedule(soup, today)
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
            s3_client, REGULAR_SCHEDULE_BUCKET, REGULAR_SCHEDULE_KEY, regular_schedule_effective_date
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
    return response_payload

def get_regular_schedule_effective_date_and_pdf(soup, base_url):
    """Extracts the effective date and PDF link of the regular schedule from the page."""
    for b in soup.find_all('b'):
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

def get_today_special_schedule(soup, today):
    """Finds today's special schedule PDF and description, if any."""
    special_h2 = next((h2 for h2 in soup.find_all('h2') if "Special Schedule" in h2.get_text()), None)
    if not special_h2:
        return None, None

    ul = special_h2.find_next('ul')
    if not ul:
        return None, None

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
                        return a['href'], link_text
                except Exception:
                    continue
    return None, None

def check_new_regular_schedule(s3_client, bucket, key, effective_date):
    """Checks if the regular schedule is new compared to S3 metadata."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        s3_last_modified_str = response.get('Metadata', {}).get('last-modified-date')
        if not s3_last_modified_str:
            return True
        s3_last_modified_dt = datetime.fromisoformat(s3_last_modified_str.replace('Z', '+00:00'))
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
