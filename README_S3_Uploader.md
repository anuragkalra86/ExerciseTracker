# S3 Uploader Service

An automated service that monitors a local directory for MP4 files and uploads them to Amazon S3, then deletes the local files after successful upload.

## Features

- **File System Watcher**: Monitors directory for new MP4 files in real-time
- **Automatic Upload**: Uploads files to S3 with retry logic and exponential backoff
- **Safety Checks**: Verifies upload success before deleting local files
- **Configurable**: All settings managed through configuration file
- **Logging**: Comprehensive logging with rotation support
- **Graceful Shutdown**: Handles SIGINT and SIGTERM signals

## Setup

### 1. Create Virtual Environment and Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: On Raspberry Pi OS and other Debian-based systems, you may need to install `python3-venv` first:
```bash
sudo apt update
sudo apt install python3-venv python3-full
```

### 2. Configure AWS Credentials

Ensure your AWS credentials are configured. The service uses the default AWS credential chain:

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### 3. Configure S3 Bucket

Create an S3 bucket or use an existing one. Update the bucket name in `s3_uploader_config.ini`.

### 4. Update Configuration

Edit `s3_uploader_config.ini` to match your setup:

```ini
[s3]
bucket_name = your-bucket-name
region = us-east-1

[local]
video_directory = /path/to/your/video/directory
```

### 5. Create Log Directory

```bash
mkdir -p /home/orange/gym/logs
```

## Usage

### Start the Service

```bash
# Activate virtual environment first
source venv/bin/activate

# Start the service
python3 s3_uploader.py
```

### Run as Background Service

```bash
# Activate virtual environment and run in background
source venv/bin/activate
nohup python3 s3_uploader.py &
```

### Stop the Service

Press `Ctrl+C` or send SIGTERM signal:

```bash
kill -TERM <process_id>
```

## Configuration Options

### S3 Settings
- `bucket_name`: Your S3 bucket name
- `region`: AWS region for your bucket

### Local Settings
- `video_directory`: Directory to monitor for MP4 files
- `file_extensions`: Comma-separated list of file extensions to monitor

### Upload Settings
- `max_retries`: Maximum number of retry attempts (default: 3)
- `initial_retry_delay`: Initial retry delay in seconds (default: 5)
- `file_age_threshold`: Minimum file age before upload (default: 2 seconds)

### Logging Settings
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `log_file`: Path to log file (empty = console only)
- `max_log_size`: Maximum log file size in MB
- `log_backup_count`: Number of log files to keep

## How It Works

1. **File Detection**: Service monitors the configured directory for new MP4 files
2. **File Readiness**: Waits for file to be stable (no modifications for threshold time)
3. **Upload**: Uploads file to S3 with retry logic if failures occur
4. **Verification**: Verifies upload by checking file size matches
5. **Cleanup**: Deletes local file only after successful upload verification

## Logging

The service provides comprehensive logging:

- **INFO**: Normal operations (file detected, upload started/completed)
- **WARNING**: Non-critical issues (upload verification failed, retrying)
- **ERROR**: Serious issues (upload failed, S3 connection problems)
- **DEBUG**: Detailed information for troubleshooting

## Monitoring

Check the logs to monitor service health:

```bash
tail -f /home/orange/gym/logs/s3_uploader.log
```

## Error Handling

The service handles various error scenarios:

- **Network Issues**: Automatic retry with exponential backoff
- **S3 Service Errors**: Retry with configurable attempts
- **File System Errors**: Logged with detailed error messages
- **Configuration Errors**: Service fails to start with clear error message

## Integration with Motion Recorder

This service is designed to work alongside the `motion_record.py` script:

1. `motion_record.py` records video clips to `/home/orange/gym/videos/`
2. S3 uploader detects new files and uploads them automatically
3. Local files are cleaned up after successful upload
4. Both services run independently without blocking each other

## Troubleshooting

### Service Won't Start
- Check if configuration file exists
- Verify AWS credentials are configured
- Ensure S3 bucket exists and is accessible
- Check directory permissions

### Files Not Uploading
- Check AWS credentials and permissions
- Verify S3 bucket name and region
- Check network connectivity
- Review log files for error details

### High CPU Usage
- Increase `file_age_threshold` if files are being processed too quickly
- Check if video directory has excessive file creation activity

## Systemd Service (Optional)

To run as a system service, create `/etc/systemd/system/s3-uploader.service`:

```ini
[Unit]
Description=S3 Video Uploader Service
After=network.target

[Service]
Type=simple
User=orange
WorkingDirectory=/home/orange/Code/ExerciseTracker
ExecStart=/home/orange/Code/ExerciseTracker/venv/bin/python s3_uploader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl enable s3-uploader.service
sudo systemctl start s3-uploader.service
``` 