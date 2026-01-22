# 📈 DSE Sniper - Volume Anomaly Detection System

**Algorithmic Trading System for the Dhaka Stock Exchange (DSE)**

> **Philosophy:** Price can be manipulated. Volume cannot. This system detects quiet accumulation before explosive moves.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Update stock data
python main.py update

# 3. Generate trading signals
python main.py analyze

# 4. Launch portfolio monitor
python portfolio_ui.py
```

Access portfolio dashboard at: http://localhost:8080

---

## 📚 Documentation

### Getting Started
- **[Quick Start Guide](docs/QUICKSTART.md)** - Get up and running in 5 minutes
- **[Complete Workflow](docs/COMPLETE_WORKFLOW.md)** - Step-by-step system usage
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - What's built and how it works

### Theory & Strategy
- **[DSE Sniper Theory](docs/DSE_SNIPER_THEORY.md)** - Trading philosophy and algorithm details
- **[Portfolio Management](docs/harvest_module.md)** - The Harvest Module (sell signals)

### Automation
- **[How Automation Works](docs/HOW_AUTOMATION_WORKS.md)** - ⭐ **START HERE** - Simple explanation of cron jobs
- **[Automation Setup](docs/AUTOMATION_README.md)** - Complete automation guide (Linux & Windows)
- **[Linux Cron Setup](docs/CRON_SETUP.md)** - Detailed Linux/cron configuration

---

## 🎯 What This System Does

### Daily Automated Tasks (10:00 AM)
1. **Fetches** latest DSE stock data
2. **Analyzes** volume anomalies (RVOL > 2.5x)
3. **Generates** BUY/WAIT/IGNORE signals
4. **Creates** HTML & CSV reports

### Portfolio Monitoring (2:45 PM)
1. **Launches** web dashboard
2. **Tracks** your positions
3. **Alerts** on sell signals:
   - -7% Stop Loss (Emergency Brake)
   - -5% Trailing Stop (The Ratchet)
   - RVOL >5x (Climax Sell)

---

## 🏗️ System Architecture

```
stock-prediction-system/
├── main.py                    # Main pipeline (update, analyze, portfolio)
├── portfolio_ui.py            # Web dashboard (Flask)
├── config.yaml                # Trading parameters & thresholds
├── requirements.txt           # Python dependencies
│
├── src/                       # Core modules
│   ├── db_manager.py          # SQLite database operations
│   ├── data_loader.py         # Historical data ingestion
│   ├── stocksurfer_fetcher.py # Live data updates (API)
│   ├── analyzer.py            # RVOL calculation & scoring
│   ├── report_generator.py    # HTML/CSV signal reports
│   └── portfolio_manager.py   # Position tracking & sell signals
│
├── data/
│   ├── dse_history.db         # SQLite database (10+ years)
│   ├── adjusted_data/         # Historical CSVs (bonus-adjusted)
│   └── unadjusted_data/       # Raw historical CSVs
│
├── outputs/
│   ├── signals/               # Daily signal reports
│   └── logs/                  # System logs
│
├── templates/
│   └── portfolio_dashboard.html  # Web UI template
│
├── docs/                      # Documentation (you are here)
│
└── run_morning_update.sh      # Automation script (Linux)
    run_portfolio_ui.sh        # UI launcher (Linux)
    run_morning_update.bat     # Automation script (Windows)
    run_portfolio_ui.bat       # UI launcher (Windows)
```

---

## 🔧 Available Commands

### Data Management
```bash
# Load historical data
python main.py load --data-dir data/adjusted_data

# Update with latest data (from API)
python main.py update

# Show database statistics
python main.py stats
```

### Analysis & Signals
```bash
# Analyze all stocks
python main.py analyze

# Analyze specific stock
python main.py analyze --ticker GP

# Skip console output
python main.py analyze --no-console
```

### Portfolio Management
```bash
# Add a position
python main.py portfolio add --ticker GP --price 45.50 --quantity 500

# View portfolio
python main.py portfolio list

# Check for sell signals
python main.py portfolio check

# Portfolio summary
python main.py portfolio summary

# Remove position
python main.py portfolio remove --ticker GP
```

### Web Interface
```bash
# Launch portfolio dashboard
python portfolio_ui.py

