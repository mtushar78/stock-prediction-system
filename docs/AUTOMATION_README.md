ple# 🤖 DSE Sniper - Automation Guide

Complete automation setup for the DSE Sniper trading system.

---

## 📋 Quick Reference

### DSE Trading Schedule
- **Market Open:** 10:00 AM (Bangladesh Time)
- **Market Close:** 2:30 PM (Bangladesh Time)
- **Trading Days:** Monday - Friday
- **Timezone:** Asia/Dhaka (UTC+6)

### Automated Tasks
| Time | Task | What It Does |
|------|------|--------------|
| **10:00 AM** | Morning Update | Fetches data + Runs analysis + Generates signals |
| **2:45 PM** | Portfolio UI | Launches web interface for portfolio monitoring |

---

## 🐧 Linux Setup (Cron Jobs)

### Files Created:
1. **`run_morning_update.sh`** - Shell script for morning automation
2. **`run_portfolio_ui.sh`** - Shell script for UI launcher
3. **`crontab_config.txt`** - Crontab reference configuration
4. **`CRON_SETUP.md`** - Detailed Linux setup guide

### Quick Setup:
```bash
# 1. Make scripts executable
chmod +x run_morning_update.sh run_portfolio_ui.sh

# 2. Test manually
./run_morning_update.sh
./run_portfolio_ui.sh  # Press CTRL+C to stop

# 3. Edit crontab
crontab -e

# 4. Add these lines (replace path):
0 10 * * 1-5 /path/to/stock-prediction-system/run_morning_update.sh >> /path/to/stock-prediction-system/outputs/logs/cron_morning.log 2>&1
45 14 * * 1-5 /path/to/stock-prediction-system/run_portfolio_ui.sh >> /path/to/stock-prediction-system/outputs/logs/cron_ui.log 2>&1

# 5. Verify
crontab -l
```

**📖 Full Guide:** See [`CRON_SETUP.md`](./CRON_SETUP.md) for detailed instructions, troubleshooting, and advanced configuration.

---

## 🪟 Windows Setup (Task Scheduler)

### Files Created:
1. **`run_morning_update.bat`** - Batch script for morning automation
2. **`run_portfolio_ui.bat`** - Batch script for UI launcher

### Quick Setup:

#### Option 1: Using Task Scheduler GUI

1. Open **Task Scheduler** (search in Start menu)

2. **Create Morning Update Task:**
   - Click "Create Task"
   - **General:**
     - Name: `DSE Sniper - Morning Update`
     - Run whether user is logged on or not
   - **Triggers:**
     - New trigger
     - Daily at 10:00 AM
     - Repeat: Weekdays only (Mon-Fri)
   - **Actions:**
     - Action: Start a program
     - Program: `d:\work\personal\stock-prediction-system\run_morning_update.bat`
     - Start in: `d:\work\personal\stock-prediction-system`
   - Click OK

3. **Create Portfolio UI Task:**
   - Same steps but:
     - Name: `DSE Sniper - Portfolio UI`
     - Time: 2:45 PM (14:45)
     - Program: `d:\work\personal\stock-prediction-system\run_portfolio_ui.bat`

#### Option 2: Using Command Line

```cmd
REM Morning Update Task
schtasks /create /tn "DSE Sniper - Morning Update" /tr "d:\work\personal\stock-prediction-system\run_morning_update.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 10:00

REM Portfolio UI Task
schtasks /create /tn "DSE Sniper - Portfolio UI" /tr "d:\work\personal\stock-prediction-system\run_portfolio_ui.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 14:45
```

#### Verify Tasks:
```cmd
schtasks /query /tn "DSE Sniper - Morning Update"
schtasks /query /tn "DSE Sniper - Portfolio UI"
```

---

## 🔍 What Each Script Does

### Morning Update (`run_morning_update.sh` / `.bat`)

**Sequential Execution:**
1. **`python main.py update`**
   - Fetches latest stock data from DSE
   - Updates SQLite database
   - Handles data cleaning and validation

2. **`python main.py analyze`** (runs only if update succeeds)
   - Calculates volume anomalies (RVOL)
   - Applies syndicate detection logic
   - Generates BUY/WAIT/IGNORE signals
   - Creates reports:
     - HTML: `outputs/signals/signals_YYYYMMDD.html`
     - CSV: `outputs/signals/signals_YYYYMMDD.csv`

**When:** 10:00 AM (market open)  
**Duration:** ~2-5 minutes  
**Output:** Signal reports ready for review

### Portfolio UI (`run_portfolio_ui.sh` / `.bat`)

**Execution:**
1. Launches Flask web server
2. Serves portfolio dashboard at http://localhost:8080
3. Real-time sell signal monitoring
4. Interactive position management

**When:** 2:45 PM (15 min after market close)  
**Duration:** Runs until manually stopped  
**Access:** http://localhost:8080

---

## 📊 Monitoring & Logs

### Log Locations:
```
outputs/logs/
├── cron_morning.log       # Morning automation logs (Linux)
└── cron_ui.log           # Portfolio UI logs (Linux)
```

