# DSE Sniper - Score Breakdown Guide

The system scores each stock out of **100** using 13 indicators. A stock scoring **55+** gets a **BUY** signal, **30-54** gets **WAIT**, and below 30 is **IGNORED**.

---

## 1. Graduated RVOL (Max: 60 pts)

**What it measures:** How much *more* a stock is trading today compared to its normal volume.

- If today's volume is **4x or more** than average — full 60 points (very unusual activity)
- **2.5x** — 50 pts, **2x** — 30 pts, **1.5x** — 15 pts
- Below 1.5x — 0 pts (nothing special happening)

**Why it matters:** Abnormally high volume is the #1 sign that "big players" are entering a stock.

---

## 2. Quiet Accumulation - 5 Day (Max: 20 pts)

**What it measures:** High volume over 5 days **but** the price barely moved.

**Why it matters:** When someone is buying large quantities without pushing the price up, it means they're carefully accumulating shares — a classic sign of planned buying before a price move.

---

## 3. Multi-Day Accumulation - 10 Day (Max: 45 pts)

**What it measures:** How many of the last 10 days had above-normal volume.

- 7+ days with high volume — 35 pts
- 5+ days — 25 pts, 3+ days — 15 pts
- Bonus +10 if the average volume across those days is very high

**Why it matters:** One day of high volume could be random. But sustained high volume over many days means someone is systematically building a position.

---

## 4. Volume Acceleration (Max: 10 pts)

**What it measures:** Whether the last 3 days' volume is ramping up compared to the last 10 days.

**Why it matters:** Volume that is *increasing* day-over-day suggests momentum is building — something may be about to happen.

---

## 5. SMA 200 Position (Range: -50 to +25 pts)

**What it measures:** Where the stock price is relative to its **200-day moving average** (the long-term trend line).

- Price **above** the 200-day line — +10 pts (healthy uptrend)
- Price **just crossed above** it in the last 3 days — +15 bonus (trend reversal signal)
- Price **slightly below** — -5 pts (caution)
- Price **far below** — up to -50 pts (strong penalty, stock is in a downtrend)

**Why it matters:** Stocks below their long-term trend are risky. This filter prevents buying into falling stocks.

---

## 6. OBV Divergence (Max: 15 pts)

**What it measures:** Volume is rising over 20 days **but** the price is flat or falling.

**Why it matters:** This is called "hidden accumulation" — money is flowing into the stock even though the price doesn't show it yet. It often precedes a breakout.

---

## 7. Close Position Ratio (Max: 10 pts)

**What it measures:** Whether the stock closed **near its daily high** on a high-volume day.

**Why it matters:** If a stock closes near the top of its daily range with strong volume, it means buyers dominated the day — bulls are in control.

---

## 8. Low Float (Max: 20 pts)

**What it measures:** Whether the company has a **small paid-up capital** (under 50 Crore).

**Why it matters:** Stocks with fewer shares outstanding move faster. The same amount of buying pressure has a bigger impact on price.

---

## 9. Price Squeeze / Bollinger Band (Max: 15 pts)

**What it measures:** Whether the stock's price range has been **unusually tight** recently (low volatility).

**Why it matters:** Tight price ranges (squeezes) often come right before big moves. Think of it like a spring being compressed — the tighter it gets, the more explosive the release.

---

## 10. Buying Streak (Max: 20 pts)

**What it measures:** Consecutive "green candle" days (price went up) with above-average volume.

- 5+ consecutive green days — 20 pts
- 3+ consecutive green days — 10 pts

**Why it matters:** Retail investors rarely buy consistently for many days in a row. A sustained buying streak with volume points to organized/institutional buying.

---

## 11. Smart Money Divergence (Max: 15 pts)

**What it measures:** A pattern where price goes **up on high-volume days** and goes **down on low-volume days**.

**Why it matters:** This means "smart money" (institutions) is buying, while the small dips are caused by minor retail selling. The real direction is up.

---

## 12. VWAP Proximity (Max: 10 pts)

**What it measures:** Whether the price is staying very close to the **5-day Volume Weighted Average Price** while volume is elevated.

**Why it matters:** Institutional algorithms typically buy at or near VWAP to avoid moving the market. Price hugging VWAP with high volume = large order being filled methodically.

---

## 13. Reward:Risk Ratio (Range: -10 to +10 pts)

**What it measures:** The potential profit vs. potential loss based on support/resistance levels.

- Reward is **2x or more** than risk — +10 pts
- Risk and reward roughly equal — 0 pts (neutral)
- Risk **exceeds** reward — -10 pts (penalty)

**Why it matters:** Even a great setup is a bad trade if you're risking more than you stand to gain.

---

## How the Final Score Works

| Raw Points Earned | Normalized to | Signal |
|---|---|---|
| High (many indicators firing) | 55 - 100 | **BUY** |
| Moderate | 30 - 54 | **WAIT** (watch closely) |
| Low | 0 - 29 | **IGNORE** |

All 13 components add up to a **raw score** (max ~275 points), which is then **normalized to 0-100** for easy reading.

---

## In Simple Terms

The system looks for stocks where:
1. **Volume is unusually high** (someone big is buying)
2. **The buying is sustained** over days, not a one-off spike
3. **The buying is "quiet"** — price isn't shooting up yet (early stage)
4. **The stock isn't in a downtrend** (not catching a falling knife)
5. **The risk-reward makes sense** (potential gain justifies the risk)

When multiple signals align, the score rises — and the higher the score, the stronger the conviction.
