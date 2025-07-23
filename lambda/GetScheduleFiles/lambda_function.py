import json
import boto3
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

s3 = boto3.client('s3')

# Constants
BUCKET_NAME = 'patco-today'
PRESIGNED_URL_EXPIRATION = 3600  # 1 hour
SPECIAL_SCHEDULE_FILES = ['special_schedule_eastbound.csv', 'special_schedule_westbound.csv']
WEEKDAY_FILES = ['weekdays-east.csv', 'weekdays-west.csv']
WEEKEND_FILES = ['saturdays-east.csv', 'saturdays-west.csv', 'sundays-east.csv', 'sundays-west.csv']

# Date ranges for regular schedules
DATE_RANGES = [
    (datetime(2025, 7, 14), datetime(2025, 7, 25), '2025-07-14'),
    (datetime(2025, 7, 28), datetime(2025, 8, 8), '2025-07-28'),
    (datetime(2025, 8, 11), datetime(2025, 8, 22), '2025-08-11'),
    (datetime(2025, 8, 25), datetime(2025, 8, 29), '2025-08-25'),
    (datetime(2025, 9, 1), datetime(2026, 2, 27), '2025-09-01'),
]

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function."""
    try:
        # Extract and validate parameters
        query_params = event.get('queryStringParameters', {}) or {}
        schedule_date = query_params.get('schedule_date', datetime.now().strftime('%Y-%m-%d'))
        last_updated = query_params.get('last_updated')
        
        parsed_date = _validate_date(schedule_date)
        if isinstance(parsed_date, dict):  # Error response
            return {
                'statusCode': 400,
                'body': json.dumps(parsed_date)
            }
            
        response_data = {}
        
        # Check for special schedules
        special_schedules = _get_special_schedules(schedule_date)
        if special_schedules:
            response_data['special_schedules'] = special_schedules
        
        # Handle regular schedules
        regular_schedules = _handle_regular_schedules(parsed_date, last_updated)
        response_data['regular_schedules'] = regular_schedules
        
        # Add message
        response_data['message'] = _generate_message(bool(special_schedules), regular_schedules, last_updated)
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def _validate_date(schedule_date: str) -> datetime:
    """Validate and parse the schedule date."""
    try:
        return datetime.strptime(schedule_date, '%Y-%m-%d')
    except ValueError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid date format. Use YYYY-MM-DD.'})
        }

def _get_special_schedules(schedule_date: str) -> Optional[Dict[str, Any]]:
    """Check for and return special schedule URLs if they exist."""
    special_base_path = f'schedules/special/{schedule_date}/'
    
    # Check if both special schedule files exist
    files_exist = [
        _check_file_exists(f'{special_base_path}{filename}')
        for filename in SPECIAL_SCHEDULE_FILES
    ]
    
    if not all(files_exist):
        return None
    
    # Generate presigned URLs
    urls = {}
    for filename in SPECIAL_SCHEDULE_FILES:
        key = f'{special_base_path}{filename}'
        url = _generate_presigned_url(key)
        # Convert filename to URL key
        url_key = filename.replace('special_schedule_', '').replace('.csv', '_url')
        urls[url_key] = url

    # Add PDF URL key
    pdf_key = f'{special_base_path}special_schedule.pdf'
    if _check_file_exists(pdf_key):
        urls['pdf_url'] = _generate_presigned_url(pdf_key)
    
    return {
        'schedule_date': schedule_date,
        **urls,
        'expires_in_seconds': PRESIGNED_URL_EXPIRATION
    }

def _handle_regular_schedules(date: datetime, last_updated: Optional[str]) -> Dict[str, Any]:
    """Handle regular schedules based on whether last_updated is provided."""
    if last_updated:
        return _check_regular_schedules_for_updates(date, last_updated)
    else:
        return _get_regular_schedule_urls(date)

def _check_regular_schedules_for_updates(date: datetime, last_updated_str: str) -> Dict[str, Any]:
    """Check if regular schedules need updating and return URLs if needed."""
    try:
        last_updated = _parse_last_updated(last_updated_str)
        if isinstance(last_updated, dict):  # Error response
            return {'error': last_updated['error']}
        
        regular_path = _get_regular_schedule_path(date)
        reference_key = f'{regular_path}/weekdays-east.csv'
        
        s3_last_modified = _get_file_last_modified(reference_key)
        if isinstance(s3_last_modified, dict):  # Error response
            return {'error': s3_last_modified['error']}
        
        if last_updated >= s3_last_modified:
            return {'updated': False}
        
        # Files are newer, return URLs
        urls = _generate_regular_schedule_urls(date)
        return {
            'updated': True,
            'last_modified': s3_last_modified.strftime('%Y-%m-%d %H:%M:%S'),
            'urls': urls,
            'expires_in_seconds': PRESIGNED_URL_EXPIRATION
        }
        
    except Exception as e:
        return {'error': f'Error checking regular schedules: {str(e)}'}

def _get_regular_schedule_urls(date: datetime) -> Dict[str, Any]:
    """Always return regular schedule URLs for the given date."""
    try:
        regular_path = _get_regular_schedule_path(date)
        reference_key = f'{regular_path}/weekdays-east.csv'
        
        s3_last_modified = _get_file_last_modified(reference_key)
        if isinstance(s3_last_modified, dict):  # Error response
            return {'error': s3_last_modified['error']}
        
        urls = _generate_regular_schedule_urls(date)
        return {
            'updated': True,
            'last_modified': s3_last_modified.strftime('%Y-%m-%d %H:%M:%S'),
            'urls': urls,
            'expires_in_seconds': PRESIGNED_URL_EXPIRATION
        }
        
    except Exception as e:
        return {'error': f'Error getting regular schedules: {str(e)}'}

def _generate_regular_schedule_urls(date: datetime) -> Dict[str, str]:
    """Generate presigned URLs for all regular schedule files."""
    regular_path = _get_regular_schedule_path(date)
    urls = {}
    
    # Generate URLs for weekday files (from date-specific path)
    for filename in WEEKDAY_FILES:
        file_key = f'{regular_path}/{filename}'
        if _check_file_exists(file_key):
            url = _generate_presigned_url(file_key)
            url_key = _filename_to_url_key(filename)
            urls[url_key] = url
    
    # Generate URLs for weekend files (from base regular path)
    for filename in WEEKEND_FILES:
        file_key = f'schedules/regular/{filename}'
        if _check_file_exists(file_key):
            url = _generate_presigned_url(file_key)
            url_key = _filename_to_url_key(filename)
            urls[url_key] = url
    
    return urls

def _get_regular_schedule_path(date: datetime) -> str:
    """Determine the file path for regular schedules based on the date."""
    for start_date, end_date, path_suffix in DATE_RANGES:
        if start_date <= date <= end_date:
            return f'schedules/regular/{path_suffix}'
    
    # For dates from March 2, 2026 onwards or fallback
    return 'schedules/regular'

def _parse_last_updated(last_updated_str: str) -> datetime:
    """Parse the last_updated parameter from various formats."""
    try:
        return datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Try ISO format and convert to naive datetime
            dt = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)
        except ValueError:
            return {'error': 'Invalid last_updated format. Use YYYY-MM-DD HH:MM:SS or ISO format.'}

def _get_file_last_modified(key: str) -> datetime:
    """Get the last modified time of a file in S3."""
    try:
        response = s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return response['LastModified'].replace(tzinfo=None)
    except Exception as e:
        return {'error': f'Could not get file metadata: {str(e)}'}

def _generate_message(has_special: bool, regular_schedules: Dict[str, Any], last_updated: Optional[str]) -> str:
    """Generate appropriate response message."""
    special_msg = "Special schedule found" if has_special else "No special schedule found for the given date"
    
    if 'error' in regular_schedules:
        regular_msg = "Regular schedule error occurred"
    elif last_updated:
        if regular_schedules.get('updated'):
            regular_msg = "Regular schedules updated"
        else:
            regular_msg = "Regular schedules are up to date"
    else:
        regular_msg = "Regular schedules provided"
    
    return f"{special_msg}. {regular_msg}"

def _filename_to_url_key(filename: str) -> str:
    """Convert filename to URL key format."""
    return filename.replace('.csv', '_url').replace('-', '_')

def _generate_presigned_url(key: str) -> str:
    """Generate a presigned URL for the given S3 key."""
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': key},
        ExpiresIn=PRESIGNED_URL_EXPIRATION
    )

def _check_file_exists(key: str) -> bool:
    """Check if a file exists in S3."""
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except Exception:
        return False
