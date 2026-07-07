# 📗 Your DSE Trading Playbook

**Your personal operating manual for the DSE Sniper app.**
Written 2026-07-07, from your own backtests on 14 years of DSE data. Read this once fully, then keep it as a checklist.

---

## 0. The one sentence that matters most

> **You are a part-time SEASONAL swing trader, not a daily trader. You make money in a few clusters per year by buying panic, and you protect money the rest of the time by doing almost nothing.**

Everything below is just the detail of that sentence.

---

## 1. Why not daily trading? (settled, don't re-litigate)

- DSE settles **T+2** — shares you buy aren't sellable for ~3 days. Intraday round-trips are impossible.
- Round-trip commission is **~0.8%**. To profit daily you'd need to beat that *every day*. Nothing on DSE does.
- Your own test: **forcing a trade every week — by any method, even picking randomly — loses 20–36% of your capital per year.** The losses are just commission grinding you down while the average stock goes nowhere.

**Trading more often is the single most expensive mistake available to you.** The empty screen is the app protecting you, not failing you.

---

## 2. The core idea: the market has two SEASONS

The app measures **market breadth** = the % of liquid stocks trading above their 50-day average. That one number tells you which season you're in. It's shown at the top of the dashboard.

### 🌱 REVERSAL SEASON — breadth **under 45%**
The market is falling, fear is high, stocks are oversold. **This is when you make money.**
- Your backtest: buying reversals here returned **+2.5% to +7.9% net per trade** (the sweet spot is breadth 30–45%, which paid **+7.9% net, 74% win**).
- The **Reversals list** fills up. These are your buys.
- This happens in **clusters, a few times a year** — around selloffs. When it comes, you act.

### 🛡️ PRESERVATION SEASON — breadth **45% or higher** (where you are now: 87.7%)
The market is strong and everything looks like it's going up. **This is a trap for buyers.**
- Your backtest: buying reversals here returns **≈0** net. Buying breakouts/patterns here also ≈0.
- The app marks any reversal fires as **"info only, not high-conviction buys."**
- Your job now is **capital preservation**: hold your winners, build a watchlist, and **do not force new buys.**

**The season is the master switch. Check it before anything else.**

---

## 3. Your weekly routine (15 minutes, once or twice a week)

You do **not** need to watch the screen daily. Here is the whole loop:

```
1. Open the dashboard. LOOK AT THE SEASON BANNER FIRST.
   └─ Green 🌱 "Reversal Season"?  → go to step 2 (hunt)
   └─ Amber 🛡️ "Preservation Season"? → go to step 4 (protect)

2. HUNT (reversal season only):
   - Open the Reversals list.
   - Pick 2–4 with the best GRADE (A/B) and a DEEP VALUE badge.
   - Size each position (see §4). Place the buys.
   - Write each one in your journal (§9) with its stop and target.

3. Done hunting. Close the app.

4. PROTECT (preservation season):
   - Check the red alert box for any SELL signals on stocks you hold.
   - Glance at your open positions vs their stops/targets.
   - See a tempting stock? Don't buy — add it to your watchlist for next season.
   - Close the app. Doing nothing today is the correct move.
```

The app now rings a **🔔 "Season just changed"** bell the day breadth crosses 45%, so you'll know the moment hunting season opens without watching daily.

---

## 4. How to size a position (do this every time)

**Rule: never let one trade lose more than ~1% of your total money.**

Your reversal stop is **−10%**. So:

```
Position size  =  (1% of total capital)  ÷  (10% stop)  =  ~10% of your capital per trade
```

