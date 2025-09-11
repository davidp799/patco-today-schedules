"""
PDF to CSV Converter
Converted from ConvertPdfToTxt Lambda function
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import boto3
import fitz  # PyMuPDF
import requests

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import load_config
from utils.logger import setup_logging

def process_text(text):
    """Clean and format extracted PDF text into CSV format."""
    # Step 1: Replace special characters with CLOSED
    text = text.replace("►", "")
    text = text.replace("à", "CLOSED,")
    
    # Step 2: Remove whitespace and tabs
    text = text.replace(" ", "")
    text = text.replace("\t", "")
    
    # Step 3: Add commas after time patterns (e.g., "12:34A" -> "12:34A,")
    text = re.sub(r'(\d{1,2}:\d{2}[AP])', r'\1,', text)
    
    # Step 4: Filter lines to keep only valid schedule data
    text = filter_valid_lines(text)
    
    # Step 5: Fix CLOSED entries that need comma separation
    text = fix_closed_formatting(text)
    
    # Step 6: Fix missing A/P suffixes in time entries
    text = fix_missing_am_pm(text)
    
    # Step 7: Ensure each line has exactly 14 columns
    text = normalize_to_14_columns(text)
    
    # Log the final processed text line by line for debugging
    logging.info("--- Text after processing (line by line) ---")
    for i, line in enumerate(text.split('\n')):
        logging.info(f"Processed line {i+1}: {line}")
    logging.info("--------------------------------------------")
    
    return text

def filter_valid_lines(text):
    """Keep only lines that contain valid schedule data (numbers, times, CLOSED)."""
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
        
        # Keep lines that contain time patterns or CLOSED
        if re.search(r'\d{1,2}:\d{2}[AP]?', line) or 'CLOSED' in line:
            # Make sure it has some comma-separated structure
            if ',' in line or re.search(r'\d', line):
                filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def fix_closed_formatting(text):
    """Add commas before CLOSED when it's not at the beginning or already preceded by comma."""
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Add comma before CLOSED if not already there
        line = re.sub(r'(?<!,)CLOSED', r',CLOSED', line)
        # Clean up any double commas
        line = re.sub(r',+', ',', line)
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def fix_missing_am_pm(text):
    """Fix missing AM/PM suffixes in time entries."""
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        columns = line.split(',')
        
        for i, col in enumerate(columns):
            col = col.strip()
            # If it looks like a time but missing AM/PM
            if re.match(r'^\d{1,2}:\d{2}$', col):
                # Infer AM/PM based on context
                suffix = infer_am_pm_suffix(columns, i)
                columns[i] = col + suffix
        
        fixed_lines.append(','.join(columns))
    
    return '\n'.join(fixed_lines)

def infer_am_pm_suffix(columns, current_index):
    """Infer AM/PM suffix based on surrounding times."""
    # Look for nearby times with AM/PM to infer
    for i in range(max(0, current_index - 2), min(len(columns), current_index + 3)):
        if i != current_index:
            col = columns[i].strip()
            if re.search(r'\d{1,2}:\d{2}[AP]', col):
                return col[-1]  # Return 'A' or 'P'
    
    # Default to 'A' if we can't infer
    return 'A'

def normalize_to_14_columns(text):
    """Ensure each line has exactly 14 columns."""
    lines = text.split('\n')
    normalized_lines = []
    
    for line in lines:
        columns = [col.strip() for col in line.split(',')]
        
        # Remove empty columns
        columns = [col for col in columns if col]
        
        # Pad or trim to 14 columns
        if len(columns) < 14:
            columns.extend(['CLOSED'] * (14 - len(columns)))
        elif len(columns) > 14:
            columns = columns[:14]
        
        normalized_lines.append(','.join(columns))
    
    return '\n'.join(normalized_lines)

def split_westbound_eastbound(text):
    """Split text into westbound and eastbound schedules."""
    lines = text.split('\n')
    
    # Look for section headers or try to split roughly in half
    westbound_lines = []
    eastbound_lines = []
    found_eastbound_marker = False
    
    for line in lines:
        if 'east' in line.lower() or 'philadelphia' in line.lower():
            found_eastbound_marker = True
            continue
        
        if found_eastbound_marker:
            eastbound_lines.append(line)
        else:
            westbound_lines.append(line)
    
    # If no clear marker found, split roughly in half
    if not found_eastbound_marker:
        mid_point = len(lines) // 2
        westbound_lines = lines[:mid_point]
        eastbound_lines = lines[mid_point:]
    
    westbound_text = clean_empty_lines(westbound_lines)
    eastbound_text = clean_empty_lines(eastbound_lines)
    
    return westbound_text, eastbound_text

