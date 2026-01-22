# 📈 DSE Sniper

**The Complete Algorithmic Trading Blueprint for the Dhaka Stock Exchange (DSE)**

> **Objective:** Build a statistically profitable, volume-anomaly detection system for the Dhaka Stock Exchange.

---

## 🧠 1. Executive Summary & Philosophy

Building a trading system for the **Dhaka Stock Exchange (DSE)** requires a fundamental departure from Western market assumptions like the **Efficient Market Hypothesis (EMH)**.

### ❌ The Flaw of Standard Models

- Popular indicators such as **RSI**, **MACD**, and momentum oscillators frequently fail in Bangladesh.
- **Floor prices** and **circuit breakers** create artificial price stability.
- These constraints generate false buy/sell signals and break traditional price-based strategies.

### ✅ The Core Insight

> **Price can be manipulated. Volume cannot.**

Syndicates can suppress or inflate prices, but they **cannot hide the massive volume required to accumulate shares**.

### 🎯 The Solution

This system:
- Ignores price prediction
- Focuses on **Volume Anomaly Detection**
- Detects **quiet accumulation** before explosive moves

**Guiding Principle:**

> Do not predict where the price will go. Detect where the money is hiding.

---

## 🏗️ 2. System Architecture

Designed as a **single-engineer, monolithic-but-modular system**. The priority is **speed, correctness, and maintainability**—not over-engineering.

### 📂 2.1 Repository Structure

```plaintext
dse-sniper/
├── data/
│   ├── raw/                   # Daily CSV dumps from DSE (Immutable)
│   ├── processed/             # Adjusted for Bonus Shares (The "Truth")
│   └── external/              # Fundamental data (Paid-up capital, Category)
├── src/
│   ├── __init__.py
│   ├── data_loader.py         # Ingestion & Corporate Action Adjuster
│   ├── indicators.py          # Custom Syndicate Metrics (RVOL, Float)
│   ├── filters.py             # Liquidity Trap & "Z" Category Filters
│   └── strategy.py            # Buy/Sell Logic & Scoring Engine
├── notebooks/                 # Jupyter notebooks for sandpit & backtesting
├── outputs/
│   ├── signals/               # Daily generated reports (CSV/HTML)
│   └── logs/                  # System health & error logs
├── config.yaml                # Thresholds (RVOL > 2.5, StopLoss = 7%)
├── main.py                    # System entry point (Cron job target)
└── requirements.txt
```

---

## ⚙️ 2.2 Technology Stack

- **Language:** Python 3.10+
- **Data Processing:** Pandas, NumPy
- **Technical Analysis:** TA-Lib, Pandas-TA
- **Machine Learning:** Scikit-learn (Random Forest for regime classification)
- **Database:** SQLite (file-based, zero-config, sufficient for 10+ years of daily data)

---

## 🧹 3. The Data Layer (Sanitization & Engineering)

> **This is the most critical phase of the entire system.**

Raw DSE data is *dirty*, inconsistent, and misleading unless properly adjusted.

### 🔄 3.1 Corporate Action Adjuster

#### ❗ The Problem

Stock Dividends (Bonus Shares) are common in DSE.

Without adjustment:
- A 20% bonus looks like a **20% price crash**
- Historical charts become meaningless
- ML models learn incorrect patterns

#### ✅ The Solution

Use **backward price adjustment** for all historical prices.

#### 📐 Formula

```math
P_adj = P_raw × (1 / (1 + BonusFraction))
```

#### 🧪 Example

- ACMELAB trades at **100 BDT**
- Declares **20% bonus shares**
- New base price: **83.33 BDT**

➡️ Multiply all historical prices *before* this date by **0.833**

---

### 🚫 3.2 Liquidity Trap Filters

Before analysis, every stock must pass **survival filters**.

#### 👻 Ghost Town Rule

```text
If Volume == 0 for 3 consecutive days → DROP
```

Reason: Stock is stuck at floor/ceiling with no buyers.

#### 🪙 Penny Trap Rule

```text
If Paid-Up Capital > 500 Cr AND Daily Movement < 0.5% → DROP
```

Reason: Stock is too heavy to move (e.g., large banks).

---

## 🧠 4. The Prediction Engine ("Syndicate Logic")

Signals are weighted based on **Bangladesh market realities**.

### ⚖️ 4.1 Signal Weighting

| Component | Weight |
|---------|--------|
| Volume / Smart Money Flow | **60%** |
| Trend & Technicals | **30%** |
| Fundamentals (Safety Only) | **10%** |

---

