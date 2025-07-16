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
    
    # Process text: first handle special characters, then fix time formatting
    text = text.replace("à", "CLOSED,")
    text = text.replace("►", "CLOSED,")
    text = text.replace(" ", "")
    text = text.replace("\t", "")
    
    # Fix time formatting: add commas after A and P only when they follow time patterns
    # This regex matches time patterns like "12:34A" or "1:23P" and adds comma after A/P
    text = re.sub(r'(\d{1,2}:\d{2}[AP])', r'\1,', text)
    
    # Filter lines: keep only lines that don't contain letters other than A and P
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip empty lines - keep them
        if not line.strip():
            filtered_lines.append(line)
            continue
            
        # Check if line contains any letters other than A and P
        # Remove allowed characters and see if any letters remain
        temp_line = line
        # Remove numbers, punctuation, and allowed special characters
        temp_line = re.sub(r'[0-9:,AP►à\n\r\tCLOSED]', '', temp_line)
        # If any letters remain, they are not A or P, so skip this line
        if not re.search(r'[a-zA-Z]', temp_line):
            filtered_lines.append(line)
    
    text = '\n'.join(filtered_lines)
    
    # Fix CLOSED entries that are not at the beginning of line and not preceded by comma
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        # Use regex to find CLOSED that is not at the beginning and not preceded by comma
        # This will match any character (except comma) followed by CLOSED
        fixed_line = re.sub(r'([^,])CLOSED', r'\1,CLOSED', line)
        fixed_lines.append(fixed_line)
    
    text = '\n'.join(fixed_lines)

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
