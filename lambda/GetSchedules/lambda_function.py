import json
import boto3
from datetime import datetime

s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        # Extract schedule_date from query parameters or default to today's date
        query_params = event.get('queryStringParameters', {})
        schedule_date = query_params.get('schedule_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Validate schedule_date format
        try:
            datetime.strptime(schedule_date, '%Y-%m-%d')
        except ValueError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid date format. Use YYYY-MM-DD.'
                })
            }
        
        bucket_name = 'patco-today'
        base_path = f'schedules/special/{schedule_date}/'
        
        # Check if both eastbound and westbound files exist
        eastbound_key = f'{base_path}special_schedule_eastbound.csv'
        westbound_key = f'{base_path}special_schedule_westbound.csv'
        
        eastbound_exists = check_file_exists(bucket_name, eastbound_key)
        westbound_exists = check_file_exists(bucket_name, westbound_key)
        
        if not eastbound_exists or not westbound_exists:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'message': 'No special schedule found for the given date',
                    'schedule_date': schedule_date
                })
            }
        
        # Generate presigned URLs (valid for 1 hour)
        presigned_url_expiration = 3600  # 1 hour in seconds
        
        eastbound_presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': eastbound_key},
            ExpiresIn=presigned_url_expiration
        )
        
        westbound_presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': westbound_key},
            ExpiresIn=presigned_url_expiration
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Special schedule found',
                'schedule_date': schedule_date,
                'eastbound_url': eastbound_presigned_url,
                'westbound_url': westbound_presigned_url,
                'expires_in_seconds': presigned_url_expiration
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def check_file_exists(bucket_name, key):
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        return True
    except Exception:
        return False