**Worked example — ৳500,000 total capital:**
- 1% of capital = ৳5,000 (the most you'll lose if stopped out)
- Position size = ৳5,000 ÷ 0.10 = **৳50,000 per stock** (10% of capital)
- Buy 2–4 such positions in a reversal cluster = 20–40% of capital deployed, the rest in cash.

**Never** put more than ~10% in one name. **Never** go all-in. Cash is a position — in preservation season it's your best one.

⚠️ **Liquidity check before you buy:** if the app tags a stock **THIN**, skip it — you won't be able to sell it. On any stock, keep your order under ~10–20% of its average daily volume or your own buying moves the price against you.

---

## 5. Exit rules (decide these the moment you buy — never improvise)

For every reversal you buy, set all three up front:

| Exit | Level | Why |
|---|---|---|
| **Stop loss** | **−10%** from your entry | Wider than a breakout because a reversal is a falling knife by design. |
| **Target** | **+25%** | Where reversals historically run to. |
| **Time stop** | **~20 trading days** (≈4 weeks) | If it hasn't worked by then, the thesis is stale — free the capital. |

**Iron rule: never average down.** If a reversal keeps falling, your stop takes you out. Adding more to a loser is how accounts die on DSE (oversold can always get more oversold in a downtrend).

---

## 6. Reading the app, screen by screen

| Screen | What it's for | How to use it |
|---|---|---|
| **Season banner** (top) | The master switch | Check it first, every session. Green = hunt, amber = protect. |
| **Reversals list** | Your buy list | Only high-conviction in 🌱 season. Sort by grade; prefer DEEP VALUE. |
| **Breakouts list** | Reference only | Nets ~+0.3% (breakeven after costs). A watchlist, **not** a buy list. |
| **Overheated flags** | Risk warnings | Tells you a stock you hold has run too hot — consider taking profit. Don't buy these. |
| **Portfolio + red Alerts** | Your positions & exits | The red box = act now (a stop/target hit). Check it every session. |
| **Chart Analysis page** | **Learning & context ONLY** | Read structure, support/resistance, risk tags. **Do not buy off its patterns** — see §7. |
| **Quality screen** | Fundamental safety | A tiebreaker (prefer sound companies), not a buy signal by itself. |
| **Time Machine** (date bar) | Study past seasons | Rewind to a past selloff and see what the Reversals list looked like — free training. |

---

## 7. Why you must NOT trade off the Chart Analysis page

You've been leaning on this page. Here is the hard data, from **24,781 point-in-time tests** on DSE:

- **Confirmed bullish chart patterns returned exactly the same as a random stock** (−0.2% before costs, ≈−1.0% after). The patterns carry **no buying edge** on DSE.
- The US textbook targets ("+29% on this Cup & Handle") **do not transfer** to DSE. The page now shows the *real* DSE-measured number next to each.
- Patterns *feel* like they work right now only because the whole market is rising (preservation season) — the same patterns **lost −4.5%/trade in 2024**.

**Keep using the page to *understand* a stock — never to decide to buy it.** Buys come from the Reversals list. That's the only signal that survived honest testing.

---

## 8. The 7 hard rules (print these)

1. **Check the season first.** Green = hunt, amber = protect. Nothing else matters more.
2. **Buy panic, not strength.** Reversals in weak tape. Never chase what's already up.
3. **Never risk >1% of capital per trade** (≈10% position against a −10% stop).
4. **Set stop / target / time-stop the moment you buy.** Never improvise an exit.
5. **Never average down.** Let the stop do its job.
6. **Charts are for looking, the Reversals list is for buying.**
7. **Doing nothing is a valid, often correct, move.** Cash in preservation season is a position.

---

## 9. Trade journal (keep this — it's how you learn if it really works)

The app records your sells and realized P&L. But keep your *own* log too, because the real test is whether your live results match the backtest. For every trade:

| Date | Ticker | Season | Entry | Stop | Target | Grade | Exit date | Exit price | Net % | Followed plan? |
|---|---|---|---|---|---|---|---|---|---|---|

After ~15–20 trades, ask: **is my real net per trade near +3%?** If yes, the edge is real for you — scale up slowly. If no, stay small and find out why (usually: traded out of season, or didn't respect stops).

---

## 10. The honest limits (what this app will *not* do for you)

- It will **not** give you a trade every day, or every week. Dry spells of weeks are normal and correct.
- It will **not** make you rich quickly. Realistically this is a **modest, part-time, seasonal income** — not a salary. **Do not quit your job for it.**
- The edge is **one strategy in one small market**. Respect that concentration; don't bet the house.
- The +3–4%/trade is a *backtest*. **Prove it with small real money for a few months first**, log every fill, and only scale up once your live results confirm it.

---

## 11. The evidence behind all of this (reproducible)

Every claim here comes from lookahead-free, cost-adjusted backtests on your own 14-year DSE database. Re-run them any time:

```
python weekly_system_study.py       # reversal frequency, validity, weekly-rotation test
python weekly_system_study2.py      # limit entries, regime buckets, quality overlay
python weekly_system_study3.py      # strong-tape candidates by regime
python validate_patterns_regime.py  # dense chart-pattern re-validation (24,781 samples)
python breakout_cost_audit.py       # breakout vs reversal, net of costs
```

Written up in `docs/PROFITABILITY_AUDIT.md` (see §9 for the chart-pattern verdict).

---

*Bottom line: wait for green, buy panic small, set your exits, and sit on your hands the rest of the time. That's the whole game on DSE.*
