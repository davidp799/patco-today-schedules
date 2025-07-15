import json
import boto3
import requests
import zipfile
import io
import os

s3 = boto3.client('s3')
BUCKET = "patco-today"
PREFIX = "PortAuthorityTransitCorporation/"
ZIP_URL = "http://www.ridepatco.org/developers/PortAuthorityTransitCorporation.zip"

def lambda_handler(event, context):
    try:
        # Download the zip file
        response = requests.get(ZIP_URL)
        response.raise_for_status()
        zip_bytes = io.BytesIO(response.content)

        # Extract and upload each file to S3
        with zipfile.ZipFile(zip_bytes) as z:
            for file_info in z.infolist():
                if file_info.is_dir():
                    continue
                file_data = z.read(file_info.filename)
                s3_key = os.path.join(PREFIX, file_info.filename)
                s3.put_object(Bucket=BUCKET, Key=s3_key, Body=file_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Files extracted and uploaded to S3 successfully.')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
