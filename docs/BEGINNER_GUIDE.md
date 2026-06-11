# DSE Sniper — Beginner's Guide

*A friendly, no-jargon walkthrough of how this dashboard thinks. Read top
to bottom — every term is defined the first time it appears.*

---

## 1. What this system actually does

Every trading day, this system scrapes the entire Dhaka Stock Exchange (DSE),
runs every stock through a scoring formula, and tells you:

> "Out of ~420 stocks listed, here are the few that look like good buys
> right now, and here's *exactly why* each one scored the way it did."

It's not a magic oracle. It's a checklist robot. It just checks the same
15 boxes on every stock, every day, and shows you the ones with the most
boxes ticked.

You're the human. You decide whether to actually buy. The robot does the
counting so you don't have to stare at 420 charts.

---

## 2. Stock market 101 — words you need first

### Price
What one share costs right now. e.g. **MTB = ৳12.7** means one share of
Mutual Trust Bank costs 12 taka 70 paisa.

### Volume
How many shares were traded that day. If 8 million shares of MTB traded
today, that's "today's volume = 8,000,000."

### OHLC ("open / high / low / close")
For each day, four prices matter:
- **Open** — first trade of the day
- **High** — highest trade of the day
- **Low** — lowest trade of the day
- **Close** — last trade of the day

A "**green candle**" = close higher than open (buyers won the day).
A "**red candle**" = close lower than open (sellers won the day).

### Average Volume
The average daily volume over the last 20 trading days. If MTB normally
trades 1.4 million shares a day, that's its "average volume."

### RVOL ("Relative Volume")
Today's volume ÷ average volume.
- **RVOL = 1.0×** → today is normal
- **RVOL = 3.0×** → today's volume is 3× normal (something is happening)
- **RVOL = 0.5×** → today is unusually quiet

**Why it matters**: big price moves without big volume usually don't last.
Volume is the "vote count" — the more votes for a direction, the more real
the move.

### SMA 200 ("200-day Simple Moving Average")
The average closing price over the last 200 days. It's a slow-moving line
on the chart that represents the long-term trend.
- Price **above** SMA 200 → long-term uptrend
- Price **below** SMA 200 → long-term downtrend
- Price **near** SMA 200 → trend is undecided

This system mostly hunts in uptrends. A stock below SMA 200 is "swimming
against the current" — possible to make money, but harder.

### Resistance & Support
- **Resistance** = a price ceiling. The stock keeps trying to break above
  some level but gets pushed back. e.g. "₹146 has been the ceiling for 10
  days."
- **Support** = a price floor. The stock keeps dipping to some level and
  bouncing.

When a stock finally pushes through resistance, that's called a **breakout**.
Breakouts are when the big moves happen. This whole system is designed to
catch breakouts *early*, ideally on day one.

### "Coil" / "Base" / "Consolidation"
When a stock stops moving and just drifts sideways in a tight range for a
while, traders call that a **base** or a **coil**. It looks boring on a
chart. But it's like a spring being wound up — energy is being stored.
When the stock finally breaks out of the base, the move tends to be
explosive.

This system **loves tight bases.** Half its job is finding stocks in
boring sideways patterns that look ready to spring.

---

## 3. The big idea — two scores, two questions

Every day, every stock gets **two separate scores** in this system:

### Score (the "BUY" score, 0–100)
**Question it asks:** *"Has the move already started, and is it still
safe to ride?"*

This is the **confirmation engine**. It rewards stocks that are actively
breaking out *right now*. High volume, strong close, breaking through
resistance — that kind of action.

Thresholds:
- **≥ 50** → **BUY** (green badge)
- **≥ 28** → **WAIT** (yellow badge — interesting but not enough)
- **< 28** → IGNORE (gray)

### EarlyScore (the "setup quality" score, 0–100)
**Question it asks:** *"Is this stock coiled like a spring, about to
move?"*

