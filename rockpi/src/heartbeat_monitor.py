#!/usr/bin/env python3
"""
Rock Pi Heartbeat Monitor
Sends periodic heartbeat signals to AWS CloudWatch for monitoring uptime.
Cost: ~$0.30-0.50/month for custom metrics
"""

import boto3
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError, BotoCoreError

# Add utils to path for shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from logger import setup_logger
from config import load_config

class HeartbeatMonitor:
    def __init__(self, config_path='../config.json'):
        """Initialize the heartbeat monitor with configuration."""
        self.logger = setup_logger('heartbeat_monitor')
        self.config = load_config(config_path)
        
        # AWS clients
        try:
            self.cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
            self.logger.info("AWS CloudWatch client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS clients: {e}")
            raise
        
        # Configuration
        self.device_id = self.config.get('device_id', 'rockpi-4b-plus')
        self.metric_namespace = self.config.get('metric_namespace', 'RockPi/Heartbeat')
        self.metric_name = self.config.get('heartbeat_metric_name', 'DeviceUptime')
        
    def send_heartbeat(self):
        """Send a heartbeat metric to CloudWatch."""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Send custom metric to CloudWatch
            response = self.cloudwatch.put_metric_data(
                Namespace=self.metric_namespace,
                MetricData=[
                    {
                        'MetricName': self.metric_name,
                        'Dimensions': [
                            {
                                'Name': 'DeviceId',
                                'Value': self.device_id
                            }
                        ],
                        'Value': 1.0,  # Simple alive signal
                        'Unit': 'Count',
                        'Timestamp': timestamp
                    }
                ]
            )
            
            self.logger.info(f"Heartbeat sent successfully at {timestamp.isoformat()}")
            return True
            
        except ClientError as e:
            self.logger.error(f"AWS CloudWatch error: {e}")
            return False
        except BotoCoreError as e:
            self.logger.error(f"AWS connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending heartbeat: {e}")
            return False
    
    def get_system_info(self):
        """Get basic system information for the heartbeat."""
        try:
            # Get system uptime
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            
            # Get load average
            with open('/proc/loadavg', 'r') as f:
                load_avg = f.readline().split()[:3]
            
            # Get memory info
            memory_info = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith(('MemTotal:', 'MemAvailable:', 'MemFree:')):
                        key, value = line.split(':')
                        memory_info[key.strip()] = int(value.strip().split()[0])
            
            return {
                'uptime_hours': round(uptime_seconds / 3600, 2),
                'load_avg_1min': float(load_avg[0]),
                'load_avg_5min': float(load_avg[1]),
                'load_avg_15min': float(load_avg[2]),
                'memory_used_percent': round(
                    (memory_info['MemTotal'] - memory_info['MemAvailable']) / memory_info['MemTotal'] * 100, 2
                )
            }
        except Exception as e:
            self.logger.warning(f"Could not gather system info: {e}")
            return {}
    
    def send_enhanced_heartbeat(self):
        """Send heartbeat with additional system metrics."""
        try:
            timestamp = datetime.now(timezone.utc)
            system_info = self.get_system_info()
            
            metrics = [
                {
                    'MetricName': self.metric_name,
                    'Dimensions': [{'Name': 'DeviceId', 'Value': self.device_id}],
                    'Value': 1.0,
                    'Unit': 'Count',
                    'Timestamp': timestamp
                }
            ]
            
            # Add system metrics if available
            if system_info:
                if 'uptime_hours' in system_info:
                    metrics.append({
                        'MetricName': 'SystemUptime',
                        'Dimensions': [{'Name': 'DeviceId', 'Value': self.device_id}],
                        'Value': system_info['uptime_hours'],
                        'Unit': 'Count',
                        'Timestamp': timestamp
                    })
                
                if 'load_avg_1min' in system_info:
                    metrics.append({
                        'MetricName': 'LoadAverage',
                        'Dimensions': [{'Name': 'DeviceId', 'Value': self.device_id}],
                        'Value': system_info['load_avg_1min'],
                        'Unit': 'None',
                        'Timestamp': timestamp
                    })
                
                if 'memory_used_percent' in system_info:
                    metrics.append({
                        'MetricName': 'MemoryUsagePercent',
                        'Dimensions': [{'Name': 'DeviceId', 'Value': self.device_id}],
                        'Value': system_info['memory_used_percent'],
                        'Unit': 'Percent',
                        'Timestamp': timestamp
                    })
            
            # Send all metrics in one API call
            response = self.cloudwatch.put_metric_data(
                Namespace=self.metric_namespace,
                MetricData=metrics
            )
            
            self.logger.info(f"Enhanced heartbeat sent with {len(metrics)} metrics at {timestamp.isoformat()}")
            if system_info:
                self.logger.info(f"System stats: {json.dumps(system_info, indent=2)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending enhanced heartbeat: {e}")
            # Fallback to simple heartbeat
            return self.send_heartbeat()

def main():
    """Main function to send a single heartbeat."""
    try:
        monitor = HeartbeatMonitor()
        success = monitor.send_enhanced_heartbeat()
        
        if success:
            print(f"✅ Heartbeat sent successfully at {datetime.now().isoformat()}")
            sys.exit(0)
        else:
            print("❌ Failed to send heartbeat")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
