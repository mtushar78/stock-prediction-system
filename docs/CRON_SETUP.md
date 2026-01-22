# 🕒 DSE Sniper - Automated Cron Job Setup

This guide explains how to set up automated cron jobs for the DSE Sniper system on Linux.

---

## 📋 Overview

The system will run automatically on trading days (Monday-Friday):

| Time | Task | Description |
|------|------|-------------|
| **10:00 AM** | Morning Update | Updates stock data and generates analysis signals |
| **2:45 PM** | Portfolio UI | Launches web interface for portfolio monitoring |

DSE Trading Hours: **10:00 AM - 2:30 PM** (Bangladesh Time, UTC+6)

---

## 🚀 Quick Setup

### Step 1: Make Scripts Executable

```bash
cd /path/to/stock-prediction-system
chmod +x run_morning_update.sh
chmod +x run_portfolio_ui.sh
```

### Step 2: Test Scripts Manually

Before setting up cron jobs, test that the scripts work:

```bash
# Test morning update script
./run_morning_update.sh

# Test portfolio UI script (will start server - press CTRL+C to stop)
./run_portfolio_ui.sh
```

### Step 3: Create Log Directory

```bash
mkdir -p outputs/logs
```

### Step 4: Set Up Cron Jobs

Open your crontab editor:

```bash
crontab -e
```

Add the following lines (replace `/path/to/stock-prediction-system` with your actual path):

```bash
# DSE Sniper - Morning Update (10:00 AM, Monday-Friday)
0 10 * * 1-5 /path/to/stock-prediction-system/run_morning_update.sh >> /path/to/stock-prediction-system/outputs/logs/cron_morning.log 2>&1

# DSE Sniper - Portfolio UI (2:45 PM, Monday-Friday)
45 14 * * 1-5 /path/to/stock-prediction-system/run_portfolio_ui.sh >> /path/to/stock-prediction-system/outputs/logs/cron_ui.log 2>&1
```

Save and exit (usually `ESC` then `:wq` in vim, or `CTRL+X` then `Y` in nano).

### Step 5: Verify Cron Jobs

Check that your cron jobs are installed:

```bash
crontab -l
```

---

## 📝 Detailed Configuration

### Option A: Using Shell Scripts (Recommended)

**Advantages:**
- Cleaner crontab
- Easier to modify and test
- Better logging and error handling
- More maintainable

```bash
# Morning update at 10:00 AM
0 10 * * 1-5 /path/to/stock-prediction-system/run_morning_update.sh >> /path/to/stock-prediction-system/outputs/logs/cron_morning.log 2>&1

# Portfolio UI at 2:45 PM
45 14 * * 1-5 /path/to/stock-prediction-system/run_portfolio_ui.sh >> /path/to/stock-prediction-system/outputs/logs/cron_ui.log 2>&1
```

### Option B: Direct Python Commands

If you prefer to run Python commands directly:

```bash
# Morning update at 10:00 AM
0 10 * * 1-5 cd /path/to/stock-prediction-system && /usr/bin/python main.py update && /usr/bin/python main.py analyze >> /path/to/stock-prediction-system/outputs/logs/cron_morning.log 2>&1

# Portfolio UI at 2:45 PM
45 14 * * 1-5 cd /path/to/stock-prediction-system && /usr/bin/python portfolio_ui.py >> /path/to/stock-prediction-system/outputs/logs/cron_ui.log 2>&1
```

---

## 🔧 Finding Your Python Path

If you're not sure where Python is installed:

```bash
which python
# or
which python3
```

Use the full path in your cron jobs for reliability.

---

## 🌍 Timezone Considerations

### If Your System is in Bangladesh Time (UTC+6)
The cron times above are correct as-is.

### If Your System is in a Different Timezone

You need to adjust the cron times to match Bangladesh time. For example:

| Your Timezone | Adjustment | 10:00 AM BD | 2:45 PM BD |
|---------------|------------|-------------|------------|
| **UTC (GMT)** | -6 hours | `0 4 * * 1-5` | `45 8 * * 1-5` |
| **EST (UTC-5)** | -11 hours | `0 23 * * 0-4` | `45 3 * * 1-5` |
| **IST (UTC+5:30)** | -0:30 hours | `30 9 * * 1-5` | `15 14 * * 1-5` |

**Better Solution:** Set your system timezone to Bangladesh:

```bash
# Check current timezone
timedatectl

# Set to Bangladesh (if you have root access)
sudo timedatectl set-timezone Asia/Dhaka
```

---

## 📊 Monitoring Cron Jobs

### View Cron Logs

```bash
# View morning update logs
tail -f outputs/logs/cron_morning.log

# View portfolio UI logs
tail -f outputs/logs/cron_ui.log

# View system cron logs (varies by distribution)
tail -f /var/log/syslog | grep CRON  # Ubuntu/Debian
tail -f /var/log/cron                 # CentOS/RHEL
```

### Check if Cron is Running

```bash
# Check cron service status
systemctl status cron     # Ubuntu/Debian
systemctl status crond    # CentOS/RHEL

# Restart cron service if needed
sudo systemctl restart cron
```

