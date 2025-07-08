#!/usr/bin/env python3
"""
S3 Uploader Service
Monitors local directory for MP4 files and uploads them to S3 bucket.
Deletes local files after successful upload.
"""

import os
import sys
import time
import logging
import signal
from pathlib import Path
from datetime import datetime
from configparser import ConfigParser
from logging.handlers import RotatingFileHandler

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class S3UploaderConfig:
    """Configuration manager for S3 Uploader"""
    
    def __init__(self, config_file='s3_uploader_config.ini'):
        self.config = ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        self.config.read(self.config_file)
        
        # Validate required sections
        required_sections = ['s3', 'local', 'upload']
        for section in required_sections:
            if not self.config.has_section(section):
                raise ValueError(f"Required section '{section}' missing from config file")
    
    def get_s3_bucket(self):
        return self.config.get('s3', 'bucket_name')
    
    def get_s3_region(self):
        return self.config.get('s3', 'region', fallback='us-east-1')
    
    def get_video_directory(self):
        return self.config.get('local', 'video_directory')
    
    def get_file_extensions(self):
        extensions = self.config.get('local', 'file_extensions', fallback='.mp4,.MP4')
        return [ext.strip() for ext in extensions.split(',')]
    
    def get_max_retries(self):
        return self.config.getint('upload', 'max_retries', fallback=3)
    
    def get_initial_retry_delay(self):
        return self.config.getint('upload', 'initial_retry_delay', fallback=5)
    
    def get_file_age_threshold(self):
        return self.config.getint('upload', 'file_age_threshold', fallback=2)
    
    def get_log_level(self):
        return self.config.get('logging', 'log_level', fallback='INFO')
    
    def get_log_file(self):
        return self.config.get('logging', 'log_file', fallback='')
    
    def get_max_log_size(self):
        return self.config.getint('logging', 'max_log_size', fallback=10)
    
    def get_log_backup_count(self):
        return self.config.getint('logging', 'log_backup_count', fallback=3)