This is the **pre-breakout detector**. It rewards stocks that have been
*boring* (tight base) and are showing the *first hint* of waking up. The
opposite of the main Score — it actually punishes stocks that already
moved a lot.

Thresholds:
- **≥ 60** AND volume tell present → **EARLY** (orange badge — act now)
- **≥ 40** → **WATCH** (amber badge — setting up, don't buy yet)
- otherwise → **NONE** (gray badge — no setup)

### Why two scores?

Because timing is hard. A stock can be a "good buy" in two very different
ways:

1. **Caught early** — you see the coil before everyone else. Reward is big,
   risk is small because you got in cheap. But you might be wrong about the
   breakout coming at all.
2. **Confirmed buy** — the breakout is happening today, in front of you.
   Lower risk of being wrong, but you paid a higher price and the upside
   is smaller.

The sweet spot is when **both scores are high**: the setup is still
intact AND today's tape confirms the move. That's the gold-standard entry.

---

## 4. EarlyScore — the 5 ingredients explained simply

EarlyScore is built from **5 ingredients** that get added together to make
a number out of 100. Each ingredient is worth up to 25 points.

Think of it like grading a recipe. The robot tastes the stock and gives a
score to each ingredient.

### Ingredient 1 — Tight Base (up to 25 points)
**Question:** *"Has this stock been boringly flat for the last 10 days?"*

The robot looks at the price range over the last 10 days. If the highest
close and lowest close are within a narrow band, the base is tight.

| 10-day price range | Points | Plain English |
|---|---|---|
| Less than 4% | **25** | Dead-flat. Maximum coil. |
| Less than 6% | 18 | Tight enough. Solid coil. |
| Less than 8% | 10 | Mild base. Some compression. |
| 8% or more | 0 | Too choppy. No coil here. |

**Why it matters**: tight bases store energy. The longer and tighter
a stock sits, the more violent the eventual breakout tends to be.

### Ingredient 2 — Goldilocks Volume (up to 25 points)
**Question:** *"Has volume woken up — but not too much?"*

This one is tricky and very different from how most people think.
The robot looks at today's RVOL (today's volume vs. the 20-day average).

