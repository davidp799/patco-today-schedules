import json
import boto3
from datetime import datetime

s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        # Extract parameters from query string
        query_params = event.get('queryStringParameters', {})
        schedule_date = query_params.get('schedule_date', datetime.now().strftime('%Y-%m-%d'))
        last_updated = query_params.get('last_updated')
        
        # Validate schedule_date format
        try:
            parsed_date = datetime.strptime(schedule_date, '%Y-%m-%d')
        except ValueError:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid date format. Use YYYY-MM-DD.'
                })
            }
        
        bucket_name = 'patco-today'
        response_data = {}
        
        # Check for special schedules
        special_base_path = f'schedules/special/{schedule_date}/'
        eastbound_key = f'{special_base_path}special_schedule_eastbound.csv'
        westbound_key = f'{special_base_path}special_schedule_westbound.csv'
        
        eastbound_exists = check_file_exists(bucket_name, eastbound_key)
        westbound_exists = check_file_exists(bucket_name, westbound_key)
        
        has_special_schedules = eastbound_exists and westbound_exists
        
        if has_special_schedules:
            # Generate presigned URLs for special schedules (valid for 1 hour)
            presigned_url_expiration = 3600
            
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
            
            response_data['special_schedules'] = {
                'schedule_date': schedule_date,
                'eastbound_url': eastbound_presigned_url,
                'westbound_url': westbound_presigned_url,
                'expires_in_seconds': presigned_url_expiration
            }
        
        # Check regular schedules if last_updated parameter is provided
        if last_updated:
            regular_schedule_result = check_regular_schedules(bucket_name, parsed_date, last_updated)
            
            # Structure regular schedules response
            if 'regular_schedules_error' in regular_schedule_result:
                response_data['regular_schedules'] = {
                    'error': regular_schedule_result['regular_schedules_error']
                }
            else:
                regular_schedules_data = {
                    'updated': regular_schedule_result.get('regular_schedules_updated', False)
                }
                
                if regular_schedule_result.get('regular_schedules_updated') == True:
                    regular_schedules_data['last_modified'] = regular_schedule_result['regular_schedules_last_modified']
                    regular_schedules_data['urls'] = regular_schedule_result['regular_schedule_urls']
                    regular_schedules_data['expires_in_seconds'] = regular_schedule_result['regular_urls_expire_in_seconds']
                
                response_data['regular_schedules'] = regular_schedules_data
            
            # Construct a comprehensive message
            if regular_schedule_result.get('regular_schedules_updated') == False:
                if has_special_schedules:
                    response_data['message'] = 'Special schedule found. Regular schedules are up to date'
                else:
                    response_data['message'] = 'No special schedule found for the given date. Regular schedules are up to date'
            elif regular_schedule_result.get('regular_schedules_updated') == True:
                if has_special_schedules:
                    response_data['message'] = 'Special schedule found. Regular schedules updated'
                else:
                    response_data['message'] = 'No special schedule found for the given date. Regular schedules updated'
        else:
            # No last_updated parameter provided, only check special schedules
            if has_special_schedules:
                response_data['message'] = 'Special schedule found'
            else:
                response_data['message'] = 'No special schedule found for the given date'
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def get_regular_schedule_path(date):
    """
    Determine the file path for regular schedules based on the date.
    """
    # Define date ranges and their corresponding paths
    date_ranges = [
        (datetime(2025, 7, 14), datetime(2025, 7, 25), '2025-07-14'),
        (datetime(2025, 7, 28), datetime(2025, 8, 8), '2025-07-28'),
        (datetime(2025, 8, 11), datetime(2025, 8, 22), '2025-08-11'),
        (datetime(2025, 8, 25), datetime(2025, 8, 29), '2025-08-25'),
        (datetime(2025, 9, 1), datetime(2026, 2, 27), '2025-09-01'),
    ]
    
    for start_date, end_date, path_suffix in date_ranges:
        if start_date <= date <= end_date:
            return f'schedules/regular/{path_suffix}'
    
    # For dates from March 2, 2026 onwards
    if date >= datetime(2026, 3, 2):
        return 'schedules/regular'
    
    # Default fallback (should not happen with proper date ranges)
    return 'schedules/regular'

def check_regular_schedules(bucket_name, date, last_updated_str):
    """
    Check if regular schedules need to be updated and return presigned URLs if needed.
    """
    try:
        # Parse last_updated parameter
        try:
            last_updated = datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                # Try ISO format and convert to naive datetime
                last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                # Convert to naive datetime (remove timezone info)
                last_updated = last_updated.replace(tzinfo=None)
            except ValueError:
                return {
                    'regular_schedules_error': 'Invalid last_updated format. Use YYYY-MM-DD HH:MM:SS or ISO format.'
                }
        
        # Get the appropriate path for regular schedules
        regular_path = get_regular_schedule_path(date)
        
        # Check the last-modified time of weekdays-east.csv as reference
        weekdays_east_key = f'{regular_path}/weekdays-east.csv'
        
        try:
            response = s3.head_object(Bucket=bucket_name, Key=weekdays_east_key)
            s3_last_modified = response['LastModified'].replace(tzinfo=None)  # Remove timezone for comparison
            
            # If user's last_updated is older than S3 file, provide new URLs
            if last_updated < s3_last_modified:
                presigned_url_expiration = 3600  # 1 hour
                
                # Define all regular schedule files
                schedule_files = [
                    'saturdays-east.csv',
                    'saturdays-west.csv',
                    'sundays-east.csv',
                    'sundays-west.csv',
                    'weekdays-east.csv',
                    'weekdays-west.csv'
                ]
                
                regular_urls = {}
                for file_name in schedule_files:
                    file_key = f'{regular_path}/{file_name}'
                    if check_file_exists(bucket_name, file_key):
                        presigned_url = s3.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket_name, 'Key': file_key},
                            ExpiresIn=presigned_url_expiration
                        )
                        # Convert filename to URL key (remove .csv and replace - with _)
                        url_key = file_name.replace('.csv', '_url').replace('-', '_')
                        regular_urls[url_key] = presigned_url
                
                return {
                    'regular_schedules_updated': True,
                    'regular_schedules_last_modified': s3_last_modified.strftime('%Y-%m-%d %H:%M:%S'),
                    'regular_schedule_urls': regular_urls,
                    'regular_urls_expire_in_seconds': presigned_url_expiration
                }
            else:
                return {
                    'regular_schedules_updated': False
                }
                
        except Exception as e:
            return {
                'regular_schedules_error': f'Could not check regular schedules: {str(e)}'
            }
            
    except Exception as e:
        return {
            'regular_schedules_error': f'Error checking regular schedules: {str(e)}'
        }

def check_file_exists(bucket_name, key):
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        return True
    except Exception:
        return False
