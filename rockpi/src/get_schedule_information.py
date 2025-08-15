"""
Schedule Information Scraper
Converted from GetScheduleInformation Lambda function
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests
from bs4 import BeautifulSoup

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import load_config
from utils.logger import setup_logging

def get_regular_schedule_effective_date_and_pdf(soup, base_url):
    """Extracts the effective date and PDF link of the regular schedule from the page."""
    for b in soup.find_all('b'):
        text = b.get_text().strip()
        if "effective" in text.lower() and ("schedule" in text.lower() or "timetable" in text.lower()):
            # Look for PDF link in the same vicinity
            link = None
            parent = b.parent
            while parent and not link:
                link = parent.find('a', href=lambda x: x and x.endswith('.pdf'))
                parent = parent.parent
            
            if link:
                pdf_url = link.get('href')
                if not pdf_url.startswith('http'):
                    pdf_url = f"{base_url.rstrip('/')}/{pdf_url.lstrip('/')}"
                return text, pdf_url
    
    return None, None

def get_today_special_schedule(soup, today):
    """Finds today's special schedule PDF and description, if any."""
    special_h2 = next((h2 for h2 in soup.find_all('h2') if "Special Schedule" in h2.get_text()), None)
    if not special_h2:
        return None, None

    ul = special_h2.find_next('ul')
    if not ul:
        return None, None

    # First try: Look for date in link text (existing logic)
    for li in ul.find_all('li'):
        li_text = li.get_text()
        if today.strftime('%B %d') in li_text:  # e.g., "August 13"
            link = li.find('a', href=lambda x: x and x.endswith('.pdf'))
            if link:
                return link.get('href'), li_text

    # Second try: Look for TW_yyyy-mm-dd.pdf format in href
    target_date_str = today.strftime('%Y-%m-%d')
    for li in ul.find_all('li'):
        link = li.find('a', href=lambda x: x and f'TW_{target_date_str}.pdf' in x)
        if link:
            return link.get('href'), li.get_text()

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
        link = li.find('a', href=lambda x: x and x.endswith('.pdf'))
        if link:
            href = link.get('href')
            if any(pattern in href for pattern in date_patterns):
                return href, li.get_text()

    return None, None

def save_special_schedule_to_s3(pdf_url, date_str, s3_client, bucket):
    """Downloads and saves special schedule PDF to S3."""
    try:
        headers = {
            'User-Agent': load_config()['user_agent'],
            'Accept': 'application/pdf,application/octet-stream,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        }
        response = requests.get(pdf_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        s3_key = f'schedules/special/{date_str}/special_schedule.pdf'
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=response.content,
            ContentType='application/pdf'
        )
        
        logging.info(f"Special schedule PDF saved to S3: {s3_key}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download PDF from {pdf_url}: {e}")
        return False
    except Exception as e:
        logging.error(f"Failed to save PDF to S3: {e}")
        return False

def check_new_regular_schedule(s3_client, bucket, key, effective_date):
    """Checks if the regular schedule is new compared to S3 metadata."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        metadata_date = response['Metadata'].get('effective-date')
        
        if metadata_date != effective_date:
            logging.info(f"New regular schedule detected. Current: {metadata_date}, New: {effective_date}")
            return True
        else:
            logging.info(f"Regular schedule is up to date: {effective_date}")
            return False
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logging.info("No existing regular schedule metadata found - treating as new")
            return True
        else:
            logging.error(f"Error checking regular schedule metadata: {e}")
            raise

def main():
    """Main function to scrape schedule information."""
    config = load_config()
    setup_logging(config['log_level'])
    
    # Create temp directory for output
    os.makedirs('temp', exist_ok=True)
    
    today = datetime.now(timezone.utc)
    url = config['patco_schedules_url']
    
    # Use more comprehensive headers to look like a real browser
    headers = {
        'User-Agent': config['user_agent'],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.ridepatco.org/'
    }
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=config['aws_region'])
    bucket = config['s3_bucket']
    
    try:
        logging.info(f"Scraping schedule information from {url}")
        
        # Add a small delay to avoid looking too automated
        import time
        time.sleep(2)
        
        # Create a session for better persistence
        session = requests.Session()
        session.headers.update(headers)
        
        # Try multiple times with increasing delays
        max_retries = config.get('retry_attempts', 3)
        for attempt in range(max_retries):
            try:
                # Try without following redirects first
                response = session.get(url, timeout=config['timeout_seconds'], allow_redirects=False)
                
                # If we get a redirect, follow it manually
                if response.status_code in [301, 302]:
                    redirect_url = response.headers.get('Location')
                    logging.info(f"Got redirect to: {redirect_url}")
                    if redirect_url:
                        response = session.get(redirect_url, timeout=config['timeout_seconds'])
                
                response.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    if attempt < max_retries - 1:
                        delay = (attempt + 1) * 5  # 5, 10, 15 second delays
                        logging.warning(f"Got 403 error, waiting {delay} seconds before retry {attempt + 2}/{max_retries}")
                        time.sleep(delay)
                        continue
                raise
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get regular schedule information
        regular_schedule_effective_date, regular_schedule_pdf_url = get_regular_schedule_effective_date_and_pdf(soup, url)
        
        # Get special schedule information
        pdf_url, special_schedule_text = get_today_special_schedule(soup, today)
        has_special_schedule = pdf_url is not None

        # Check for new regular schedule
        has_new_regular_schedule = False
        if regular_schedule_effective_date:
            regular_schedule_key = 'schedules/regular/current_schedule_metadata'
            has_new_regular_schedule = check_new_regular_schedule(
                s3_client, bucket, regular_schedule_key, regular_schedule_effective_date
            )

        # Save special schedule PDF if found
        if has_special_schedule:
            if not pdf_url.startswith('http'):
                pdf_url = f"{url.rstrip('/')}/{pdf_url.lstrip('/')}"
            
            date_str = today.strftime('%Y-%m-%d')
            success = save_special_schedule_to_s3(pdf_url, date_str, s3_client, bucket)
            if not success:
                has_special_schedule = False

        # Prepare output
        result = {
            'regular_schedule_effective_date': regular_schedule_effective_date,
            'regular_schedule_pdf_url': regular_schedule_pdf_url,
            'has_new_regular_schedule': has_new_regular_schedule,
            'has_special_schedule': has_special_schedule,
            'special_schedule_pdf_url': pdf_url if has_special_schedule else None,
            'special_schedule_text': special_schedule_text,
            'current_timestamp': today.isoformat(),
            'schedule_date': today.strftime('%Y-%m-%d')
        }
        
        # Save result to temp file
        with open('temp/schedule_info.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        logging.info(f"Schedule information saved. Special: {has_special_schedule}, New Regular: {has_new_regular_schedule}")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