| RVOL | Points | Plain English |
|---|---|---|
| 1.8× to 3.0× | **25** | Sweet spot. Smart money is starting to nibble. |
| 1.5× to 1.8× | 18 | Mild wake-up call. |
| 3.0× to 4.0× | 12 | Getting late — already noticed by others. |
| 1.2× to 1.5× | 8 | Faint interest. Could go either way. |
| Outside those | 0 | Dead, OR already exploded (5×+ means you're late). |

**The big surprise**: high volume is *bad* for EarlyScore. If volume is
5× normal, the move is already happening — you missed the early window.
Sweet spot is 2×: enough to confirm interest, not so much that the news
is already out.

This is *the* signature philosophy of EarlyScore — be early, not at the peak.

### Ingredient 3 — Closing Tell (up to 20 points)
**Question:** *"Did today's candle look bullish at the close?"*

Three things the robot checks at the end of the trading day:

- **Green close** — Did the stock close higher than it opened? (`close > open`)
- **CPR ≥ 60%** — Did the stock close in the **top 40% of the day's range**?
  (CPR = "Close Position in Range" = where the close sits between the
  day's low and high.) A CPR of 1.0 means closed at the day's high.
  A CPR of 0.0 means closed at the day's low.
- **Above yesterday** — Did today close higher than yesterday's close?

| State | Points |
|---|---|
| Green + closed in top 40% + above yesterday | **20** |
| Green + above yesterday (but closed mid-range) | 10 |
| Just above yesterday (red but recovered) | 5 |
| else | 0 |

**Why it matters**: the last hour of trading is when professionals trade.
A stock that runs up all day and closes near its high means buyers were
in control until the bell. That's "the smart money said yes."

### Ingredient 4 — Near Resistance (up to 15 points)
**Question:** *"Is the stock pressing against its 10-day ceiling?"*

The robot finds the highest price over the last 10 days, then checks how
close today's close is to that ceiling.

| Distance to 10-day high | Points |
|---|---|
| Within 2% | **15** |
| Within 4% | 8 |
| Further away | 0 |

**Why it matters**: a stock right under its ceiling is one good day away
from breaking out. Like water rising against a dam — one more push and it
spills over.

### Ingredient 5 — Not Extended (-10 to +15 points)
**Question:** *"Has the stock NOT already run up huge in the last 5 days?"*

This is the *only ingredient that can take points away*. It's the robot's
brake against chasing.

| 5-day return | Points | Plain English |
|---|---|---|
| Less than +8% | **+15** | Fresh, plenty of room to run. |
| 8% to 15% | +8 | Still okay. |
| 15% to 25% | 0 | Getting late, neutral. |
| 25% or more | **-10** | Already up huge. You'd be chasing. |

**Why it matters**: by the time a stock is up 25% in five days, the easy
money is gone. The risk-to-reward is now bad — small upside left, big
downside if it pulls back. This penalty actively discourages the robot
from flagging chasers.

### How the final EarlyScore is computed

```
EarlyScore = Tight Base + Goldilocks Vol + Closing Tell + Near Resistance + Not Extended
           (clipped to 0–100)
```

Then the label is assigned:

- **EARLY** = EarlyScore ≥ 60 AND Goldilocks Vol points ≥ 12
- **WATCH** = EarlyScore ≥ 40
- **NONE** = below 40

The "AND Goldilocks Vol points ≥ 12" rule is important: it means you
**can't be EARLY without an actual volume signal**. A tight base alone is
just a quiet stock. Without volume confirming someone is starting to buy,
the robot won't say "buy now" — at most it'll say "watch."

---

## 5. The main Score — 15 ingredients (the long version)

The main Score (the 0–100 number in the **SCORE** column) uses 15
ingredients. You don't need to memorise them, but here's the list so the
modal makes sense when you click the **Info** button:

| # | Ingredient | What it checks |
|---|---|---|
| 1 | Graduated RVOL | Higher RVOL = more points (rewards big volume — opposite of EarlyScore) |
| 2 | Quiet Accumulation (5D) | 5-day price range tight + cumulative RVOL stacking |
| 3 | Multi-Day Accumulation (10D) | How many of the last 10 days had above-average volume |
| 4 | Volume Acceleration | Is recent volume accelerating vs. older volume? |
| 5 | SMA 200 Position | Price's relationship to the 200-day moving average |
| 6 | OBV Divergence | "On-Balance Volume" — does volume confirm price direction? |
| 7 | Close Position Ratio | Where in the day's range did it close? |
| 8 | Low Float | Smaller companies (fewer shares) can move faster |
| 9 | Price Squeeze (Bollinger Bands) | Volatility compression indicator |
| 10 | Buying Streak | Consecutive green candles with above-average volume |
| 11 | Smart Money | Big volume on up days, small volume on down days |
| 12 | VWAP Proximity | Close to the "Volume-Weighted Average Price" |
| 13 | Pre-Breakout Coil | Tight range + ATR (volatility) shrinking |
| 14 | Late-Entry Penalty | Subtracts points if stock already ran up |
| 15 | Reward:Risk Ratio | Distance to resistance vs. distance to stop-loss |

The main Score is **a vote**. Each ingredient that "passes" adds points.
The final number is capped at 100. **≥ 50 = BUY, ≥ 28 = WAIT.**

The **Late-Entry Penalty** at #14 is the key counterweight that prevents
the system from screaming "BUY!" on a stock that already moved 30%.

---

## 6. The labels on the dashboard

| Label | Color | Meaning |
|---|---|---|
| **BUY** | green | Main Score ≥ 50. Confirmed entry. |
| **WAIT** | yellow | Main Score ≥ 28. Watching, not buying yet. |
| **EARLY** | orange | EarlyScore ≥ 60 + volume tell. Pre-breakout setup, act now. |
| **WATCH** | amber | EarlyScore ≥ 40. Setting up but not ready. |
| **NONE** | gray | No EarlyScore signal. |
| **FRESH** | colored tag | First day this signal fired. Yesterday this stock wasn't BUY/EARLY. |

**FRESH** is the highest-quality version of any signal. A "fresh BUY"
means today is **day 1** of the breakout — yesterday it didn't qualify.
You can't get any earlier than day 1.

---

## 7. The dashboard tabs

The Sniper Scope at the top has four tabs:

- **ALL (N)** — every stock with a non-trivial score (~156 on a typical day)
- **EARLY (N)** — stocks with EarlySignal = EARLY or WATCH (pre-breakout setups)
- **BUY (N)** — stocks with main Signal = BUY (confirmed today)
- **FRESH (N)** — day-1 signals only (the freshest entries from either tab)

Most people should live on the **FRESH** tab. Those are the highest-edge
opportunities. Use **BUY** to see all confirmed buys (including day 2, 3,
etc.), and **EARLY** to scout setups that haven't triggered yet.

---

## 8. The dashboard columns

Reading left to right:

| Column | What it shows |
|---|---|
| TICKER | The stock symbol (e.g. ACIFORMULA). FRESH tag appears here if applicable. |
| PRICE | Today's close. Info icon → 20-day OHLC history. |
| TREND | Arrow showing relationship to SMA 200: ⬆️ uptrend, ↔️ near, ⬇️ downtrend. |
| LAST CLOSING VOL | Volume on the most recent close. |
| CURRENT VOL | Today's live volume (during market hours). |
| PROJECTED VOL | Estimated end-of-day volume based on intraday pace. |
| RVOL | Today's volume ÷ 20-day average. **2.0x** = double normal. |
| EARLY | EarlyScore (0–100) + label (EARLY/WATCH/NONE). |
| SCORE | Main confirmation score (0–100). |
| REASON | Short summary of which ingredients fired. Info icon → full breakdown. |

---

## 9. A full worked example — ACIFORMULA (live numbers)

Today, 2026-06-11, ACIFORMULA's live EarlyScore breakdown looks like this:

**Raw inputs:**
- Today's close: somewhere near ৳142.5 (vs. yesterday's higher close)
- 10-day high: ৳146.4
- 10-day price range: 4.34%
- RVOL: 1.25×
- Day's CPR: 0.12 (closed near the day's low)
- Not green (close ≤ open)
- 5-day return: -1.04% (actually slightly down)