class S3Uploader:
    """Handles S3 upload operations with retry logic"""
    
    def __init__(self, config: S3UploaderConfig):
        self.config = config
        self.s3_client = None
        self.logger = logging.getLogger(__name__)
        self.init_s3_client()
    
    def init_s3_client(self):
        """Initialize S3 client with error handling"""
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=self.config.get_s3_region()
            )
            # Test connection
            self.s3_client.head_bucket(Bucket=self.config.get_s3_bucket())
            self.logger.info(f"Successfully connected to S3 bucket: {self.config.get_s3_bucket()}")
        except NoCredentialsError:
            self.logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        except ClientError as e:
            self.logger.error(f"Failed to connect to S3: {e}")
            raise
    
    def upload_file(self, local_path: str, s3_key: str = None) -> bool:
        """Upload file to S3 with retry logic"""
        if s3_key is None:
            s3_key = os.path.basename(local_path)
        
        # Ensure S3 client is initialized
        if self.s3_client is None:
            raise RuntimeError("S3 client not initialized")
        
        max_retries = self.config.get_max_retries()
        initial_delay = self.config.get_initial_retry_delay()
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"Uploading {local_path} to S3 (attempt {attempt + 1}/{max_retries + 1})")
                
                # Upload file
                self.s3_client.upload_file(
                    local_path,
                    self.config.get_s3_bucket(),
                    s3_key
                )
                
                # Verify upload
                if self.verify_upload(s3_key, local_path):
                    self.logger.info(f"Successfully uploaded {local_path} to S3 as {s3_key}")
                    return True
                else:
                    self.logger.warning(f"Upload verification failed for {local_path}")
                    
            except ClientError as e:
                self.logger.error(f"S3 upload failed (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries:
                    delay = initial_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All upload attempts failed for {local_path}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Unexpected error during upload: {e}")
                return False
        
        return False
    
    def verify_upload(self, s3_key: str, local_path: str) -> bool:
        """Verify that the uploaded file exists and has correct size"""
        try:
            # Ensure S3 client is initialized
            if self.s3_client is None:
                raise RuntimeError("S3 client not initialized")
            
            # Get S3 object metadata
            response = self.s3_client.head_object(
                Bucket=self.config.get_s3_bucket(),
                Key=s3_key
            )
            
            # Get local file size
            local_size = os.path.getsize(local_path)
            s3_size = response['ContentLength']
            
            if local_size == s3_size:
                self.logger.debug(f"Upload verification successful: {s3_key} ({s3_size} bytes)")
                return True
            else:
                self.logger.error(f"Size mismatch - Local: {local_size}, S3: {s3_size}")
                return False
                
        except ClientError as e:
            self.logger.error(f"Failed to verify upload: {e}")
            return False


class VideoFileHandler(FileSystemEventHandler):
    """Handles file system events for video files"""
    
    def __init__(self, uploader: S3Uploader, config: S3UploaderConfig):
        self.uploader = uploader
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.pending_files = {}  # Track files being written
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Check if it's a video file
        if not self.is_video_file(file_path):
            return
        
        self.logger.info(f"New file detected: {file_path}")
        self.pending_files[file_path] = time.time()
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Update timestamp for pending files
        if file_path in self.pending_files:
            self.pending_files[file_path] = time.time()
    
    def is_video_file(self, file_path: str) -> bool:
        """Check if file is a video file based on extension"""
        file_ext = os.path.splitext(file_path)[1]
        return file_ext in self.config.get_file_extensions()
    
    def is_file_ready(self, file_path: str) -> bool:
        """Check if file is ready for upload (not being written)"""
        if file_path not in self.pending_files:
            return False
        
        # Check if file age exceeds threshold
        file_age = time.time() - self.pending_files[file_path]
        threshold = self.config.get_file_age_threshold()
        
        if file_age >= threshold:
            self.logger.debug(f"File {file_path} is ready for upload (age: {file_age:.1f}s)")
            return True
        
        return False
    
    def process_pending_files(self):
        """Process files that are ready for upload"""
        files_to_remove = []
        
        for file_path in list(self.pending_files.keys()):
            if not os.path.exists(file_path):
                # File was deleted or moved
                files_to_remove.append(file_path)
                continue
            
            if self.is_file_ready(file_path):
                self.logger.info(f"Processing file for upload: {file_path}")
                
                # Upload file
                if self.uploader.upload_file(file_path):
                    # Delete local file after successful upload
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Successfully deleted local file: {file_path}")
                    except OSError as e:
                        self.logger.error(f"Failed to delete local file {file_path}: {e}")
                else:
                    self.logger.error(f"Failed to upload {file_path}")
                
                files_to_remove.append(file_path)
        
        # Remove processed files from pending list
        for file_path in files_to_remove:
            self.pending_files.pop(file_path, None)


class S3UploaderService:
    """Main service class for S3 Uploader"""
    
    def __init__(self, config_file='s3_uploader_config.ini'):
        self.config = S3UploaderConfig(config_file)
        self.uploader = S3Uploader(self.config)
        self.observer = Observer()
        self.event_handler = VideoFileHandler(self.uploader, self.config)
        self.logger = None
        self.running = False
        
        self.setup_logging()
        self.setup_signal_handlers()
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.get_log_level().upper())
        
        # Create logger
        self.logger = logging.getLogger()
        self.logger.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if configured)
        log_file = self.config.get_log_file()
        if log_file:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.config.get_max_log_size() * 1024 * 1024,  # Convert MB to bytes
                backupCount=self.config.get_log_backup_count()
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def start(self):
        """Start the S3 uploader service"""
        video_dir = self.config.get_video_directory()
        
        if not os.path.exists(video_dir):
            raise FileNotFoundError(f"Video directory not found: {video_dir}")
        
        self.logger.info(f"Starting S3 Uploader Service")
        self.logger.info(f"Monitoring directory: {video_dir}")
        self.logger.info(f"S3 Bucket: {self.config.get_s3_bucket()}")
        self.logger.info(f"File extensions: {self.config.get_file_extensions()}")
        
        # Start file system observer
        self.observer.schedule(self.event_handler, video_dir, recursive=False)
        self.observer.start()
        
        self.running = True
        
        try:
            while self.running:
                # Process pending files periodically
                self.event_handler.process_pending_files()
                time.sleep(1)  # Check every second
                
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the S3 uploader service"""
        self.logger.info("Stopping S3 Uploader Service...")
        self.running = False
        
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        
        self.logger.info("S3 Uploader Service stopped")


def main():
    """Main entry point"""
    try:
        # Check if config file exists
        config_file = 's3_uploader_config.ini'
        if not os.path.exists(config_file):
            print(f"Configuration file not found: {config_file}")
            print("Please create the configuration file before starting the service.")
            sys.exit(1)
        
        # Create and start service
        service = S3UploaderService(config_file)
        service.start()
        
    except KeyboardInterrupt:
        print("\nService interrupted by user")
    except Exception as e:
        print(f"Service failed to start: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 