### 📊 4.2 Primary Indicator: Relative Volume (RVOL)

We look for **quiet accumulation**—huge volume without price spikes.

#### 🧮 Algorithm

1. Calculate **20-day average volume**
2. Compute:

```text
RVOL = Today Volume / 20-Day Avg Volume
```

#### 🚨 Buy Signal

```text
RVOL > 2.5 AND Price Change < 2%
```

#### 🧠 Interpretation

Big players are absorbing all sell pressure.
A breakout is likely imminent.

---

### 🧲 4.3 Secondary Indicator: Low Float Multiplier

Syndicates prefer **low paid-up capital stocks**.

```text
If Paid-Up Capital < 50 Cr → Final Score +20%
```

---

## 🛡️ 5. Risk Management (Survival Rules)

> Even a 90% accurate system fails without strict risk control.

### 💰 5.1 Position Sizing — The 2% Rule

- Risk **max 2%** of total capital per trade

#### 📐 Example

- Portfolio: **10,00,000 BDT**
- Max risk: **20,000 BDT**
- Stop loss: **5%**

➡️ Max position size = **4,00,000 BDT**

---

### 🧯 5.2 Stop Loss Rules

- **Fixed Stop Loss:** 7% below entry
  - Prevents getting stuck in limit-down scenarios
- **Trailing Stop:**
  - After +10% gain → Move stop loss to **Break Even**

---

## 🔄 6. System Workflow

### ⏰ 6.1 Daily Automated Routine (Cron)

| Time | Task |
|-----|-----|
| 2:30 PM | Scrape daily OHLCV data from DSE |
| 2:35 PM | Adjust for dividends & apply filters |
| 2:40 PM | Calculate RVOL, scores & rankings |
| 2:45 PM | Generate `signals_today.csv` |

---

### 📄 6.2 Sample Output

| Ticker | Close | RVOL | Paid-Up (Cr) | Score | Action | Logic |
|------|------|------|-------------|------|--------|-------|
| PAPERPROC | 142.5 | 3.4 | 25.0 | 92 | BUY | High RVOL + Low Cap + Flat Price |
| GP | 286.1 | 0.8 | 350.0 | 15 | IGNORE | High Cap, Low Volume |
| ORION | 45.2 | 1.1 | 85.0 | 45 | WAIT | Normal activity |

---

## 🗺️ 7. Implementation Roadmap (12 Weeks)

| Weeks | Milestone |
|------|----------|
| 1–2 | Build `data_loader.py`, ingest 10 years of data |
| 3–4 | Implement RVOL & paid-up capital logic |
| 5–6 | Backtesting (2020–2022) |
| 7–10 | Paper trading & virtual P/L tracking |
| 11–12 | Go live with 10% capital |

---

## ⚠️ 8. Hard Truths for the Engineer

- **Do not over-optimize.** Volume beats fancy neural nets.
- **Data quality is everything.** One bug in dividend adjustment invalidates the entire system.
- **Liquidity is king.** No buyers = no exit, regardless of prediction.

> Spend **80% of your time on data correctness**. Everything else depends on it.

---

## 🧩 Final Note

This system is not designed to be perfect.

It is designed to **survive**, **adapt**, and **exploit structural inefficiencies unique to the Dhaka Stock Exchange**.

📌 *Simple. Ruthless. Volume-driven.*


---

# 📘 DSE Sniper System — Master Blueprint (Theory → Code → Execution)

This document is the **authoritative blueprint** for building and running the DSE Sniper system. It covers **market theory, architecture, exact scoring logic, and a weekend-ready implementation plan**.

> **Data Source Note:** We use **`bdshare`**, a Python package purpose-built for scraping Dhaka Stock Exchange data, for daily updates. Your **14-year CSV archive** forms the historical base.

---

## 🧠 1. The Theory (The “Brain”)

### Why This Works in Bangladesh

**The Problem**
- DSE is illiquid and syndicate-driven
- Prices are often manipulated or stuck at *floor prices*
- RSI, MACD, and price-only indicators fail because **price is easy to fake**

**The Solution**
- Track **Volume**, not prediction
- Syndicates can move price with 1 share
- They **cannot accumulate control without massive volume**

**The Signal**
> *Quiet Accumulation* — Large volume enters while price stays flat

This is the footprint of smart money.

---

## 🏗️ 2. The Architecture (The “Body”)

A **local monolith** optimized for reliability and speed.

- **Language:** Python 3.10+
- **Data Fetcher:** `bdshare` + `pandas`
- **Database:** SQLite (single-file, zero-config)
- **Analysis Engine:** pandas + TA-Lib
- **Scheduler:** Cron (Linux) / Task Scheduler (Windows)

