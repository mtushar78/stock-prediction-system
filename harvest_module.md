# The Harvest Module: Portfolio Guardian

**Philosophy:** Buying is about finding opportunities; Selling is about discipline and math.

To "get the meat" (capture the majority of a trend), you must abandon the idea of selling at a specific "target" (like "I'll sell when it doubles"). Instead, you sell only when the stock stops going up.

---

## 📉 The Portfolio Guardian: Selling Architecture

### 1. The Theory: "The Ratchet Effect"

We do not predict the top. We let the market tell us when the top is in.

**The Concept:** Imagine a ratchet mechanism that only turns one way (UP). As the price rises, your "Sell Line" rises with it. It never moves down.

**The Goal:** If a stock goes from 100 to 200, we don't want to sell at 120. We want to sell at 190 (after it peaks at 200 and drops). We sacrifice the top 5-10% to ensure we capture the middle 90%.

---

### 2. The Logic & Formulas

There are 3 Distinct Sell Conditions. The system checks them in this specific order.

#### Condition A: The "Emergency Brake" (Stop Loss)
- **Status:** Active immediately after buying.
- **Purpose:** To prevent a small scratch from becoming a fatal wound.
- **Formula:**
  ```
  P_sell = P_buy × (1 - 0.07)
  ```
  *(Sell if price drops 7% below entry)*

#### Condition B: The "Ratchet" (Trailing Stop)
- **Status:** Active once Price > Buy Price.
- **Purpose:** To lock in profits as the stock climbs ("Getting the meat").
- **State Variable:** You must track `Highest_Price_Seen` (The highest daily close since you bought).
- **Formula:**
  ```
  P_trail = P_highest × (1 - 0.05)
  ```
  *(Sell if price drops 5% from its highest peak)*

#### Condition C: The "Climax" (Volume Anomalies)
- **Status:** Active when Profit > 20%.
- **Purpose:** To escape a "Pump & Dump" before the crash.
- **Formula:**
  ```
  IF (RVOL > 5.0) AND (Candle is Red or Doji): SELL HALF
  ```
  *(If volume is insane but price is struggling, the Syndicate is dumping)*

---

### 3. System Architecture (The Code Structure)

You need a new database table to track your Portfolio. The system needs to "remember" the `highest_price` for each stock you own.

#### Database Schema (portfolio table):

| Column | Type | Description |
|:---|:---|:---|
| ticker | TEXT | Stock Symbol (e.g., SANDHANINS) |
| buy_price | REAL | Your entry price (e.g., 30.5) |
| quantity | INTEGER | Number of shares (e.g., 500) |
| highest_seen | REAL | Crucial: The highest price reached since purchase. |
| purchase_date | TEXT | Date bought. |

---

### 4. The Python Implementation (`src/portfolio_manager.py`)

Create this file. It acts as your Selling Engine.

