# DSE Sniper - Quick Start Guide

## 🚀 Quick Start (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If `ta-lib` installation fails, you can skip it for now. The system will work with pandas-based calculations.

### Step 2: Load Historical Data

Load all historical data from the `data/adjusted_data` directory:

```bash
python main.py load
```

This will:
- Create a SQLite database at `data/dse_history.db`
- Load all CSV files from `data/adjusted_data`
- Show loading statistics

**Expected output:**
```
Load Statistics:
  Success: XXX
  Failed: 0
  Total: XXX

Database Statistics:
  total_tickers: XXX
  total_records: XXXXX
  date_range: 2012-10-01 to 2024-02-20
```

### Step 3: Analyze Stocks and Generate Signals

Run the analysis on all stocks:

```bash
python main.py analyze
```

This will:
- Analyze all stocks in the database
- Calculate RVOL, SMA, and scoring
- Apply survival filters
- Generate BUY/WAIT/IGNORE signals
- Create reports in `outputs/signals/`

**Output includes:**
- Console report with top BUY signals
- CSV report: `outputs/signals/signals_YYYYMMDD.csv`
- HTML report: `outputs/signals/signals_YYYYMMDD.html`

### Step 4: View Results

Open the HTML report in your browser:
```bash
# Windows
start outputs/signals/signals_YYYYMMDD.html

# Linux/Mac
open outputs/signals/signals_YYYYMMDD.html
```

---

## 📋 Common Commands

### Load specific ticker
```bash
python main.py load --ticker GP
```

### Analyze specific ticker
```bash
python main.py analyze --ticker GP
```

### Show database statistics
```bash
python main.py stats
```

### Show detailed statistics with ticker list
```bash
python main.py stats --verbose
```

### Load only specific tickers
```bash
python main.py load --filter GP BEXIMCO SQURPHARMA
```

---

## 📊 Understanding the Output

### Score Ranges
- **80-100**: **BUY** - Strong buy signal with high RVOL and positive indicators
- **45-79**: **WAIT** - Moderate potential, watch for better entry
- **0-44**: **IGNORE** - Weak signal or below 200 SMA

### Key Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| **RVOL** | Relative Volume (Volume / 20-day Avg) | > 2.5x |
| **Score** | Trading score (0-100) | > 80 |
| **Price Change** | Daily price change % | < 2% (for quiet accumulation) |
| **Volume** | Today's volume | > 50,000 |

### Scoring Logic

- **RVOL > 2.5**: +50 points (High volume activity)
- **Quiet Accumulation** (RVOL > 2.5 AND Price Change < 2%): +20 points
- **Low Float** (Paid-Up Capital < 50 Cr): +20 points
- **Above 200 SMA**: +10 points
- **Below 200 SMA**: -50 points (Bearish trend)

---

## 🎯 Example Analysis Result

```
1. PAPERPROC - Score: 92
   Price: 142.5 BDT | RVOL: 3.4x | Volume: 450,000
   Change: 1.5% | Avg Vol (20d): 132,000
   Reasons: High RVOL (3.4x), Quiet Accumulation, Above 200 SMA
```

**Interpretation:**
- **PAPERPROC** has a score of 92 (Strong BUY)
- Volume is 3.4x higher than 20-day average
- Price changed only 1.5% despite high volume (quiet accumulation)
- Price is above 200-day moving average (uptrend)

---

## 🛠️ Troubleshooting

### Problem: "No data available"
**Solution:** Run `python main.py load` first to load historical data

### Problem: "No stocks passed analysis filters"
**Solution:** Check if:
- Data is loaded correctly (`python main.py stats`)
- Recent data has sufficient volume (> 50,000)
- Stocks are not stuck at floor/ceiling prices

### Problem: Import errors in IDE
**Solution:** The imports will work fine when running. This is just an IDE warning. You can ignore it or add the `src` directory to your Python path.

---

## 📁 Project Structure

```
stock-prediction-system/
├── data/
│   ├── adjusted_data/        # Historical CSV files (input)
│   ├── unadjusted_data/      # Raw data (backup)
│   └── dse_history.db        # SQLite database (generated)
├── src/
│   ├── db_manager.py         # Database operations
│   ├── data_loader.py        # CSV to database loader
│   ├── analyzer.py           # RVOL calculation & scoring
│   └── report_generator.py   # Report creation
├── outputs/
│   └── signals/              # Generated reports
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
├── README.md                 # Full documentation
└── QUICKSTART.md            # This file
```

---

## 🔄 Daily Workflow

For daily analysis after market close:

```bash
# 1. Update database with latest data (if using bdshare)
# python main.py load --ticker TICKER_NAME

# 2. Run analysis
python main.py analyze

# 3. Review the HTML report
start outputs/signals/signals_YYYYMMDD.html
```

---

## ⚠️ Important Notes

1. **Data Quality**: The system uses the `adjusted_data` directory which should already have corporate action adjustments applied

2. **No Guarantees**: This is an analytical tool, not financial advice. Always do your own research

3. **Volume is King**: The system focuses on volume anomalies. Low volume stocks are automatically filtered out

4. **Survival Filters**: Stocks with zero volume for 3+ days or stuck at floor/ceiling prices are excluded

---

## 📚 Learn More

- Read the full [README.md](README.md) for detailed theory and implementation
- Check the `src/` directory for implementation details
- Review scoring logic in `src/analyzer.py`

---

## 🆘 Need Help?

Common issues and solutions:

1. **Missing dependencies**: Run `pip install pandas numpy sqlalchemy`
2. **No signals**: Ensure data is recent and markets are active
3. **Performance**: For faster analysis, consider loading only active tickers

---

**Built for:** Dhaka Stock Exchange (DSE)
**Philosophy:** Volume cannot be faked. Detect where the money is hiding.
