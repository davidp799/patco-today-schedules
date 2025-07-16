import json
import os
import boto3
import requests
import re
from datetime import datetime
from io import BytesIO
import fitz  # pymupdf

S3_BUCKET = 'patco-today'

def lambda_handler(event, context):
    # Get PDF URL from event
    pdf_url = event.get('special_schedule_pdf_url')
    if not pdf_url:
        raise ValueError('No PDF URL provided in event.')

    # Download PDF
    response = requests.get(pdf_url)
    if response.status_code != 200:
        raise Exception(f'Failed to download PDF: {response.status_code}')

    # Convert PDF to text using pymupdf
    pdf_file = BytesIO(response.content)
    doc = fitz.open(stream=pdf_file, filetype="pdf")
    
    # Extract text from all pages
    text = ""
    for page in doc:
        text += page.get_text()
    
    doc.close()
    
    # Clean and format the extracted text
    text = _process_text(text)

    # Prepare output event - pass through all original data
    output_event = dict(event)
    
    # Check if we're in debug mode
    debug_mode = event.get('debug_mode', False)
    
    if debug_mode:
        # Debug mode: save to local file
        file_name = event.get('file_name', 'special_schedule')
        output_dir = 'output'
        output_path = f"{output_dir}/{file_name}.csv"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Write text to local file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        output_event['special_schedule_txt_local_path'] = output_path
    else:
        # Production mode: upload to S3
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        s3_key = f"{today_str}/special_schedule.txt"

        # Upload to S3
        s3 = boto3.client('s3')
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=text.encode('utf-8'))

        output_event['special_schedule_txt_s3_uri'] = f"s3://{S3_BUCKET}/{s3_key}"
    
    # Also include the extracted text content for potential use by next step
    output_event['extracted_text_preview'] = text[:500] + "..." if len(text) > 500 else text

    return output_event

def _process_text(text):
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
    text = _filter_valid_lines(text)
    
    # Step 5: Fix CLOSED entries that need comma separation
    text = _fix_closed_formatting(text)
    
    # Step 6: Ensure each line has exactly 14 columns
    text = _normalize_to_14_columns(text)
    
    return text

def _filter_valid_lines(text):
    """Keep only lines that contain valid schedule data (numbers, times, CLOSED)."""
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        # Keep empty lines
        if not line.strip():
            filtered_lines.append(line)
            continue
            
        # Check if line contains only allowed characters
        temp_line = re.sub(r'[0-9:,AP►à\n\r\tCLOSED]', '', line)
        
        # If no unwanted letters remain, keep the line
        if not re.search(r'[a-zA-Z]', temp_line):
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def _fix_closed_formatting(text):
    """Add commas before CLOSED when it's not at the beginning or already preceded by comma."""
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Add comma before CLOSED if it's not at start of line and not already preceded by comma
        fixed_line = re.sub(r'([^,])CLOSED', r'\1,CLOSED', line)
        fixed_lines.append(fixed_line)
    
    return '\n'.join(fixed_lines)

def _normalize_to_14_columns(text):
    """Ensure each line has exactly 14 columns by combining lines as needed."""
    lines = text.split('\n')
    normalized_lines = []
    current_line_columns = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Split current line into columns (remove empty strings from trailing commas)
        columns = [col for col in line.split(',') if col]
        current_line_columns.extend(columns)
        
        # If we have 14 or more columns, create a complete line
        if len(current_line_columns) >= 14:
            # Take exactly 14 columns
            complete_line = ','.join(current_line_columns[:14])
            normalized_lines.append(complete_line)
            
            # Keep any extra columns for the next line
            current_line_columns = current_line_columns[14:]
        
        i += 1
    
    # If there are remaining columns that didn't make a complete line of 14,
    # add them as a final line (this handles partial schedules)
    if current_line_columns:
        remaining_line = ','.join(current_line_columns)
        normalized_lines.append(remaining_line)
    
    return '\n'.join(normalized_lines)

if __name__ == "__main__":
    """Local testing entry point."""
    test_event = {
        "debug_mode": True,
        "file_name": "TW_2025-07-15",
        "special_schedule_pdf_url": "https://www.ridepatco.org/publish/library/TW_2025-07-15.pdf"  # Local file for testing
    }
    try:
        result = lambda_handler(test_event, None)
        print("Processing complete!")
        print(f"Output saved to: {result.get('special_schedule_txt_local_path')}")
        print(f"Preview: {result.get('extracted_text_preview')}")
    except Exception as e:
        print(f"Error during processing: {e}")
        raise
