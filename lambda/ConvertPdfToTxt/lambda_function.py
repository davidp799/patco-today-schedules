import json
import os
import boto3
import requests
from datetime import datetime
from io import BytesIO
from pdfminer.high_level import extract_text

S3_BUCKET = 'your-s3-bucket-name'  # <-- Replace with your bucket name

def lambda_handler(event, context):
    # Get PDF URL from event
    pdf_url = event.get('special_schedule_pdf_url')
    if not pdf_url:
        return {
            'statusCode': 400,
            'body': json.dumps('No PDF URL provided in event.')
        }

    # Download PDF
    response = requests.get(pdf_url)
    if response.status_code != 200:
        return {
            'statusCode': 400,
            'body': json.dumps(f'Failed to download PDF: {response.status_code}')
        }

    # Convert PDF to text
    pdf_bytes = BytesIO(response.content)
    try:
        text = extract_text(pdf_bytes)
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error extracting text from PDF: {str(e)}')
        }

    # Prepare S3 path
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    s3_key = f"{today_str}/special_schedule.txt"

    # Upload to S3
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=text.encode('utf-8'))
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error uploading to S3: {str(e)}')
        }

    # Prepare output event
    output_event = dict(event)
    output_event['special_schedule_txt_s3_uri'] = f"s3://{S3_BUCKET}/{s3_key}"

    return {
        'statusCode': 200,
        'body': json.dumps(output_event)
    }
