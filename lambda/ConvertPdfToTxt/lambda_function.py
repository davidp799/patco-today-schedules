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

    # Prepare S3 path
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    s3_key = f"{today_str}/special_schedule.txt"

    # Upload to S3
    s3 = boto3.client('s3')
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=text.encode('utf-8'))

    # Prepare output event - pass through all original data and add S3 URI
    output_event = dict(event)
    output_event['special_schedule_txt_s3_uri'] = f"s3://{S3_BUCKET}/{s3_key}"
    
    # Also include the extracted text content for potential use by next step
    output_event['extracted_text_preview'] = text[:500] + "..." if len(text) > 500 else text

    return output_event
