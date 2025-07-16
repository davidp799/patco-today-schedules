#!/usr/bin/env python3
"""
Test script to process local CSV files and demonstrate DynamoDB structure.
This script processes your CSV files locally without requiring AWS credentials.
"""

import csv
import json
from datetime import datetime
import os

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
# PATCO_STATIONS_EASTBOUND = list(PATCO_STATIONS_WESTBOUND)

def process_csv_file(csv_file_path, direction):
    """
    Process a CSV file and return the data structure that would be stored in DynamoDB.
    """
    stations = PATCO_STATIONS_EASTBOUND if direction == 'eastbound' else PATCO_STATIONS_WESTBOUND
    
    records = []
    trip_counter = 0
    
    print(f"\nProcessing {direction} CSV file: {csv_file_path}")
    print(f"Station order: {stations}")
    print("-" * 80)
    
    with open(csv_file_path, 'r') as file:
        csv_reader = csv.reader(file)
        
        for row in csv_reader:
            trip_counter += 1
            trip_id = f"{direction}-trip-{trip_counter:04d}"
            
            # Only show details for first 3 trips
            if trip_counter <= 3:
                print(f"\nTrip {trip_counter} ({trip_id}):")
                print(f"Raw times: {row}")
            
            # Create segments for each station pair
            trip_segments = []
            for i in range(len(row) - 1):
                source_time = row[i].strip()
                destination_time = row[i + 1].strip()
                
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
                
                trip_segments.append(segment)
                records.append(segment)
                
                # Print valid segments for first 3 trips only
                if trip_counter <= 3 and segment['is_valid']:
                    print(f"  {stations[i]} -> {stations[i+1]}: {source_time} -> {destination_time}")
            
            # Show continuation message after 3rd trip
            if trip_counter == 3:
                print(f"\n... (continuing to process remaining trips silently)")
    
    
    print(f"\nTotal trips processed: {trip_counter}")
    print(f"Total segments created: {len(records)}")
    print(f"Valid segments: {len([r for r in records if r['is_valid']])}")
    
    return records

def query_trips_between_stations(records, source_station_index, destination_station_index):
    """
    Simulate querying trips between two stations.
    This finds trips that go from source to destination, even if they're not consecutive stations.
    """
    trips = {}  # Group by trip_id
    
    # First, organize records by trip_id
    for record in records:
        trip_id = record['trip_id']
        if trip_id not in trips:
            trips[trip_id] = []
        trips[trip_id].append(record)
    
    matching_trips = []
    
    # For each trip, check if it goes from source to destination
    for trip_id, segments in trips.items():
        # Sort segments by source station index
        segments.sort(key=lambda x: x['source_station_index'])
        
        source_time = None
        destination_time = None
        
        # Find the departure time at source station
        for segment in segments:
            if segment['source_station_index'] == source_station_index and segment['is_valid']:
                source_time = segment['departure_time']
                break
        
        # Find the arrival time at destination station  
        for segment in segments:
            if segment['destination_station_index'] == destination_station_index and segment['is_valid']:
                destination_time = segment['arrival_time']
                break
        
        # If we found both times, this trip works
        if source_time and destination_time and source_time != 'CLOSED' and destination_time != 'CLOSED':
            # Get station names
            source_station = None
            dest_station = None
            for segment in segments:
                if segment['source_station_index'] == source_station_index:
                    source_station = segment['source_station_name']
                if segment['destination_station_index'] == destination_station_index:
                    dest_station = segment['destination_station_name']
                    
            if source_station and dest_station:
                matching_trips.append({
                    'departure_time': source_time,
                    'arrival_time': destination_time,
                    'source_station': source_station,
                    'destination_station': dest_station,
                    'trip_id': trip_id
                })
    
    return matching_trips

def main():
    """
    Main function to test CSV processing with your files.
    """
    # File paths
    westbound_csv = "/home/david/Github/patco-today-schedules/output/TW_2025-07-15_westbound.csv"
    eastbound_csv = "/home/david/Github/patco-today-schedules/output/TW_2025-07-15_eastbound.csv"
    
    # Process both files
    westbound_records = process_csv_file(westbound_csv, 'westbound')
    eastbound_records = process_csv_file(eastbound_csv, 'eastbound')
    
    # Example query: trips from City Hall (index 4) to Haddonfield (index 9) westbound
    print("\n" + "="*80)
    print("EXAMPLE QUERY: City Hall to Haddonfield (Westbound)")
    print("="*80)
    
    source_idx = 4  # City Hall
    dest_idx = 9    # Haddonfield
    
    trips = query_trips_between_stations(westbound_records, source_idx, dest_idx)
    
    print(f"Found {len(trips)} trips from {PATCO_STATIONS_WESTBOUND[source_idx]} to {PATCO_STATIONS_WESTBOUND[dest_idx]}")
    print("\nTrip options:")
    for i, trip in enumerate(trips[:10]):  # Show first 10 trips
        print(f"{i+1:2d}. {trip['departure_time']} -> {trip['arrival_time']} (Trip: {trip['trip_id']})")
    
    if len(trips) > 10:
        print(f"... and {len(trips) - 10} more trips")
    
    # Example query: trips from Lindenwold (index 0) to 8th & Market (index 10) eastbound
    print("\n" + "="*80)
    print("EXAMPLE QUERY: Lindenwold to 8th & Market (Eastbound)")
    print("="*80)
    
    source_idx = 0   # Lindenwold (first station eastbound)
    dest_idx = 10    # 8th & Market
    
    trips = query_trips_between_stations(eastbound_records, source_idx, dest_idx)
    
    print(f"Found {len(trips)} trips from {PATCO_STATIONS_EASTBOUND[source_idx]} to {PATCO_STATIONS_EASTBOUND[dest_idx]}")
    print("\nTrip options:")
    for i, trip in enumerate(trips[:10]):  # Show first 10 trips
        print(f"{i+1:2d}. {trip['departure_time']} -> {trip['arrival_time']} (Trip: {trip['trip_id']})")
    
    if len(trips) > 10:
        print(f"... and {len(trips) - 10} more trips")
    
    # Save sample data to JSON for inspection
    sample_data = {
        'westbound_sample': westbound_records[:5],  # First 5 records
        'eastbound_sample': eastbound_records[:5],
        'query_example': {
            'source_station': PATCO_STATIONS_WESTBOUND[4],
            'destination_station': PATCO_STATIONS_WESTBOUND[9],
            'trips': trips[:5]
        }
    }
    
    with open('/home/david/Github/patco-today-schedules/sample_dynamodb_data.json', 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"\nSample data saved to: sample_dynamodb_data.json")
    print("\nDynamoDB Table Structure Summary:")
    print("- Primary Key: trip_id (HASH) + segment_id (RANGE)")
    print("- Global Secondary Index: source_station_index (HASH) + destination_station_index (RANGE)")
    print("- This allows efficient querying by station pairs for your Android app")

if __name__ == "__main__":
    main()
