# 📈 DSE Sniper

**The Complete Algorithmic Trading Blueprint for the Dhaka Stock Exchange (DSE)**

> **Objective:** Build a statistically profitable, volume-anomaly detection system for the Dhaka Stock Exchange.

---

## 🧠 1. Executive Summary & Philosophy

Building a trading system for the **Dhaka Stock Exchange (DSE)** requires a fundamental departure from Western market assumptions like the **Efficient Market Hypothesis (EMH)**.

### ❌ The Flaw of Standard Models

* Popular indicators such as **RSI**, **MACD**, and momentum oscillators frequently fail in Bangladesh.
* **Floor prices** and **circuit breakers** create artificial price stability.
* These constraints generate false buy/sell signals and break traditional price-based strategies.

### ✅ The Core Insight

> **Price can be manipulated. Volume cannot.**

Syndicates can suppress or inflate prices, but they **cannot hide the massive volume required to accumulate shares**.

### 🎯 The Solution

This system:

* Ignores price prediction
* Focuses on **Volume Anomaly Detection**
* Detects **quiet accumulation** before explosive moves

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

* **Language:** Python 3.10+
* **Data Processing:** Pandas, NumPy
* **Technical Analysis:** TA-Lib, Pandas-TA
* **Machine Learning:** Scikit-learn (Random Forest for regime classification)
* **Database:** SQLite (file-based, zero-config, sufficient for 10+ years of daily data)

---

## 🧹 3. The Data Layer (Sanitization & Engineering)

> **This is the most critical phase of the entire system.**

Raw DSE data is *dirty*, inconsistent, and misleading unless properly adjusted.

### 🔄 3.1 Corporate Action Adjuster

#### ❗ The Problem

Stock Dividends (Bonus Shares) are common in DSE.

Without adjustment:

* A 20% bonus looks like a **20% price crash**
* Historical charts become meaningless
* ML models learn incorrect patterns

#### ✅ The Solution

Use **backward price adjustment** for all historical prices.

#### 📐 Formula

```math
P_adj = P_raw × (1 / (1 + BonusFraction))
```

#### 🧪 Example

* ACMELAB trades at **100 BDT**
* Declares **20% bonus shares**
* New base price: **83.33 BDT**

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

| Component                  | Weight  |
| -------------------------- | ------- |
| Volume / Smart Money Flow  | **60%** |
| Trend & Technicals         | **30%** |
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

* Risk **max 2%** of total capital per trade

#### 📐 Example

* Portfolio: **10,00,000 BDT**
* Max risk: **20,000 BDT**
* Stop loss: **5%**

➡️ Max position size = **4,00,000 BDT**

---

### 🧯 5.2 Stop Loss Rules

* **Fixed Stop Loss:** 7% below entry

  * Prevents getting stuck in limit-down scenarios
* **Trailing Stop:**

  * After +10% gain → Move stop loss to **Break Even**

---

## 🔄 6. System Workflow

### ⏰ 6.1 Daily Automated Routine (Cron)

| Time    | Task                                 |
| ------- | ------------------------------------ |
| 2:30 PM | Scrape daily OHLCV data from DSE     |
| 2:35 PM | Adjust for dividends & apply filters |
| 2:40 PM | Calculate RVOL, scores & rankings    |
| 2:45 PM | Generate `signals_today.csv`         |

---

### 📄 6.2 Sample Output

| Ticker    | Close | RVOL | Paid-Up (Cr) | Score | Action | Logic                            |
| --------- | ----- | ---- | ------------ | ----- | ------ | -------------------------------- |
| PAPERPROC | 142.5 | 3.4  | 25.0         | 92    | BUY    | High RVOL + Low Cap + Flat Price |
| GP        | 286.1 | 0.8  | 350.0        | 15    | IGNORE | High Cap, Low Volume             |
| ORION     | 45.2  | 1.1  | 85.0         | 45    | WAIT   | Normal activity                  |

---

## 🗺️ 7. Implementation Roadmap (12 Weeks)

| Weeks | Milestone                                       |
| ----- | ----------------------------------------------- |
| 1–2   | Build `data_loader.py`, ingest 10 years of data |
| 3–4   | Implement RVOL & paid-up capital logic          |
| 5–6   | Backtesting (2020–2022)                         |
| 7–10  | Paper trading & virtual P/L tracking            |
| 11–12 | Go live with 10% capital                        |

---

## ⚠️ 8. Hard Truths for the Engineer

* **Do not over-optimize.** Volume beats fancy neural nets.
* **Data quality is everything.** One bug in dividend adjustment invalidates the entire system.
* **Liquidity is king.** No buyers = no exit, regardless of prediction.

> Spend **80% of your time on data correctness**. Everything else depends on it.

---

## 🧩 Final Note

This system is not designed to be perfect.

It is designed to **survive**, **adapt**, and **exploit structural inefficiencies unique to the Dhaka Stock Exchange**.

📌 *Simple. Ruthless. Volume-driven.*