# Access at: http://localhost:8080
```

---

## 📊 Signal Scoring System

| Condition | Points |
|-----------|--------|
| RVOL > 2.5 | +50 |
| Quiet Accumulation (RVOL high + price flat) | +20 |
| Low Paid-Up Capital (<50 Cr) | +20 |
| Price above 200-day SMA | +10 |
| Price below 200-day SMA | -50 |

**Signals:**
- **BUY**: Score ≥ 80
- **WAIT**: Score 45-79
- **IGNORE**: Score < 45

---

## ⚡ Automated Trading Schedule

### DSE Trading Hours
- **Market Open:** 10:00 AM (Bangladesh Time)
- **Market Close:** 2:30 PM (Bangladesh Time)

### Automation Schedule
| Time | Task | What Happens |
|------|------|--------------|
| **10:00 AM** | Morning Update | Fetch data → Analyze → Generate signals |
| **2:45 PM** | Portfolio UI | Launch web dashboard for monitoring |

**Setup:** See [How Automation Works](docs/HOW_AUTOMATION_WORKS.md)

---

## 🛡️ Risk Management

### Position Sizing
- Max **2% risk** per trade
- Calculate position size: `(Portfolio × 0.02) / Stop Loss %`

### Exit Rules (Automatic Alerts)
1. **Emergency Brake:** -7% from entry (hard stop)
2. **Trailing Stop:** -5% from highest price seen
3. **Climax Sell:** RVOL >5x (distribution detected)

**Rule:** When system says SELL, you SELL. No exceptions.

---

## 🔑 Key Features

✅ **Volume-Based Signals** - Detects smart money before price moves  
✅ **Automated Data Updates** - Daily fetching from DSE via API  
✅ **Portfolio Guardian** - Web UI with real-time sell signals  
✅ **Bonus Adjustment** - Properly handles stock dividends  
✅ **Liquidity Filters** - Avoids dead/trapped stocks  
✅ **10+ Years History** - SQLite database with full DSE data  
✅ **Cron Ready** - Full automation with Linux/Windows support  

---

## 📖 Core Concepts

### Why Volume?
- **Price** can be manipulated with 1 share
- **Volume** exposes accumulation (needs millions of shares)
- Syndicates cannot hide their footprint

### Quiet Accumulation
- High volume (RVOL >2.5x)
- Flat price (<2% change)
- = Smart money loading before breakout

### The Guardian
- Tracks highest price seen
- Implements trailing stops
- Prevents emotional "one more day" holding

---

## 🐛 Troubleshooting

### Data Issues
```bash
# Reload specific ticker
python main.py load --ticker GP

# Check database
python main.py stats --verbose
```

### No Signals Generated
- Check if market is open (Mon-Fri)
- Verify data update completed: `python main.py stats`
- Check logs: `tail -f outputs/logs/*.log`

### Portfolio UI Not Starting
```bash
# Check if port 8080 is in use
netstat -ano | findstr :8080  # Windows
netstat -tulpn | grep 8080    # Linux

# Kill existing process
pkill -f portfolio_ui.py
```

---

## 🎓 Learning Path

1. **Read:** [How Automation Works](docs/HOW_AUTOMATION_WORKS.md) - Understand the basics
2. **Read:** [DSE Sniper Theory](docs/DSE_SNIPER_THEORY.md) - Learn the strategy
3. **Follow:** [Quick Start Guide](docs/QUICKSTART.md) - Run your first analysis
4. **Study:** [Complete Workflow](docs/COMPLETE_WORKFLOW.md) - Master daily operations
5. **Setup:** [Automation Guide](docs/AUTOMATION_README.md) - Automate everything

---

## ⚠️ Important Notes

### Data Sources
- **Historical Data:** Pre-loaded 14-year CSV archive (2010-2024)
- **Live Updates:** StockSurferBD API (Nov 2022 onwards)
- **Bonus Adjustments:** Already applied to historical data

### System Requirements
- Python 3.10+
- Linux (for cron) or Windows (for Task Scheduler)
- ~500MB disk space for database
- Internet connection for updates

### Trading Discipline
This system provides **signals**, not guarantees:
- Do your own research
- Start with small positions
- Follow stop losses religiously
- Never risk more than 2% per trade

---

## 📞 Support & Resources

- **Documentation:** `/docs` folder
- **Configuration:** `config.yaml` (adjust thresholds)
- **Logs:** `outputs/logs/` (debugging)
- **Reports:** `outputs/signals/` (daily signals)

---

## 🏆 Philosophy

> "Do not predict where the price will go. Detect where the money is hiding."

This system is designed to:
- **Survive** the chaos of DSE
- **Adapt** to syndicate behavior  
- **Exploit** volume anomalies

**Simple. Ruthless. Volume-driven.**

---

**⚡ Ready to start? Read [How Automation Works](docs/HOW_AUTOMATION_WORKS.md) first!**

---

*DSE Sniper - Detect. Signal. Execute.*  
*Last Updated: January 2026*