### 📂 Folder Structure

```plaintext
DSE_Sniper/
├── data/
│   ├── dse_history.db         # SQLite master database
│   ├── raw_csvs/              # 14 years of historical CSVs
│   └── paid_up_capital.csv    # Manual fundamentals
├── src/
│   ├── db_manager.py          # SQLite insert/update logic
│   ├── data_fetcher.py        # Daily fetch via bdshare
│   ├── analyzer.py            # RVOL, scoring & signals
│   └── notifier.py            # Console / Telegram alerts
├── main.py                    # Full pipeline entry point
└── requirements.txt
```

---

## 🧠 3. The Logic (The “Code”)

### A. Data Ingestion & Cleaning

1. Load today’s data using `bdshare`
2. Apply survival filters:

```text
Filter 1: Volume < 50,000 → IGNORE (Dead stock)
Filter 2: Price unchanged for 5 days + Volume = 0 → IGNORE (Floor/Ceiling trap)
```

---

### B. The “Syndicate” Algorithm

#### Indicators

**Relative Volume (RVOL)**

```math
RVOL = Today Volume / Average Volume (Last 20 Days)
```

**Price Change**

```math
% Change = (Today Close − Yesterday Close) / Yesterday Close
```

---

### 🎯 Scoring System (0–100)

| Condition | Points |
|---------|--------|
| RVOL > 2.5 | +50 |
| Price Change < 2% AND RVOL > 2.5 | +20 |
| Paid-Up Capital < 50 Cr | +20 |
| Price > 200-Day SMA | +10 |
| Below 200 SMA | −50 |

---

### C. Decision Rules

```text
BUY  → Score > 80
SELL → Price < (Buy Price − 7%)
```

---

## 🛠️ 4. Step-by-Step Implementation Guide

### Step 1: Environment Setup

```bash
pip install pandas numpy ta-lib bdshare sqlalchemy
```

---

### Step 2: Database Initialization (`src/db_manager.py`)

```python
import sqlite3

def init_db():
    conn = sqlite3.connect('data/dse_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_data (
            date TEXT,
            ticker TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER
        )
    ''')
    conn.commit()
    return conn
```

---

### Step 3: Load 14 Years of History

- One-time script
- Normalize dates to `YYYY-MM-DD`
- **Apply bonus/split adjustments BEFORE insert**

> ❗ If this step is wrong, the entire system is wrong.

---

### Step 4: Daily Data Fetcher (`src/data_fetcher.py`)

```python
from bdshare import get_current_trade_data

def fetch_today():
    df = get_current_trade_data()
    df['close'] = df['close'].str.replace(',', '').astype(float)
    df['volume'] = df['volume'].str.replace(',', '').astype(int)
    return df
```

---

### Step 5: Analyzer (`src/analyzer.py`)

```python
import talib

def analyze_stock(ticker, df):
    df['SMA_200'] = talib.SMA(df['close'], timeperiod=200)
    df['AVG_VOL_20'] = talib.SMA(df['volume'], timeperiod=20)

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    rvol = today['volume'] / today['AVG_VOL_20']
    price_change = (today['close'] - yesterday['close']) / yesterday['close']

    score = 0
    reasons = []

    if rvol > 2.5 and price_change < 0.02:
        score += 70
        reasons.append(f"Quiet Accumulation (RVOL {rvol:.1f}x)")

    if today['close'] > today['SMA_200']:
        score += 10
    else:
        score -= 50
        reasons.append("Below 200 SMA")

    return score, reasons
```

---

### Step 6: Automation

`main.py` flow:

```text
Fetch → Save → Analyze → Rank → Report
```

Schedule to run **2:45 PM** (15 minutes after market close).

---

## 📄 5. Final Output Example

```text
REPORT: 22 Jan 2026

| Ticker    | Price | RVOL | Score | Decision | Reason |
|-----------|-------|------|-------|----------|--------|
| PAPERPROC | 185.2 | 4.1  | 90    | BUY      | Quiet Accumulation, Low Float |
| GP        | 286.5 | 0.8  | 10    | IGNORE   | Low Volume |
| SEAPEARL  | 33.0  | 1.2  | -20   | AVOID    | Below 200 SMA |
```

---

## 🧠 Final Engineering Truth

- **Volume exposes intent**
- **Liquidity decides survival**
- **Data correctness > model complexity**

This blueprint is designed to be **built, tested, and run by one disciplined engineer**.

