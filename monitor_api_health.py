#!/usr/bin/env python3
"""
Automated API Health Monitor
Runs every 5 minutes via cron to check API health and alert on failures
"""

import requests
import sys
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
import json

# Configuration
API_URL = "https://dse-sniper-backend.maksudul.com/api/sniper-signals"
MIN_EXPECTED_SIGNALS = 1  # Alert if fewer than this
ALERT_FILE = Path(__file__).parent / "data" / "last_alert.txt"
LOG_FILE = Path(__file__).parent / "data" / "health_monitor.log"

def log(message):
    """Log message to file and stdout"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    # Append to log file
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def send_alert(subject, message):
    """Send alert via system notification"""
    # Use notify-send for desktop notification
    import subprocess
    try:
        subprocess.run(['notify-send', '-u', 'critical', subject, message], timeout=5)
        log(f"ALERT SENT: {subject}")
    except:
        log(f"Could not send desktop notification (notify-send not available)")
    
    # Also write to alert file
    ALERT_FILE.parent.mkdir(exist_ok=True)
    with open(ALERT_FILE, 'w') as f:
        f.write(f"{datetime.now().isoformat()}\n{subject}\n{message}\n")

def check_api_health():
    """Check API health and return status"""
    try:
        log("Checking API health...")
        
        # Make request with timeout
        response = requests.get(API_URL, timeout=10)
        
        # Check HTTP status
        if response.status_code != 200:
            return {
                'healthy': False,
                'error': f"HTTP {response.status_code}: {response.text[:200]}"
            }
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            return {
                'healthy': False,
                'error': f"Invalid JSON response: {str(e)}"
            }
        
        # Check if it's a list
        if not isinstance(data, list):
            return {
                'healthy': False,
                'error': f"Expected list, got {type(data).__name__}"
            }
        
        # Check signal count
        signal_count = len(data)
        
        if signal_count < MIN_EXPECTED_SIGNALS:
            return {
                'healthy': False,
                'error': f"Too few signals: {signal_count} (expected at least {MIN_EXPECTED_SIGNALS})"
            }
        
        # All checks passed
        log(f"✅ API healthy: {signal_count} signals")
        return {
            'healthy': True,
            'signal_count': signal_count
        }
        
    except requests.Timeout:
        return {
            'healthy': False,
            'error': "Request timeout (>10s)"
        }
    except requests.ConnectionError as e:
        return {
            'healthy': False,
            'error': f"Connection error: {str(e)}"
        }
    except Exception as e:
        return {
            'healthy': False,
            'error': f"Unexpected error: {str(e)}"
        }

def main():
    """Main monitoring logic"""
    result = check_api_health()
    
    if not result['healthy']:
        # API is unhealthy - send alert
        error_msg = result['error']
        log(f"❌ API UNHEALTHY: {error_msg}")
        
        send_alert(
            "🚨 DSE Sniper API DOWN",
            f"API health check failed!\n\n{error_msg}\n\nTime: {datetime.now().strftime('%I:%M %p')}"
        )
        
        sys.exit(1)  # Exit with error code
    else:
        # API is healthy
        signal_count = result.get('signal_count', 0)
        log(f"✅ API healthy: {signal_count} signals")
        
        # Clear any previous alerts
        if ALERT_FILE.exists():
            ALERT_FILE.unlink()
        
        sys.exit(0)  # Exit successfully

if __name__ == "__main__":
    main()
