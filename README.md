# PATCO Today Schedules

Repository containing schedule files and AWS Lambda functions for the PATCO Today application. This system manages both regular and special train schedules for the Port Authority Transit Corporation (PATCO) rail system.

## Repository Structure

```
patco-today-schedules/
├── assets/                     # Schedule CSV files
│   ├── *.csv                   # Base regular schedules
│   └── YYYY-MM-DD/            # Date-specific schedule overrides
├── lambda/                     # AWS Lambda functions
│   ├── ConvertPdfToTxt/       # PDF to CSV conversion
│   ├── GetScheduleFiles/      # Schedule file retrieval API
│   ├── GetScheduleInformation/ # Schedule information scraper
│   └── SaveNewRegularSchedules/ # Regular schedule updater
└── README.md
```

## Schedule Files

### Regular Schedules

The [assets/](assets/) directory contains CSV files with train schedules:

- **Weekdays**: [`weekdays-east.csv`](assets/weekdays-east.csv), [`weekdays-west.csv`](assets/weekdays-west.csv)
- **Saturdays**: [`saturdays-east.csv`](assets/saturdays-east.csv), [`saturdays-west.csv`](assets/saturdays-west.csv)
- **Sundays**: [`sundays-east.csv`](assets/sundays-east.csv), [`sundays-west.csv`](assets/sundays-west.csv)

### Date-Specific Schedules

Some periods have modified schedules stored in date-specific folders:
- [2025-07-14/](assets/2025-07-14/) - July 14-25, 2025
- [2025-07-28/](assets/2025-07-28/) - July 28 - August 8, 2025
- [2025-08-11/](assets/2025-08-11/) - August 11-22, 2025
- [2025-08-25/](assets/2025-08-25/) - August 25-29, 2025
- [2025-09-01/](assets/2025-09-01/) - September 1, 2025 - February 27, 2026

### CSV Format

Each CSV file contains 14 columns representing train stations, with times in `HH:MM[A|P]` format or `CLOSED` for stations not served by particular trains.

## Lambda Functions

### 1. GetScheduleFiles

**File**: [`lambda/GetScheduleFiles/lambda_function.py`](lambda/GetScheduleFiles/lambda_function.py)

Main API endpoint that provides presigned URLs for schedule files.

**Features**:
- Returns special schedule URLs when available
- Provides regular schedule URLs based on date ranges
- Supports incremental updates via `last_updated` parameter
- Generates presigned S3 URLs with 1-hour expiration

**Usage**:
```bash
# Get schedules for a specific date
curl "https://api-endpoint/prod?schedule_date=2025-07-15"

# Check for updates since last fetch
curl "https://api-endpoint/prod?schedule_date=2025-07-15&last_updated=2025-07-01T10:00:00Z"
```

### 2. GetScheduleInformation

**File**: [`lambda/GetScheduleInformation/lambda_function.py`](lambda/GetScheduleInformation/lambda_function.py)

Scrapes PATCO's website for schedule information and detects updates.

**Features**:
- Monitors for special schedule announcements
- Checks regular schedule effective dates
- Downloads and saves special schedule PDFs to S3
- Returns structured schedule information

### 3. ConvertPdfToTxt

**File**: [`lambda/ConvertPdfToTxt/lambda_function.py`](lambda/ConvertPdfToTxt/lambda_function.py)

Converts special schedule PDFs to CSV format.

**Features**:
- Downloads PDFs from PATCO website
- Extracts text using PyMuPDF
- Processes and cleans extracted text
- Splits into westbound/eastbound schedules
- Normalizes to 14-column CSV format
- Handles missing AM/PM suffixes

**Dependencies**: See [`requirements.txt`](lambda/ConvertPdfToTxt/requirements.txt)

### 4. SaveNewRegularSchedules

**File**: [`lambda/SaveNewRegularSchedules/lambda_function.py`](lambda/SaveNewRegularSchedules/lambda_function.py)

Downloads and extracts regular schedule files from PATCO's GTFS data.

**Features**:
- Downloads ZIP file from PATCO developers portal
- Extracts and uploads files to S3
- Maintains regular schedule updates

## API Response Examples

### Special Schedule Response
```json
{
  "message": "Special schedule found",
  "special_schedules": {
    "schedule_date": "2025-07-15",
    "eastbound_url": "https://s3-presigned-url",
    "westbound_url": "https://s3-presigned-url",
    "expires_in_seconds": 3600
  }
}
```

### Regular Schedule Response
```json
{
  "message": "Regular schedules updated",
  "regular_schedules": {
    "updated": true,
    "last_modified": "2025-07-10 14:30:00",
    "urls": {
      "weekdays_east_url": "https://s3-presigned-url",
      "weekdays_west_url": "https://s3-presigned-url",
      "saturdays_east_url": "https://s3-presigned-url",
      "saturdays_west_url": "https://s3-presigned-url",
      "sundays_east_url": "https://s3-presigned-url",
      "sundays_west_url": "https://s3-presigned-url"
    },
    "expires_in_seconds": 3600
  }
}
```

## Sample Data

- [`lambda/GetScheduleFiles/sample-data.json`](lambda/GetScheduleFiles/sample-data.json) - Example API requests and responses
- [`lambda/GetScheduleFiles/samples.json`](lambda/GetScheduleFiles/samples.json) - Real API response samples

## AWS Infrastructure

The system uses:
- **S3**: Storage for schedule files and PDFs
- **Lambda**: Serverless functions for processing
- **API Gateway**: REST API endpoint
- **CloudWatch**: Logging and monitoring

## Development

### Local Testing

The ConvertPdfToTxt function supports local testing:

```python
# Set debug mode in event
test_event = {
    "debug_mode": True,
    "file_name": "TW_2025-07-15",
    "special_schedule_pdf_url": "https://www.ridepatco.org/publish/library/TW_2025-07-15.pdf"
}
```

### Date Range Configuration

Regular schedule date ranges are configured in [`lambda/GetScheduleFiles/lambda_function.py`](lambda/GetScheduleFiles/lambda_function.py):

```python
DATE_RANGES = [
    (datetime(2025, 7, 14), datetime(2025, 7, 25), '2025-07-14'),
    (datetime(2025, 7, 28), datetime(2025, 8, 8), '2025-07-28'),
    # ... additional ranges
]
```

## License

This repository contains schedule data and tools for the PATCO Today application.