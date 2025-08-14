#!/usr/bin/env python3
"""
Simple Rock Pi Heartbeat Monitor
Sends periodic heartbeat signals to AWS CloudWatch for monitoring uptime.
"""

import boto3
import json
import os
import sys
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError, BotoCoreError

def send_heartbeat():
    """Send a heartbeat metric to CloudWatch."""
    try:
        # AWS clients
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        
        # Configuration
        device_id = 'rockpi-4b-plus-home'
        metric_namespace = 'RockPi/Heartbeat'
        metric_name = 'DeviceUptime'
        
        timestamp = datetime.now(timezone.utc)
        
        # Send custom metric to CloudWatch
        response = cloudwatch.put_metric_data(
            Namespace=metric_namespace,
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': [
                        {
                            'Name': 'DeviceId',
                            'Value': device_id
                        }
                    ],
                    'Value': 1.0,  # Simple alive signal
                    'Unit': 'Count',
                    'Timestamp': timestamp
                }
            ]
        )
        
        print(f"✅ Heartbeat sent successfully at {timestamp.isoformat()}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending heartbeat: {e}")
        return False

def get_system_info():
    """Get basic system information."""
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
                if line.startswith(('MemTotal:', 'MemAvailable:')):
                    key, value = line.split(':')
                    memory_info[key.strip()] = int(value.strip().split()[0])
        
        return {
            'uptime_hours': round(uptime_seconds / 3600, 2),
            'load_avg_1min': float(load_avg[0]),
            'memory_used_percent': round(
                (memory_info['MemTotal'] - memory_info['MemAvailable']) / memory_info['MemTotal'] * 100, 2
            ) if 'MemTotal' in memory_info and 'MemAvailable' in memory_info else 0
        }
    except Exception as e:
        print(f"⚠️ Could not gather system info: {e}")
        return {}

def send_enhanced_heartbeat():
    """Send heartbeat with additional system metrics."""
    try:
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        
        device_id = 'rockpi-4b-plus-home'
        metric_namespace = 'RockPi/Heartbeat'
        timestamp = datetime.now(timezone.utc)
        system_info = get_system_info()
        
        metrics = [
            {
                'MetricName': 'DeviceUptime',
                'Dimensions': [{'Name': 'DeviceId', 'Value': device_id}],
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
                    'Dimensions': [{'Name': 'DeviceId', 'Value': device_id}],
                    'Value': system_info['uptime_hours'],
                    'Unit': 'Count',
                    'Timestamp': timestamp
                })
            
            if 'load_avg_1min' in system_info:
                metrics.append({
                    'MetricName': 'LoadAverage',
                    'Dimensions': [{'Name': 'DeviceId', 'Value': device_id}],
                    'Value': system_info['load_avg_1min'],
                    'Unit': 'None',
                    'Timestamp': timestamp
                })
            
            if 'memory_used_percent' in system_info:
                metrics.append({
                    'MetricName': 'MemoryUsagePercent',
                    'Dimensions': [{'Name': 'DeviceId', 'Value': device_id}],
                    'Value': system_info['memory_used_percent'],
                    'Unit': 'Percent',
                    'Timestamp': timestamp
                })
        
        # Send all metrics in one API call
        response = cloudwatch.put_metric_data(
            Namespace=metric_namespace,
            MetricData=metrics
        )
        
        print(f"✅ Enhanced heartbeat sent with {len(metrics)} metrics at {timestamp.isoformat()}")
        if system_info:
            print(f"📊 System stats: Uptime={system_info.get('uptime_hours', 'N/A')}h, Load={system_info.get('load_avg_1min', 'N/A')}, Memory={system_info.get('memory_used_percent', 'N/A')}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Error sending enhanced heartbeat: {e}")
        # Fallback to simple heartbeat
        return send_heartbeat()

if __name__ == '__main__':
    success = send_enhanced_heartbeat()
    sys.exit(0 if success else 1)