### View Logs:
```bash
# Linux - Real-time monitoring
tail -f outputs/logs/cron_morning.log
tail -f outputs/logs/cron_ui.log

# Windows - View in notepad
notepad outputs\logs\cron_morning.log
```

### Check if Running:
```bash
# Linux
ps aux | grep portfolio_ui.py
crontab -l

# Windows
tasklist | findstr python
schtasks /query | findstr "DSE Sniper"
```

---

## 🎯 Typical Daily Workflow

### Morning (10:00 AM - Automated)
1. ✅ System fetches latest DSE data
2. ✅ Runs analysis and generates signals
3. ✅ Reports saved to `outputs/signals/`
4. 📧 Optional: Email notification (if configured)

### Review Signals (10:05 AM - Manual)
1. Open latest report: `outputs/signals/signals_YYYYMMDD.html`
2. Review BUY signals (Score ≥80)
3. Check WAIT signals (Score 45-79)
4. Make trading decisions based on signals

### After Market Close (2:45 PM - Automated)
1. ✅ Portfolio UI launches automatically
2. 🌐 Open browser: http://localhost:8080
3. Monitor existing positions
4. Check for SELL signals
5. Execute sells if Guardian recommends

---

## ⚠️ Important Notes

### The Emergency Brake (Automatic Sell Triggers)
The Portfolio Guardian will alert you when:
- **-7% Stop Loss:** Price drops 7% below buy price
- **-5% Trailing Stop:** Price drops 5% from highest peak
- **RVOL >5x Climax:** Extreme volume spike (potential top)

**Rule:** When system says SELL, you SELL. No "wait one more day."

### Data Updates
- System fetches data from StockSurferBD (via API)
- Covers data from Nov 14, 2022 onwards
- Historical data already loaded in database

### Portfolio Management
- Add positions via web UI or CLI: `python main.py portfolio add`
- System tracks highest price seen for trailing stops
- Manual exit decisions still recommended for large moves

---

## 🔧 Manual Commands

If automation fails or you need to run manually:

```bash
# Update data
python main.py update

# Run analysis
python main.py analyze

# Check portfolio
python main.py portfolio check

# Launch UI manually
python portfolio_ui.py
```

---

## 🐛 Troubleshooting

### Scripts Not Running?
```bash
# Linux
chmod +x run_morning_update.sh run_portfolio_ui.sh
crontab -l  # Verify cron jobs

# Windows
# Check Task Scheduler for errors
# Run batch files manually to test
```

### Python Not Found?
```bash
# Find Python path
which python    # Linux
where python    # Windows

# Update scripts with full path
/usr/bin/python main.py update  # Linux
C:\Python39\python.exe main.py update  # Windows
```

### Timezone Issues?
```bash
# Linux - Check timezone
timedatectl
# Set to Bangladesh
sudo timedatectl set-timezone Asia/Dhaka

# Windows - Check timezone
tzutil /g
# Set to Bangladesh Standard Time
tzutil /s "Bangladesh Standard Time"
```

### Portfolio UI Won't Start?
```bash
# Check if port 8080 is already in use
netstat -ano | findstr :8080  # Windows
netstat -tulpn | grep 8080    # Linux

# Kill existing process
taskkill /F /PID <PID>  # Windows
kill <PID>              # Linux
```

---

## 📚 File Reference

| File | Purpose | Platform |
|------|---------|----------|
| `run_morning_update.sh` | Morning automation script | Linux |
| `run_portfolio_ui.sh` | UI launcher script | Linux |
| `run_morning_update.bat` | Morning automation script | Windows |
| `run_portfolio_ui.bat` | UI launcher script | Windows |
| `crontab_config.txt` | Crontab reference | Linux |
| `CRON_SETUP.md` | Detailed Linux guide | Linux |
| `AUTOMATION_README.md` | This file | All |

---

## 🔐 Security Reminders

- Scripts run with your user permissions
- Portfolio UI only accessible on localhost by default
- Logs may contain trade data (keep private)
- Never commit credentials or personal trade data to git
- Use `.gitignore` to exclude sensitive files

---

## ✅ Setup Checklist

- [ ] Scripts are executable / runnable
- [ ] Tested scripts manually
- [ ] Cron jobs / scheduled tasks configured
- [ ] Verified timezone settings
- [ ] Log directory created (`outputs/logs/`)
- [ ] First automated run successful
- [ ] Portfolio UI accessible
- [ ] Sell signals working correctly

---

## 🎓 Next Steps

1. **Monitor first few automated runs** to ensure everything works
2. **Review signals daily** at 10:05 AM after automation completes
3. **Check portfolio** at 2:45 PM for sell signals
4. **Backtest signals** over time to validate strategy
5. **Adjust thresholds** in `config.yaml` based on results

---

**Philosophy:** Automate data fetching and analysis. Let mathematics guide your decisions. But always maintain manual control over actual trades.

**Discipline:** The system gives you signals. You execute with discipline. No emotions. No "just one more day."

---

*DSE Sniper - Volume Anomaly Detection System*  
*Last Updated: January 2026*
