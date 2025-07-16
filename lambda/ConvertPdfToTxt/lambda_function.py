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
    
    # Split into westbound and eastbound schedules
    westbound_text, eastbound_text = _split_westbound_eastbound(text)

    # Prepare output event - pass through all original data
    output_event = dict(event)
    
    # Check if we're in debug mode
    debug_mode = event.get('debug_mode', False)
    
    if debug_mode:
        # Debug mode: save to local files
        file_name = event.get('file_name', 'special_schedule')
        output_dir = 'output'
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Save westbound schedule
        westbound_path = f"{output_dir}/{file_name}_westbound.csv"
        with open(westbound_path, 'w', encoding='utf-8') as f:
            f.write(westbound_text)
        
        # Save eastbound schedule
        eastbound_path = f"{output_dir}/{file_name}_eastbound.csv"
        with open(eastbound_path, 'w', encoding='utf-8') as f:
            f.write(eastbound_text)
        
        output_event['westbound_schedule_local_path'] = westbound_path
        output_event['eastbound_schedule_local_path'] = eastbound_path
    else:
        # Production mode: upload to S3
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Upload westbound schedule to S3
        westbound_s3_key = f"{today_str}/special_schedule_westbound.csv"
        s3 = boto3.client('s3')
        s3.put_object(Bucket=S3_BUCKET, Key=westbound_s3_key, Body=westbound_text.encode('utf-8'))
        
        # Upload eastbound schedule to S3
        eastbound_s3_key = f"{today_str}/special_schedule_eastbound.csv"
        s3.put_object(Bucket=S3_BUCKET, Key=eastbound_s3_key, Body=eastbound_text.encode('utf-8'))

        output_event['westbound_schedule_s3_uri'] = f"s3://{S3_BUCKET}/{westbound_s3_key}"
        output_event['eastbound_schedule_s3_uri'] = f"s3://{S3_BUCKET}/{eastbound_s3_key}"
    
    # Also include preview of both schedules
    output_event['westbound_preview'] = westbound_text[:500] + "..." if len(westbound_text) > 500 else westbound_text
    output_event['eastbound_preview'] = eastbound_text[:500] + "..." if len(eastbound_text) > 500 else eastbound_text

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
    
    # Step 6: Fix missing A/P suffixes in time entries
    text = _fix_missing_am_pm(text)
    
    # Step 7: Ensure each line has exactly 14 columns
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

def _fix_missing_am_pm(text):
    """Fix time entries that are missing A or P suffixes by inferring from adjacent entries."""
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        if not line.strip():
            fixed_lines.append(line)
            continue
            
        # Split line into columns
        columns = line.split(',')
        
        # Process each column to fix missing A/P
        for i, col in enumerate(columns):
            col = col.strip()
            
            # Skip empty columns or CLOSED entries
            if not col or col == 'CLOSED':
                continue
                
            # Check if this looks like a time without A/P suffix
            if re.match(r'^\d{1,2}:\d{2}$', col):
                # This is a time without A/P suffix - need to infer it
                am_pm_suffix = _infer_am_pm_suffix(columns, i)
                if am_pm_suffix:
                    columns[i] = col + am_pm_suffix
        
        fixed_lines.append(','.join(columns))
    
    return '\n'.join(fixed_lines)

def _infer_am_pm_suffix(columns, current_index):
    """Infer A or P suffix for a time entry based on adjacent entries."""
    # First, try to look at the previous entry
    for i in range(current_index - 1, -1, -1):
        col = columns[i].strip()
        if col and col != 'CLOSED' and re.match(r'^\d{1,2}:\d{2}[AP]$', col):
            # Found a valid time with A/P suffix before current entry
            prev_suffix = col[-1]
            prev_time = col[:-1]
            current_time = columns[current_index].strip()
            
            # Parse times for comparison
            prev_hour = int(prev_time.split(':')[0])
            current_hour = int(current_time.split(':')[0])
            
            # If current hour is greater than previous hour (within reasonable range),
            # use same suffix. If it's much smaller, it probably rolled over to next period
            if current_hour >= prev_hour or (prev_hour - current_hour) <= 2:
                return prev_suffix
            else:
                # Likely rolled over from AM to PM or vice versa
                return 'P' if prev_suffix == 'A' else 'A'
    
    # If no previous entry found, try looking at the next entry
    for i in range(current_index + 1, len(columns)):
        col = columns[i].strip()
        if col and col != 'CLOSED' and re.match(r'^\d{1,2}:\d{2}[AP]$', col):
            # Found a valid time with A/P suffix after current entry
            next_suffix = col[-1]
            next_time = col[:-1]
            current_time = columns[current_index].strip()
            
            # Parse times for comparison
            next_hour = int(next_time.split(':')[0])
            current_hour = int(current_time.split(':')[0])
            
            # If current hour is less than or equal to next hour, use same suffix
            # If current hour is much larger, it's probably previous period
            if current_hour <= next_hour or (current_hour - next_hour) <= 2:
                return next_suffix
            else:
                # Likely previous period
                return 'A' if next_suffix == 'P' else 'P'
    
    # Default fallback - if we can't determine, assume AM for early hours, PM for later
    current_time = columns[current_index].strip()
    current_hour = int(current_time.split(':')[0])
    return 'A' if current_hour <= 11 else 'P'

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

def _split_westbound_eastbound(text):
    """Split the schedule into westbound and eastbound based on P->A time transition."""
    lines = text.split('\n')
    split_index = None
    
    for i in range(len(lines) - 1):
        current_line = lines[i].strip()
        next_line = lines[i + 1].strip()
        
        # Skip empty lines
        if not current_line or not next_line:
            continue
            
        # Split into columns
        current_columns = current_line.split(',')
        next_columns = next_line.split(',')
        
        # Check if current line ends with a P time and next line starts with an A time
        if current_columns and next_columns:
            # Get last non-empty column from current line
            last_time = None
            for col in reversed(current_columns):
                if col.strip() and col.strip() != 'CLOSED':
                    last_time = col.strip()
                    break
            
            # Get first non-empty column from next line
            first_time = None
            for col in next_columns:
                if col.strip() and col.strip() != 'CLOSED':
                    first_time = col.strip()
                    break
            
            # Check if we found the P->A transition
            if (last_time and first_time and 
                re.match(r'^\d{1,2}:\d{2}P$', last_time) and 
                re.match(r'^\d{1,2}:\d{2}A$', first_time)):
                split_index = i + 1
                break
    
    if split_index is not None:
        # Split found - westbound is lines 0 to split_index-1, eastbound is split_index onwards
        westbound_lines = lines[:split_index]
        eastbound_lines = lines[split_index:]
        
        # Remove empty lines from the beginning and end of each section
        westbound_lines = _clean_empty_lines(westbound_lines)
        eastbound_lines = _clean_empty_lines(eastbound_lines)
        
        westbound_text = '\n'.join(westbound_lines)
        eastbound_text = '\n'.join(eastbound_lines)
    else:
        # No split found - treat entire schedule as westbound, eastbound is empty
        westbound_text = text
        eastbound_text = ""
    
    return westbound_text, eastbound_text

def _clean_empty_lines(lines):
    """Remove empty lines from the beginning and end of a list of lines."""
    # Remove empty lines from the beginning
    while lines and not lines[0].strip():
        lines.pop(0)
    
    # Remove empty lines from the end
    while lines and not lines[-1].strip():
        lines.pop()
    
    return lines

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
