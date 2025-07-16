import json
import boto3
import csv
from decimal import Decimal
from datetime import datetime
import uuid

# PATCO station names in order (westbound direction)
PATCO_STATIONS_WESTBOUND = [
    "15th-16th & Locust",
    "12th-13th & Locust", 
    "9th-10th & Locust",
    "8th & Market",
    "City Hall",
    "Broadway",
    "Franklin Square",
    "Collingswood",
    "Westmont",
    "Haddonfield",
    "Woodcrest",
    "Ashland",
    "Woodlyn",
    "Lindenwold"
]

# For eastbound, reverse the station order
PATCO_STATIONS_EASTBOUND = list(reversed(PATCO_STATIONS_WESTBOUND))

def lambda_handler(event, context):
    """
    Process CSV schedule files and store in DynamoDB tables.
    Expects S3 event with CSV file uploads.
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        s3 = boto3.client('s3')
        
        # Process each record in the event
        for record in event.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Determine direction and table name from filename
            if 'eastbound' in key.lower():
                table_name = 'patco-schedules-eastbound'
                stations = PATCO_STATIONS_EASTBOUND
                direction = 'eastbound'
            elif 'westbound' in key.lower():
                table_name = 'patco-schedules-westbound'
                stations = PATCO_STATIONS_WESTBOUND
                direction = 'westbound'
            else:
                print(f"Skipping file {key} - not recognized as eastbound or westbound")
                continue
                
            # Get the CSV file from S3
            response = s3.get_object(Bucket=bucket, Key=key)
            csv_content = response['Body'].read().decode('utf-8')
            
            # Process the CSV and store in DynamoDB
            process_csv_to_dynamodb(csv_content, table_name, stations, direction)
            
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed schedule files')
        }
        
    except Exception as e:
        print(f"Error processing files: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def process_csv_to_dynamodb(csv_content, table_name, stations, direction):
    """
    Process CSV content and store schedule data in DynamoDB.
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Parse CSV content
    csv_reader = csv.reader(csv_content.strip().split('\n'))
    
    batch_items = []
    trip_counter = 0
    
    for row in csv_reader:
        trip_counter += 1
        trip_id = f"{direction}-trip-{trip_counter:04d}"
        
        # Create segments for each station pair
        for i in range(len(row) - 1):
            source_time = row[i].strip()
            destination_time = row[i + 1].strip()
            
            # Create segment record
            segment = {
                'trip_id': trip_id,
                'segment_id': f"{i}-{i+1}",
                'departure_time': source_time,
                'arrival_time': destination_time,
                'source_station_index': i,
                'destination_station_index': i + 1,
                'source_station_name': stations[i],
                'destination_station_name': stations[i + 1],
                'is_valid': source_time != 'CLOSED' and destination_time != 'CLOSED',
                'direction': direction,
                'created_at': datetime.utcnow().isoformat()
            }
            
            batch_items.append(segment)
            
            # Batch write when we have 25 items (DynamoDB limit)
            if len(batch_items) >= 25:
                batch_write_to_dynamodb(table, batch_items)
                batch_items = []
    
    # Write remaining items
    if batch_items:
        batch_write_to_dynamodb(table, batch_items)
    
    print(f"Processed {trip_counter} trips for {direction} direction")

def batch_write_to_dynamodb(table, items):
    """
    Batch write items to DynamoDB with retry logic.
    """
    try:
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
    except Exception as e:
        print(f"Error writing batch to DynamoDB: {str(e)}")
        raise

def create_tables_if_not_exist():
    """
    Create DynamoDB tables for eastbound and westbound schedules if they don't exist.
    This function can be called separately to set up the infrastructure.
    """
    dynamodb = boto3.resource('dynamodb')
    
    tables_config = [
        {
            'name': 'patco-schedules-eastbound',
            'description': 'PATCO eastbound train schedules'
        },
        {
            'name': 'patco-schedules-westbound', 
            'description': 'PATCO westbound train schedules'
        }
    ]
    
    for config in tables_config:
        try:
            table = dynamodb.create_table(
                TableName=config['name'],
                KeySchema=[
                    {
                        'AttributeName': 'trip_id',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'segment_id',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'trip_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'segment_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'source_station_index',
                        'AttributeType': 'N'
                    },
                    {
                        'AttributeName': 'destination_station_index',
                        'AttributeType': 'N'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'StationPairIndex',
                        'KeySchema': [
                            {
                                'AttributeName': 'source_station_index',
                                'KeyType': 'HASH'
                            },
                            {
                                'AttributeName': 'destination_station_index',
                                'KeyType': 'RANGE'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            print(f"Created table: {config['name']}")
            
        except dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {config['name']} already exists")
        except Exception as e:
            print(f"Error creating table {config['name']}: {str(e)}")

# Example query functions for your Android app
def query_trips_between_stations(source_station_index, destination_station_index, direction='westbound'):
    """
    Query trips between two stations.
    Returns all available trips with departure and arrival times.
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = f'patco-schedules-{direction}'
    table = dynamodb.Table(table_name)
    
    try:
        # Use GSI to query by station indices
        response = table.query(
            IndexName='StationPairIndex',
            KeyConditionExpression='source_station_index = :src AND destination_station_index = :dest',
            ExpressionAttributeValues={
                ':src': source_station_index,
                ':dest': destination_station_index
            },
            FilterExpression='is_valid = :valid',
            ExpressionAttributeValues={
                ':valid': True
            }
        )
        
        # Format results for your Android app
        trips = []
        for item in response['Items']:
            trips.append({
                'departure_time': item['departure_time'],
                'arrival_time': item['arrival_time'],
                'source_station': item['source_station_name'],
                'destination_station': item['destination_station_name'],
                'trip_id': item['trip_id']
            })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'trips': trips,
                'total_count': len(trips)
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error querying trips: {str(e)}')
        }