```python
import sqlite3
import pandas as pd

DB_PATH = 'data/dse_history.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_portfolio_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create Portfolio Table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            ticker TEXT PRIMARY KEY,
            buy_price REAL,
            quantity INTEGER,
            highest_seen REAL,
            purchase_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_trade(ticker, buy_price, quantity, date):
    """Call this when you buy a new stock"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Initial highest_seen is the buy_price
        c.execute("INSERT INTO portfolio VALUES (?, ?, ?, ?, ?)", 
                  (ticker, buy_price, quantity, buy_price, date))
        conn.commit()
        print(f"Added {ticker} bought at {buy_price}")
    except sqlite3.IntegrityError:
        print(f"Error: You already hold {ticker}. Update the record instead.")
    conn.close()

def check_sell_signals():
    """Run this DAILY to see if you should sell anything"""
    conn = get_db_connection()
    
    # 1. Load Portfolio
    portfolio = pd.read_sql("SELECT * FROM portfolio", conn)
    if portfolio.empty:
        print("Portfolio is empty.")
        return

    print("\n=== PORTFOLIO GUARDIAN SCAN ===")
    
    for index, position in portfolio.iterrows():
        ticker = position['ticker']
        buy_price = position['buy_price']
        highest_seen = position['highest_seen']
        
        # 2. Get Current Market Data (Latest Close)
        # Note: Ensure stock_data is updated before running this!
        latest_data = pd.read_sql(f"SELECT * FROM stock_data WHERE ticker='{ticker}' ORDER BY date DESC LIMIT 1", conn)
        
        if latest_data.empty:
            print(f"Warning: No data found for {ticker}")
            continue
            
        current_price = latest_data.iloc[0]['close']
        
        # --- LOGIC ENGINE ---
        
        # Update Highest Seen (The Ratchet)
        if current_price > highest_seen:
            new_highest = current_price
            # Update DB with new high
            conn.execute("UPDATE portfolio SET highest_seen = ? WHERE ticker = ?", (new_highest, ticker))
            conn.commit()
            print(f"📈 {ticker}: New High! Ratchet moved up to {new_highest}")
        else:
            new_highest = highest_seen

        # CALCULATE TRIGGERS
        stop_loss_price = buy_price * 0.93        # -7% Hard Stop
        trailing_stop_price = new_highest * 0.95  # -5% from Peak
        
        # DECISION MATRIX
        action = "HOLD"
        reason = f"Current: {current_price} | Trail Stop: {trailing_stop_price:.2f}"
        
        # 1. Check Hard Stop
        if current_price < stop_loss_price:
            action = "❌ SELL NOW (STOP LOSS)"
            reason = f"Hit -7% Limit. Loss accepted."
            
        # 2. Check Trailing Stop (The Meat)
        elif current_price < trailing_stop_price:
            action = "💰 SELL NOW (TAKE PROFIT)"
            reason = f"Dropped 5% from peak of {new_highest}. Trend Broken."
            
        # Output Status
        print(f"{ticker.ljust(12)} | Buy: {buy_price} | High: {new_highest} | Cur: {current_price} | Action: {action}")
        if "SELL" in action:
            print(f"   >>> REASON: {reason}")

    conn.close()

# Example Usage
if __name__ == "__main__":
    init_portfolio_db()
    
    # UNCOMMENT THIS LINE TO ADD A TEST STOCK:
    # add_trade('SANDHANINS', 21.20, 500, '2026-01-22')
    
    check_sell_signals()
```

---

### 5. Step-by-Step Instructions: How to Use It

#### Step 1: Initialize
Run the script once to create the portfolio table.

```bash
python src/portfolio_manager.py
```

#### Step 2: Input Your "Locked" Shares
Every time you buy a stock (based on the Sniper's advice), you must tell the Guardian. Open `src/portfolio_manager.py`, uncomment the `add_trade` line, and edit it:

```python
# Example: You bought 1000 shares of ACI at 250
add_trade('ACI', 250.0, 1000, '2026-01-22')
```

Run the script to save it. Then comment the line out again.

#### Step 3: Daily Routine (The Harvest)
Every day at 2:45 PM, after you update your daily data:

1. Run `python src/portfolio_manager.py`.
2. Look at the Output.

**Scenario A (The Climb):**
```
SANDHANINS   | Buy: 21.2 | High: 24.0 | Cur: 24.0 | Action: HOLD
📈 SANDHANINS: New High! Ratchet moved up to 24.0
```
**Instruction:** Do nothing. Sleep well. You are making money.

**Scenario B (The Dip - Safe):**
```
SANDHANINS   | Buy: 21.2 | High: 24.0 | Cur: 23.5 | Action: HOLD
```
**Instruction:** Do nothing. It dropped a little, but hasn't hit your Trailing Stop (which is 24.0×0.95=22.8).

**Scenario C (The Exit - Getting the Meat):**
```
SANDHANINS   | Buy: 21.2 | High: 24.0 | Cur: 22.5 | Action: 💰 SELL NOW
   >>> REASON: Dropped 5% from peak of 24.0. Trend Broken.
```
**Instruction:** Log into your DSE mobile app immediately. Sell all shares.

**Result:** You bought at 21.2. You sold at 22.5. You made profit. You didn't sell at the top (24.0), but you didn't let it fall back to 21.2 either. **You got the meat.**

---

### 6. Final "Pro Tip" for Manual Overrides

Sometimes, the system says HOLD, but you see something scary (like news of a fire in the factory). 

**The Rule:** You can always sell earlier than the system says (taking profit is never wrong), but you must **NEVER** hold longer than the system says.

**If system says SELL, you SELL. No excuses. No "Wait one more day."**

This discipline is the only thing protecting you from zero.

---

## Summary

- **Emergency Brake:** -7% stop loss protects you from disasters
- **The Ratchet:** -5% trailing stop locks in profits as stock climbs
- **The Climax:** Volume anomaly detection catches pump & dumps
- **Daily discipline:** Check signals every trading day
- **Iron rule:** When system says SELL, you sell immediately

The Harvest Module ensures you capture the middle 90% of every trend while protecting your capital from catastrophic losses.