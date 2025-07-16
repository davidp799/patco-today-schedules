# PATCO Schedule DynamoDB Structure

## Overview

This system processes PATCO train schedule CSV files and stores them in DynamoDB tables optimized for querying trips between any two stations. The structure supports your Android app's need to query trips from Station A to Station B efficiently.

## DynamoDB Table Design

### Tables
- `patco-schedules-eastbound` - Eastbound train schedules
- `patco-schedules-westbound` - Westbound train schedules

### Schema

**Primary Key:**
- `trip_id` (HASH) - Unique identifier for each train trip (e.g., "westbound-trip-0001")
- `segment_id` (RANGE) - Station pair identifier (e.g., "4-5" for segment from station 4 to station 5)

**Attributes:**
- `departure_time` - Time leaving the source station (e.g., "6:30A")
- `arrival_time` - Time arriving at destination station (e.g., "6:32A")
- `source_station_index` - Column index of source station (0-13)
- `destination_station_index` - Column index of destination station (0-13)
- `source_station_name` - Name of source station (e.g., "City Hall")
- `destination_station_name` - Name of destination station (e.g., "Broadway")
- `is_valid` - Boolean (false if either time is "CLOSED")
- `direction` - "eastbound" or "westbound"
- `created_at` - ISO timestamp when record was created

**Global Secondary Index:**
- `StationPairIndex`
  - HASH: `source_station_index`
  - RANGE: `destination_station_index`
  - Allows efficient querying by station pairs

## Station Mapping

### Westbound Direction (Index 0-13)
```
0:  15th-16th & Locust (Philadelphia)
1:  12th-13th & Locust (Philadelphia)
2:  9th-10th & Locust (Philadelphia)
3:  8th & Market (Philadelphia)
4:  City Hall (Philadelphia)
5:  Broadway (Camden)
6:  Franklin Square (Camden)
7:  Collingswood
8:  Westmont
9:  Haddonfield
10: Woodcrest
11: Ashland
12: Woodlyn
13: Lindenwold
```

### Eastbound Direction (Index 0-13)
```
0:  Lindenwold
1:  Woodlyn
2:  Ashland
3:  Woodcrest
4:  Haddonfield
5:  Westmont
6:  Collingswood
7:  Franklin Square (Camden)
8:  Broadway (Camden)
9:  City Hall (Philadelphia)
10: 8th & Market (Philadelphia)
11: 9th-10th & Locust (Philadelphia)
12: 12th-13th & Locust (Philadelphia)
13: 15th-16th & Locust (Philadelphia)
```

## Data Processing Flow

1. **CSV Upload**: Schedule CSV files are uploaded to S3
2. **Lambda Trigger**: StoreDataInDynamoDB Lambda processes each CSV
3. **Segmentation**: Each trip (row) is broken into station-to-station segments
4. **Storage**: All segments are stored in DynamoDB with proper indexing

## API Usage

### Query Endpoint
`GET /schedule/query`

**Parameters:**
- `source_station_index` (required) - Index of departure station (0-13)
- `destination_station_index` (required) - Index of arrival station (0-13)
- `direction` (required) - "eastbound" or "westbound"

**Example Request:**
```
GET /schedule/query?source_station_index=4&destination_station_index=9&direction=westbound
```

**Example Response:**
```json
{
  "trips": [
    {
      "departure_time": "5:08A",
      "arrival_time": "5:22A",
      "source_station": "City Hall",
      "destination_station": "Haddonfield",
      "trip_id": "westbound-trip-0005",
      "direction": "westbound"
    },
    {
      "departure_time": "5:23A",
      "arrival_time": "5:37A",
      "source_station": "City Hall",
      "destination_station": "Haddonfield",
      "trip_id": "westbound-trip-0006",
      "direction": "westbound"
    }
  ],
  "total_count": 83,
  "query": {
    "source_station_index": 4,
    "destination_station_index": 9,
    "direction": "westbound"
  }
}
```

## Android App Integration

### For your Android app, you would:

1. **Station Selection**: Present users with station names and map them to indices
2. **API Call**: Query the schedule API with source/destination indices and direction
3. **Display Results**: Show departure → arrival times in a list format

### Example Android Usage:
```kotlin
// User selects "City Hall" to "Haddonfield" westbound
val sourceIndex = 4  // City Hall in westbound direction
val destIndex = 9    // Haddonfield in westbound direction
val direction = "westbound"

// API call
val trips = apiService.getTrips(sourceIndex, destIndex, direction)

// Display in UI
trips.forEach { trip ->
    println("${trip.departureTime} → ${trip.arrivalTime}")
}
```

## Benefits of This Design

1. **Flexible Querying**: Can query between any two stations, not just adjacent ones
2. **Fast Lookups**: GSI enables efficient queries by station pairs
3. **Scalable**: DynamoDB scales automatically with your app's usage
4. **Comprehensive**: Handles complex PATCO schedules with closed stations
5. **Real-time Ready**: Can be updated with new schedules automatically

## Lambda Functions

### StoreDataInDynamoDB
- Processes CSV files from S3
- Creates segmented trip data
- Stores in appropriate DynamoDB table

### QueryScheduleAPI
- REST API for querying trips between stations
- Handles validation and error cases
- Returns formatted trip data for mobile apps

## Cost Considerations

- DynamoDB Pay-Per-Request billing recommended for variable usage
- GSI adds minimal cost for the query efficiency gained
- Lambda costs are minimal for this use case
- Consider implementing caching for frequently requested routes

## Testing

Run the test script to see how your data will be structured:
```bash
python3 scripts/test_dynamodb_processing.py
```

This processes your existing CSV files and shows example queries that your Android app would make.
