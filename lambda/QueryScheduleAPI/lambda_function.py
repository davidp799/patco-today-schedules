import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    API endpoint for querying PATCO schedule trips between stations.
    
    Expected query parameters:
    - source_station_index: Index of source station (0-13)
    - destination_station_index: Index of destination station (0-13) 
    - direction: 'eastbound' or 'westbound'
    
    Returns JSON with list of available trips.
    """
    try:
        # Extract query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        source_station_index = int(query_params.get('source_station_index', 0))
        destination_station_index = int(query_params.get('destination_station_index', 1))
        direction = query_params.get('direction', 'westbound').lower()
        
        # Validate parameters
        if direction not in ['eastbound', 'westbound']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Direction must be eastbound or westbound'})
            }
        
        if not (0 <= source_station_index <= 13 and 0 <= destination_station_index <= 13):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Station indices must be between 0 and 13'})
            }
        
        if source_station_index == destination_station_index:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Source and destination stations must be different'})
            }
        
        # Query DynamoDB for trips
        trips = query_trips_between_stations(
            source_station_index, 
            destination_station_index, 
            direction
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'trips': trips,
                'total_count': len(trips),
                'query': {
                    'source_station_index': source_station_index,
                    'destination_station_index': destination_station_index,
                    'direction': direction
                }
            }, cls=DecimalEncoder)
        }
        
    except ValueError as e:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Invalid parameter: {str(e)}'})
        }
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }

def query_trips_between_stations(source_station_index, destination_station_index, direction):
    """
    Query DynamoDB for trips between two stations.
    
    This function handles multi-segment trips by:
    1. Getting all trips that have segments starting from source station
    2. Checking if those trips also reach the destination station
    3. Extracting departure time from source and arrival time at destination
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = f'patco-schedules-{direction}'
    table = dynamodb.Table(table_name)
    
    try:
        # First, scan for all trips (in production, you'd want better indexing)
        response = table.scan()
        items = response['Items']
        
        # Continue scanning if there are more items
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        
        # Group segments by trip_id
        trips = {}
        for item in items:
            trip_id = item['trip_id']
            if trip_id not in trips:
                trips[trip_id] = []
            trips[trip_id].append(item)
        
        # Find valid trips between the specified stations
        valid_trips = []
        
        for trip_id, segments in trips.items():
            # Sort segments by source station index
            segments.sort(key=lambda x: int(x['source_station_index']))
            
            source_time = None
            destination_time = None
            source_station_name = None
            destination_station_name = None
            
            # Find departure time at source station
            for segment in segments:
                if (int(segment['source_station_index']) == source_station_index and 
                    segment['is_valid'] and 
                    segment['departure_time'] != 'CLOSED'):
                    source_time = segment['departure_time']
                    source_station_name = segment['source_station_name']
                    break
            
            # Find arrival time at destination station
            for segment in segments:
                if (int(segment['destination_station_index']) == destination_station_index and 
                    segment['is_valid'] and 
                    segment['arrival_time'] != 'CLOSED'):
                    destination_time = segment['arrival_time']
                    destination_station_name = segment['destination_station_name']
                    break
            
            # If we found both times and the trip makes sense (source before destination)
            if (source_time and destination_time and 
                source_station_name and destination_station_name):
                
                # For westbound: source index should be less than destination index
                # For eastbound: source index should be greater than destination index
                valid_direction = False
                if direction == 'westbound' and source_station_index < destination_station_index:
                    valid_direction = True
                elif direction == 'eastbound' and source_station_index > destination_station_index:
                    valid_direction = True
                
                if valid_direction:
                    valid_trips.append({
                        'departure_time': source_time,
                        'arrival_time': destination_time,
                        'source_station': source_station_name,
                        'destination_station': destination_station_name,
                        'trip_id': trip_id,
                        'direction': direction
                    })
        
        # Sort trips by departure time
        valid_trips.sort(key=lambda x: convert_time_to_sortable(x['departure_time']))
        
        return valid_trips
        
    except Exception as e:
        print(f"Error querying DynamoDB: {str(e)}")
        raise

def convert_time_to_sortable(time_str):
    """
    Convert time string like '6:30A' to a sortable format.
    Returns minutes since midnight.
    """
    try:
        if time_str == 'CLOSED' or not time_str:
            return 9999  # Put closed times at the end
        
        # Remove 'A' or 'P' and parse
        if time_str.endswith('A') or time_str.endswith('P'):
            am_pm = time_str[-1]
            time_part = time_str[:-1]
        else:
            return 9999  # Invalid format
        
        # Parse hour and minute
        if ':' in time_part:
            hour, minute = map(int, time_part.split(':'))
        else:
            hour = int(time_part)
            minute = 0
        
        # Convert to 24-hour format
        if am_pm == 'P' and hour != 12:
            hour += 12
        elif am_pm == 'A' and hour == 12:
            hour = 0
        
        # Return minutes since midnight
        return hour * 60 + minute
        
    except (ValueError, IndexError):
        return 9999  # Put invalid times at the end

# Example usage for testing
if __name__ == "__main__":
    # Test event for City Hall (index 4) to Haddonfield (index 9) westbound
    test_event = {
        'queryStringParameters': {
            'source_station_index': '4',
            'destination_station_index': '9', 
            'direction': 'westbound'
        }
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
