#!/bin/bash
# Setup automated API health monitoring

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor_api_health.py"

echo "🔧 Setting up automated API health monitoring..."

# Check if script exists
if [ ! -f "$MONITOR_SCRIPT" ]; then
    echo "❌ Error: monitor_api_health.py not found"
    exit 1
fi

# Make script executable
chmod +x "$MONITOR_SCRIPT"

# Add cron job (runs every 5 minutes)
CRON_JOB="*/5 * * * * cd $SCRIPT_DIR && /usr/bin/python3 $MONITOR_SCRIPT >> $SCRIPT_DIR/data/health_monitor.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "monitor_api_health.py"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    crontab -l 2>/dev/null | grep -v "monitor_api_health.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "📊 Monitoring details:"
echo "   - Check interval: Every 5 minutes"
echo "   - Log file: $SCRIPT_DIR/data/health_monitor.log"
echo "   - Alert file: $SCRIPT_DIR/data/last_alert.txt"
echo ""
echo "🔍 View current cron jobs:"
echo "   crontab -l"
echo ""
echo "📖 View monitor logs:"
echo "   tail -f $SCRIPT_DIR/data/health_monitor.log"
echo ""
echo "🧪 Test the monitor now:"
echo "   python3 $MONITOR_SCRIPT"
echo ""

# Run initial test
echo "Running initial test..."
python3 "$MONITOR_SCRIPT"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Monitoring is active! You'll get desktop notifications if API fails."
else
    echo ""
    echo "⚠️  Initial test failed. Check the logs for details."
fi
