# Automated API Health Monitoring

**Status**: ✅ ACTIVE  
**Check Interval**: Every 5 minutes  
**Alerts**: Desktop notifications when API fails

## Overview

The system now has **automated health monitoring** that continuously checks if the API is working correctly. You'll get **automatic desktop notifications** if anything breaks - no need to manually check logs!

## What It Monitors

Every 5 minutes, the monitor checks:

1. ✅ **HTTP Status** - Is the API responding?
2. ✅ **Response Format** - Is it valid JSON?
3. ✅ **Data Type** - Is it returning a list?
4. ✅ **Signal Count** - Are there at least 1 signal?
5. ✅ **Response Time** - Does it respond within 10 seconds?

## What Happens When API Fails

### Automatic Actions:
1. 🚨 **Desktop Notification** appears on your screen
2. 📝 **Log Entry** written to `data/health_monitor.log`
3. 📄 **Alert File** created at `data/last_alert.txt`
4. 🔄 **Continues checking** every 5 minutes until fixed

### Example Alert:
```
🚨 DSE Sniper API DOWN

API health check failed!

HTTP 500: Error processing signals

Time: 2:45 PM
```

## How to Use

### Check Monitor Status

```bash
# View monitor logs (real-time)
tail -f data/health_monitor.log

# View recent checks
tail -20 data/health_monitor.log

# Check if any active alerts
cat data/last_alert.txt
```

### Manual Health Check

```bash
# Run health check manually
python3 monitor_api_health.py
```

### View Cron Job

```bash
# See when next check will run
crontab -l | grep monitor_api_health
```

### Disable Monitoring (if needed)

```bash
# Remove cron job
crontab -l | grep -v "monitor_api_health" | crontab -

# Verify removed
crontab -l
```

### Re-enable Monitoring

```bash
# Run setup script again
./setup_monitoring.sh
```

## Log Files

### Health Monitor Log
**Location**: `data/health_monitor.log`

Example healthy log:
```
[2026-02-01 14:50:18] Checking API health...
[2026-02-01 14:50:18] ✅ API healthy: 16 signals
[2026-02-01 14:55:23] Checking API health...
[2026-02-01 14:55:24] ✅ API healthy: 16 signals
```

Example failure log:
```
[2026-02-01 15:00:30] Checking API health...
[2026-02-01 15:00:31] ❌ API UNHEALTHY: HTTP 500: Error processing signals
[2026-02-01 15:00:31] ALERT SENT: 🚨 DSE Sniper API DOWN
```

### Alert File
**Location**: `data/last_alert.txt`

Only exists when there's an active alert. Gets deleted automatically when API recovers.

## Benefits

### Before Monitoring:
- ❌ Bugs could silently break the API
- ❌ You'd only notice when manually checking
- ❌ Could go hours/days without detecting issues
- ❌ Had to manually check logs

### After Monitoring:
- ✅ **Instant alerts** when something breaks
- ✅ **Desktop notifications** - impossible to miss
- ✅ **Automatic recovery detection** - notifications clear when fixed
- ✅ **Complete history** in logs
- ✅ **Zero manual intervention** required

## Troubleshooting

### No Notifications Appearing?

1. Check if notify-send is installed:
```bash
which notify-send
# If not found, install:
sudo apt install libnotify-bin
```

2. Test notification manually:
```bash
notify-send -u critical "Test Alert" "This is a test"
```

### Monitor Not Running?

```bash
# Check cron service
systemctl status cron

# Restart cron if needed
sudo systemctl restart cron

# Verify cron job exists
crontab -l | grep monitor_api_health
```

### Monitor Logging Errors?

```bash
# Check monitor log for errors
tail -50 data/health_monitor.log

# Test monitor manually
python3 monitor_api_health.py
```

## Configuration

Edit `monitor_api_health.py` to customize:

```python
# Change check frequency in cron job
*/5 * * * *   # Every 5 minutes (default)
*/10 * * * *  # Every 10 minutes
*/1 * * * *   # Every 1 minute (more aggressive)

# Change minimum expected signals
MIN_EXPECTED_SIGNALS = 1  # Alert if fewer than 1 signal

# Change API URL (for testing different environments)
API_URL = "http://localhost:12001/api/sniper-signals"  # Local
API_URL = "https://dse-sniper-backend.maksudul.com/api/sniper-signals"  # Production
```

## Integration with Existing System

The monitor works alongside:
- ✅ Backend comprehensive error logging (from main.py)
- ✅ HTTP 500 errors on failure (no more silent returns)
- ✅ Detailed stack traces in systemd logs
- ✅ Manual testing scripts (test_api_logic.py)

## Summary

**You asked**: "So I have to manually check logs?"  
**Answer**: **NO!** ✅

With automated monitoring:
1. 🤖 **System monitors itself** every 5 minutes
2. 🚨 **Desktop alerts** appear instantly on failure
3. 📊 **Logs available** if you want details
4. 🔄 **Auto-recovery detection** - alerts clear when fixed
5. 😴 **Set it and forget it** - works 24/7

## Next Steps

The monitoring is **already active**! You don't need to do anything.

If the API ever fails, you'll see a desktop notification like:
```
🚨 DSE Sniper API DOWN
API health check failed!
[error details]
Time: 2:45 PM
```

That's your signal to check the logs and fix the issue.

**The system is now self-monitoring and self-healing aware!** 🎉
