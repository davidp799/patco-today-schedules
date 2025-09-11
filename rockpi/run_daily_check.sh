#!/bin/bash

# Main execution script for daily PATCO schedule processing
# This script replicates the AWS Step Function workflow

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Set up logging
LOG_FILE="logs/daily_run_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "Starting PATCO schedule processing at $(date)" | tee "$LOG_FILE"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to upload log file to S3
upload_log() {
    if [ -f "$LOG_FILE" ]; then
        log "Uploading log file to S3..."
        # Get bucket name from config, similar to test_setup.sh
        BUCKET=$(python3 -c "import json; print(json.load(open('config.json'))['s3_bucket'])" 2>/dev/null)
        
        if [ -z "$BUCKET" ]; then
            log "ERROR: S3 bucket name not found in config.json. Skipping log upload."
            return
        fi
        
        aws s3 cp "$LOG_FILE" "s3://$BUCKET/logs/" >> "$LOG_FILE" 2>&1 || log "ERROR: Failed to upload log file to S3."
    fi
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    log "Daily processing failed at $(date)"
    upload_log
    exit 1
}

# Trap errors
trap 'handle_error "Script failed on line $LINENO"' ERR

log "Step 1: Reading schedule information from AWS Lambda output..."
python3 src/read_lambda_output.py >> "$LOG_FILE" 2>&1 || handle_error "Failed to read Lambda output"

# Check if we found any special or new schedules
if [ -f "temp/schedule_info.json" ]; then
    log "Schedule information retrieved successfully"
    
    # Parse the JSON to check for special schedules and new regular schedules
    HAS_SPECIAL=$(python3 -c "import json; data=json.load(open('temp/schedule_info.json')); print(data.get('has_special_schedule', False))")
    HAS_NEW_REGULAR=$(python3 -c "import json; data=json.load(open('temp/schedule_info.json')); print(data.get('has_new_regular_schedule', False))")
    
    log "Has special schedule: $HAS_SPECIAL"
    log "Has new regular schedule: $HAS_NEW_REGULAR"
    
    # Process special schedules if found
    if [ "$HAS_SPECIAL" = "True" ]; then
        log "Step 2a: Processing special schedule..."
        python3 src/process_special_schedule.py >> "$LOG_FILE" 2>&1 || handle_error "Failed to process special schedule"
        log "Step 2b: Converting special schedule PDF to CSV..."
        python3 src/convert_pdf_to_csv.py >> "$LOG_FILE" 2>&1 || handle_error "Failed to convert PDF to CSV"
        log "Special schedule processed and converted successfully"
    else
        log "Step 2a: No special schedule found, skipping PDF processing"
    fi
    
    # Process new regular schedules if found
    if [ "$HAS_NEW_REGULAR" = "True" ]; then
        log "Step 2b: Saving new regular schedules..."
        python3 src/save_regular_schedules.py >> "$LOG_FILE" 2>&1 || handle_error "Failed to save regular schedules"
        log "New regular schedules saved successfully"
    else
        log "Step 2b: No new regular schedules found, skipping"
    fi
    
    # Clean up temporary files
    log "Cleaning up temporary files..."
    rm -rf temp/
    
else
    handle_error "Failed to create schedule information file"
fi

log "Daily processing completed successfully at $(date)"

# Upload the log file to S3 on successful completion
upload_log

# Keep only the last 30 days of logs
find logs/ -name "daily_run_*.log" -mtime +30 -delete 2>/dev/null || true

log "Log cleanup completed"