**Ingredient scoring:**

| Ingredient | What it saw | Bucket | Points |
|---|---|---|---|
| Tight Base | range 4.34% | "< 6%" | **+18** |
| Goldilocks Vol | RVOL 1.25× | "1.2 – 1.5×" (faint) | **+8** |
| Closing Tell | red close, CPR 0.12, below prev | nothing passed | **0** |
| Near Resistance | 2.66% below 10d high | "≤ 4%" | **+8** |
| Not Extended | -1.04% in 5 days | "< 8%" | **+15** |
| | | **Total** | **49** |

**Label:** 49 is between 40 and 60 → **WATCH**.

**Translation:** "The setup is still here (tight base, near the ceiling,
not extended) — but today's tape said NO. Volume was meh and the candle
closed at the lows. Don't buy today. Watch for tomorrow's candle to
confirm."

### Why yesterday it was 86 EARLY

Yesterday's snapshot (your dashboard's "Last Update: 2026-06-10") showed
ACIFORMULA at **86 EARLY** with main Score **55 BUY**. What changed
overnight to drop it 37 points?

The two volatile ingredients are **Goldilocks Vol** and **Closing Tell**
(they're worth 45 of the 100 max points). Yesterday probably looked like:

- Goldilocks Vol: RVOL was likely 2.0–2.5× → **+25**
- Closing Tell: green close, CPR > 0.6, above prev → **+20**

Plus the slower ingredients (which barely changed):
- Tight Base +18
- Near Resistance +15 (closer to high yesterday)
- Not Extended +8 (5-day return slightly higher)

**Total: ~86**. Same setup, different tape. The robot is correctly
saying "yesterday the bullish tell fired; today it didn't — wait."

---

## 10. Common situations and what to do

### "Score is high but EarlyScore is NONE"
The stock has already broken out. Buying here is *valid* but *late*. Your
upside is smaller and your stop-loss should be tighter. Size smaller.

### "EarlyScore is EARLY but main Score is WAIT"
The setup is perfect, but the breakout hasn't actually triggered yet.
Don't buy yet. Watch tomorrow's candle. If the main Score crosses 50
tomorrow with FRESH tag, that's your gold-standard entry.

### "Both EarlyScore and main Score are high (the sweet spot)"
This is the dream. The setup is intact AND today's tape is confirming.
Size up. Stops tighter under support.

### "Score dropped overnight from 80 → 40"
Don't panic. Day-to-day scores are volatile because Closing Tell and
Goldilocks Vol shift with each new candle. If the slow ingredients
(Tight Base, Not Extended) are still healthy, the setup is intact —
the stock just needs another good day to re-fire.

### "Stock is on the BUY tab but Score is only 55"
That's normal. The BUY threshold is 50, not 70. After the late-entry
penalty, even healthy buys often score in the 50–65 range. The 70+
scores are rare — usually those are huge breakouts you wouldn't want
to chase anyway.

---

## 11. Glossary (quick reference)

| Term | Meaning |
|---|---|
| **Base / Coil** | Sideways drift in a tight range. Stores energy for a breakout. |
| **Breakout** | When price punches through a long-standing resistance level. |
| **Candle** | The visual representation of one day's OHLC. Green = up day, red = down day. |
| **Close** | The last price of the day. The most important price. |
| **CPR (Close Position in Range)** | Where the close sits between the day's high and low. 1.0 = closed at high. 0.0 = closed at low. |
| **Day-1 Signal** | First day a signal fires. The FRESH tag. |
| **EarlyScore** | The pre-breakout detector score, 0–100. |
| **Late-Entry Penalty** | A points deduction in the main Score for stocks that already moved a lot. |
| **OBV (On-Balance Volume)** | Volume-weighted momentum indicator. |
| **OHLC** | Open, High, Low, Close — the four key prices of a candle. |
| **Resistance** | A price ceiling the stock keeps failing to break. |
| **RVOL (Relative Volume)** | Today's volume ÷ 20-day average volume. |
| **Score (main)** | The confirmation score, 0–100. ≥ 50 = BUY. |
| **SMA (Simple Moving Average)** | Average closing price over N days. SMA 200 = 200-day average. |
| **Support** | A price floor the stock keeps bouncing off. |
| **VWAP** | Volume-Weighted Average Price — the "fair" price weighted by volume. |
| **ATR (Average True Range)** | A measure of daily volatility. Shrinking ATR = coiling. |
| **Bollinger Bands** | Volatility bands around a moving average. Squeezing = coiling. |

---

## 12. The mental model in one paragraph

A stock walks into a bar. The bouncer (main Score) checks 15 things —
mostly "is the stock actually moving right now, with real volume, in the
right direction?" If 50+ points of those checks pass, he says "okay, BUY."
A second bouncer (EarlyScore) checks 5 different things — mostly "was the
stock boringly quiet until just now, and is today the *first day* it's
starting to wake up?" If 60+ points pass *and* there's at least a small
volume tell, he says "EARLY — get in before the crowd notices."

The best entries are when both bouncers say yes on the same day. The
FRESH tag means it's the *first* day they're both saying yes. Those are
the trades the whole system was built to find.

---

*This guide is a snapshot of how the v7 analyzer works (as of 2026-06-11).
The scoring rules live in `src/analyzer.py` if you ever want to peek at
the actual code. Frontend rendering rules are in
`frontend/app/components/SignalsTable.tsx` and `SignalDetailModal.tsx`.*