### Verify Portfolio UI is Running

After 2:45 PM, check if the web interface is accessible:

```bash
# Check if portfolio_ui.py is running
ps aux | grep portfolio_ui.py

# Check if port 8080 is listening
netstat -tulpn | grep 8080
# or
ss -tulpn | grep 8080

# Access the UI
curl http://localhost:8080
```

---

## 🛑 Stopping the Portfolio UI

The portfolio UI will run indefinitely once started. To stop it:

```bash
# Find the process
ps aux | grep portfolio_ui.py

# Kill the process (replace PID with actual process ID)
kill <PID>

# Or kill all Python processes running portfolio_ui.py
pkill -f portfolio_ui.py
```

### Auto-Stop Portfolio UI (Optional)

If you want the UI to stop automatically, you can add a cron job to kill it:

```bash
# Stop portfolio UI at 11:00 PM (end of trading day)
0 23 * * 1-5 pkill -f portfolio_ui.py
```

---

## 🔔 Email Notifications (Optional)

To receive email notifications when cron jobs complete:

1. Install `mailutils` or `sendmail`:
   ```bash
   sudo apt-get install mailutils  # Ubuntu/Debian
   ```

2. Add `MAILTO` to your crontab:
   ```bash
   MAILTO=your-email@example.com
   
   0 10 * * 1-5 /path/to/stock-prediction-system/run_morning_update.sh
   ```

Cron will email you the output of each job.

---

## 🐛 Troubleshooting

### Cron Job Not Running?

1. **Check cron service:**
   ```bash
   systemctl status cron
   ```

2. **Check file permissions:**
   ```bash
   ls -l run_morning_update.sh
   # Should show: -rwxr-xr-x (executable)
   ```

3. **Test script manually:**
   ```bash
   ./run_morning_update.sh
   ```

4. **Check logs:**
   ```bash
   tail -f /var/log/syslog | grep CRON
   ```

### Python Not Found?

Use absolute path to Python:

```bash
# Find Python path
which python3

# Update scripts with full path
/usr/bin/python3 main.py update
```

### Permission Denied?

```bash
# Make scripts executable
chmod +x run_morning_update.sh run_portfolio_ui.sh

# Make sure you own the files
chown $USER:$USER run_*.sh
```

### Wrong Timezone?

```bash
# Check timezone
date

# Set timezone
sudo timedatectl set-timezone Asia/Dhaka
```

---

## 📁 File Structure

After setup, your project should have:

```
stock-prediction-system/
├── run_morning_update.sh      # Morning automation script
├── run_portfolio_ui.sh         # Portfolio UI launcher
├── crontab_config.txt          # Crontab reference
├── CRON_SETUP.md              # This file
├── main.py                     # Main pipeline
├── portfolio_ui.py             # Web interface
└── outputs/
    └── logs/
        ├── cron_morning.log    # Morning job logs
        └── cron_ui.log         # UI job logs
```

---

## ✅ Verification Checklist

After setting up, verify:

- [ ] Scripts are executable (`chmod +x`)
- [ ] Scripts run successfully when tested manually
- [ ] Log directory exists (`outputs/logs/`)
- [ ] Cron jobs are added (`crontab -l`)
- [ ] Timezone is correct (`date` or `timedatectl`)
- [ ] Python path is correct (`which python`)
- [ ] First morning run completes successfully
- [ ] Portfolio UI is accessible at http://localhost:8080

---

## 🎯 What Happens Automatically

### Every Trading Day (Monday-Friday):

**10:00 AM:**
1. System wakes up
2. Fetches latest stock data from DSE
3. Updates database with new data
4. Runs volume anomaly analysis
5. Generates BUY/WAIT/IGNORE signals
6. Creates HTML and CSV reports in `outputs/signals/`
7. Logs results to `outputs/logs/cron_morning.log`

**2:45 PM:**
1. Market closes at 2:30 PM
2. System launches Portfolio Guardian UI
3. Web interface becomes available at http://localhost:8080
4. You can monitor your portfolio and sell signals
5. UI stays running until manually stopped or system reboot

---

## 🔐 Security Notes

- Logs may contain sensitive information (don't share publicly)
- Portfolio UI runs on localhost only (not accessible remotely by default)
- If you need remote access, consider using SSH tunneling
- Keep your system and Python packages updated

---

## 📚 Additional Resources

- **Cron Syntax:** https://crontab.guru/
- **Python Logging:** See `outputs/logs/` directory
- **DSE Trading Calendar:** https://www.dsebd.org/

---

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review log files in `outputs/logs/`
3. Test scripts manually to isolate the problem
4. Verify all paths in crontab are absolute paths
5. Ensure timezone and trading hours are correct

---

**Remember:** The system automates the boring parts. You still make the final trading decisions based on the signals and your own analysis.

**⚠️ Trading Discipline:** When the Guardian says SELL, you SELL. No exceptions. No "one more day."

---

*Last Updated: January 2026*
