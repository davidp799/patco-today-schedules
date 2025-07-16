import json
import os
import boto3
import requests
from datetime import datetime
from io import BytesIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from io import StringIO

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

    # Convert PDF to text
    pdf_file = BytesIO(response.content)
    output_string = StringIO()
    extract_text_to_fp(pdf_file, output_string, laparams=LAParams())
    text = output_string.getvalue()
    output_string.close()

    # Process text: clean up unwanted sections
    lines = text.split('\n')
    
    # Remove lines until we find the SECOND occurrence of "DLOWNEDNIL" spelled by consecutive lines
    target_word = "DLOWNEDNIL"
    start_index = 0
    occurrences_found = 0
    
    for i in range(len(lines) - len(target_word) + 1):
        # Check if consecutive lines spell "DLOWNEDNIL"
        consecutive_chars = ''.join(line.strip() for line in lines[i:i+len(target_word)])
        if consecutive_chars == target_word:
            occurrences_found += 1
            if occurrences_found == 2:  # Wait for the second occurrence
                start_index = i + len(target_word)
                break
    
    # Keep only lines from after "DLOWNEDNIL" onwards
    lines = lines[start_index:]
    
    # Find and remove everything from "24/7 Customer Service" onwards
    cleaned_lines = []
    for line in lines:
        if "24/7 Customer Service" in line:
            break
        cleaned_lines.append(line)
    
    # Rejoin the cleaned lines
    text = '\n'.join(cleaned_lines)
    
    # Process text: replace "A " with "A,", "P " with "P,", then remove all remaining spaces
    text = text.replace("A ", "A,")
    text = text.replace("P ", "P,")
    text = text.replace(" ", "")

    # Prepare output event - pass through all original data
    output_event = dict(event)
    
    # Check if we're in debug mode
    debug_mode = event.get('debug_mode', False)
    
    if debug_mode:
        # Debug mode: save to local file
        file_name = event.get('file_name', 'special_schedule')
        output_dir = 'output'
        output_path = f"{output_dir}/{file_name}.txt"
        
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
