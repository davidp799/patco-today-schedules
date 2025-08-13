# PATCO Today Schedules

Hybrid cloud-edge system for processing PATCO (Port Authority Transit Corporation) train schedules. This repository contains both AWS Lambda functions for web scraping and Rock Pi edge processing components for PDF conversion and CSV generation.

## Architecture Overview

This system uses a cost-optimized hybrid approach:
- **AWS Lambda**: Web scraping (bypasses IP restrictions) - 14% of original cost
- **Rock Pi 4B+**: Heavy processing (PDF conversion, CSV generation) - 86% cost reduction
- **EventBridge**: Automated daily scheduling with 5-minute delays
- **S3 Storage**: Centralized data exchange between components

## Repository Structure

```
patco-today-schedules/
├── assets/                     # Schedule CSV files (output)
│   ├── *.csv                   # Base regular schedules
│   └── YYYY-MM-DD/            # Date-specific schedule overrides
├── lambda/                     # AWS Lambda functions
│   ├── GetScheduleFiles/      # Schedule file retrieval API
│   └── GetScheduleInformation/ # Web scraping (saves to S3)
├── rockpi/                     # Rock Pi edge processing
│   ├── src/                   # Python processing modules
│   ├── schedules/             # Local schedule cache
│   └── requirements.txt       # Python dependencies
├── deployment/                 # Setup and deployment scripts
└── machines/                   # AWS Step Functions (legacy)
```

## Hybrid Workflow

### Daily Automation Schedule
- **12:00 AM UTC**: Lambda scrapes PATCO website, saves results to S3
- **12:05 AM UTC**: Rock Pi reads Lambda output, processes PDFs, generates CSVs
- **12:15 AM UTC**: Updated schedules available in assets/ directory

### Components

#### AWS Lambda Functions

**GetScheduleInformation** (`lambda/GetScheduleInformation/`)
- Scrapes PATCO website for schedule updates
- Bypasses IP restrictions that block residential connections
- Saves JSON results to S3 at `lambda-outputs/schedule-info/YYYY-MM-DD/`
- Triggered daily by EventBridge at midnight UTC

**GetScheduleFiles** (`lambda/GetScheduleFiles/`)
- API endpoint for mobile app integration
- Returns presigned S3 URLs for schedule files
- Supports date-specific and regular schedule requests

#### Rock Pi Processing (`rockpi/`)

**read_lambda_output.py**
- Reads Lambda scraping results from S3
- Downloads special schedule PDFs
- Coordinates processing workflow

**convert_pdf_to_csv.py** 
- Converts PDF schedules to CSV format using PyMuPDF
- Handles text extraction and schedule parsing
- Normalizes to 14-column format

**save_regular_schedules.py**
- Downloads GTFS data from PATCO developers portal
- Extracts and processes regular schedule updates

## Deployment

### Prerequisites
- Rock Pi 4B+ with Armbian OS
- Python 3.x with virtual environment
- AWS CLI configured with appropriate permissions
- SSH access to Rock Pi device

### Setup Instructions

1. **Deploy to Rock Pi**:
   ```bash
   # Windows PowerShell
   .\deployment\deploy_to_rockpi.ps1

   # Linux/macOS
   ./deployment/deploy_to_rockpi.sh
   ```

2. **Configure Lambda Triggers**:
   ```bash
   ./deployment/setup_lambda_trigger.sh
   ```

3. **Setup Rock Pi Cron Jobs**:
   ```bash
   ./deployment/setup_rockpi_cron.sh
   ```

### Manual Deployment
For manual setup, see `deployment/deploy_manual.sh` for step-by-step instructions.

## Schedule Files

### Output Structure

The [assets/](assets/) directory contains processed CSV files:

- **Regular Schedules**: `weekdays-*.csv`, `saturdays-*.csv`, `sundays-*.csv`
- **Special Schedules**: Date-specific folders like `2025-07-14/`
- **Format**: 14 columns representing PATCO stations, times in `HH:MM[A|P]` format

### API Integration

The GetScheduleFiles Lambda provides API access:

```bash
# Get schedules for specific date
curl "https://api-endpoint/prod?schedule_date=2025-07-15"

# Check for updates since last fetch  
curl "https://api-endpoint/prod?schedule_date=2025-07-15&last_updated=2025-07-01T10:00:00Z"
```

## Cost Analysis

Migration from pure AWS Lambda to hybrid Rock Pi system:
- **Before**: ~$50/month for heavy PDF processing
- **After**: ~$7/month (AWS Lambda for scraping only)  
- **Savings**: 86% cost reduction
- **ROI**: Rock Pi hardware cost recovered in 3 months

## Troubleshooting

### Common Issues

**Rock Pi can't reach PATCO website**
- Solution: Hybrid architecture uses Lambda for web scraping
- Rock Pi reads results from S3 instead of direct scraping

**Missing dependencies on Rock Pi**
- Run: `pip install -r rockpi/requirements.txt`
- Ensure virtual environment is activated

**EventBridge not triggering**
- Check IAM permissions for Lambda execution
- Verify cron expression: `cron(0 0 * * ? *)`

### Logs and Monitoring

- **Lambda Logs**: CloudWatch Logs for web scraping status
- **Rock Pi Logs**: Local log files in `rockpi/logs/`
- **Cron Status**: Check with `crontab -l` and `systemctl status cron`

## Development

### Local Testing

Test Rock Pi components locally:
```bash
cd rockpi
source venv/bin/activate
python src/read_lambda_output.py --debug
```

### Adding New Processing

1. Add processing logic to `rockpi/src/`
2. Update cron schedule in `deployment/setup_rockpi_cron.sh`
3. Test with manual deployment script

## License

See [`LICENSE.md`](LICENSE.md) for license details.