def clean_empty_lines(lines):
    """Remove empty lines and return as text."""
    return '\n'.join([line for line in lines if line.strip()])

def add_difference_flags(special_schedule_text, direction):
    """Add difference flags by comparing with regular schedules."""
    # For now, just return the text as-is
    # In a full implementation, you'd compare with regular schedule files
    return special_schedule_text

def main():
    """Main function to convert PDF to CSV."""
    config = load_config()
    setup_logging(config['log_level'])
    
    # Load schedule info
    with open('temp/schedule_info.json', 'r') as f:
        schedule_info = json.load(f)
    
    if not schedule_info.get('has_special_schedule'):
        logging.info("No special schedule to process")
        return
    
    pdf_url = schedule_info.get('special_schedule_pdf_url')
    if not pdf_url:
        logging.error("No PDF URL found in schedule info")
        sys.exit(1)
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=config['aws_region'])
    bucket = config['s3_bucket']
    
    try:
        # Download PDF
        logging.info(f'Downloading PDF from URL: {pdf_url}')
        headers = {
            'User-Agent': config['user_agent'],
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
        response = requests.get(pdf_url, headers=headers, timeout=config['timeout_seconds'])
        response.raise_for_status()
        pdf_content = response.content
        
        # Convert PDF to text using PyMuPDF
        logging.info('Converting PDF to text using PyMuPDF')
        pdf_file = BytesIO(pdf_content)
        doc = fitz.open(stream=pdf_file, filetype="pdf")
        
        # Extract text from all pages
        logging.info('Extracting text from all PDF pages')
        text = ""
        for page in doc:
            text += page.get_text()
        
        doc.close()
        
        # Log the raw text before processing for debugging
        logging.info("--- Raw text from PDF before processing ---")
        for i, line in enumerate(text.split('\n')):
            logging.info(f"Raw line {i+1}: {line}")
        logging.info("-------------------------------------------")
        
        # Clean and format the extracted text
        logging.info('Processing extracted text')
        text = process_text(text)
        
        # Split into westbound and eastbound schedules
        logging.info('Splitting text into westbound and eastbound schedules')
        westbound_text, eastbound_text = split_westbound_eastbound(text)

        # Reverse each line in eastbound data
        logging.info('Reversing each line in eastbound schedule')
        eastbound_lines = eastbound_text.split('\n') if eastbound_text else []
        reversed_eastbound_lines = []
        for line in eastbound_lines:
            columns = line.split(',')
            reversed_columns = list(reversed(columns))
            reversed_eastbound_lines.append(','.join(reversed_columns))
        eastbound_text = '\n'.join(reversed_eastbound_lines)

        # Compare with regular schedules and add difference flags
        logging.info('Comparing special schedules with regular schedules')
        westbound_text = add_difference_flags(westbound_text, 'west')
        eastbound_text = add_difference_flags(eastbound_text, 'east')

        # Get the date from special_schedule_text
        special_text = schedule_info.get('special_schedule_text', '')
        date_match = re.search(r'(\w+), (\w+ \d{1,2}, \d{4})', special_text)
        if date_match:
            date_obj = datetime.strptime(date_match.group(2), "%B %d, %Y")
            schedule_date = date_obj.strftime("%Y-%m-%d")
        else:
            # fallback to today
            schedule_date = datetime.now().strftime("%Y-%m-%d")

        # Upload westbound schedule
        westbound_key = f'schedules/special/{schedule_date}/special_schedule_westbound.csv'
        s3_client.put_object(
            Bucket=bucket,
            Key=westbound_key,
            Body=westbound_text.encode('utf-8'),
            ContentType='text/csv'
        )
        logging.info(f'Uploaded westbound schedule to {westbound_key}')
        
        # Upload eastbound schedule
        eastbound_key = f'schedules/special/{schedule_date}/special_schedule_eastbound.csv'
        s3_client.put_object(
            Bucket=bucket,
            Key=eastbound_key,
            Body=eastbound_text.encode('utf-8'),
            ContentType='text/csv'
        )
        logging.info(f'Uploaded eastbound schedule to {eastbound_key}')
        
        logging.info('PDF conversion and upload completed successfully')
        
    except Exception as e:
        logging.error(f'Error processing PDF: {e}')
        sys.exit(1)

if __name__ == "__main__":
    main()
