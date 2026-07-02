"""
Can the breakout win rate be pushed toward 70%? Measure the trade-offs.

Entry = the v9 breakout rule (20d-high, not extended, uptrend, liquid).
For each exit policy we report WIN RATE and AVG RETURN per trade (and per year),
plus a market-regime filter (only take breakouts when market breadth is healthy).

Fills are intraday: target fills if the day's HIGH reaches it; stop fills if the
day's LOW reaches it; if both in one day, assume the STOP first (conservative).
Local data (~14 yrs). Read-only.
"""
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager
db = DatabaseManager()

series = {}
entries = []           # (ticker, idx, date, year)
breadth_rows = []      # for market regime

for t in db.get_all_tickers():
    df = db.get_stock_data(t)
    if len(df) < 260:
        continue
    df = df[df['close'] > 0].sort_values('date').reset_index(drop=True)
    if len(df) < 260:
        continue
    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    sma50 = c.rolling(50).mean(); sma200 = c.rolling(200).mean()
    av20 = v.rolling(20).mean(); hi20 = h.rolling(20).max(); ret20 = c.pct_change(20) * 100
    dates = pd.to_datetime(df['date'])
    series[t] = dict(c=c.values, h=h.values, l=l.values, date=dates.values)
    liquid = (av20 >= 50000) & (c >= 5)
    # breakout entries
    mask = ((c / hi20 - 1) * 100 > -1) & (ret20 < 12) & (v / av20 > 1.5) & (c > sma200) & liquid
    for i in np.where(mask.fillna(False).values)[0]:
        if i + 30 < len(c):
            entries.append((t, i, str(df['date'].iloc[i])[:10], dates.iloc[i].year))
    # breadth contribution: is this liquid name above its 50-day SMA?
    bf = pd.DataFrame({'d': df['date'].astype(str).str[:10], 'above': (c > sma50).astype(float), 'liquid': liquid.astype(int)})
    bf = bf[bf['liquid'] == 1]
    breadth_rows.append(bf[['d', 'above']])

# market breadth per date = fraction of liquid names above their 50-day SMA
B = pd.concat(breadth_rows, ignore_index=True).groupby('d')['above'].mean()
breadth = B.to_dict()
print(f"Breakout entries: {len(entries)} | breadth dates: {len(breadth)}")

def simulate(t, i, target, stop, maxhold):
    s = series[t]; buy = s['c'][i]; n = len(s['c'])
    tp = buy * (1 + target / 100); sl = buy * (1 - stop / 100)
    for step in range(1, maxhold + 1):
        j = i + step
        if j >= n: break
        lo, hi, cl = s['l'][j], s['h'][j], s['c'][j]
        if lo <= sl: return -stop                  # stop checked first (conservative)
        if hi >= tp: return target
    j = min(i + maxhold, n - 1)
    return (s['c'][j] - buy) / buy * 100

def run(name, target, stop, maxhold, regime_min=None):
    rows = []
    for (t, i, d, y) in entries:
        if regime_min is not None and breadth.get(d, 1.0) < regime_min:
            continue
        rows.append((simulate(t, i, target, stop, maxhold), y))
    r = pd.DataFrame(rows, columns=['ret', 'year'])
    if len(r) == 0:
        print(f"{name:46s} (no trades)"); return
    win = (r['ret'] > 0).mean() * 100
    yrs = sorted(y for y in r['year'].unique() if y >= 2019)
    per = " ".join(f"{(r[r.year==y]['ret']>0).mean()*100:3.0f}" if (r.year==y).sum() >= 15 else "  ." for y in yrs)
    print(f"{name:46s} n={len(r):4d}  WIN {win:3.0f}%  avg {r['ret'].mean():+5.2f}%  sum {r['ret'].sum():+7.0f}%  | win/yr {per}")

print("\n" + "=" * 110)
print("EXIT-POLICY SWEEP on the breakout entry — WIN RATE vs RETURN (and win% per year 2019+)")
print("=" * 110)
run("baseline: +none / -7% trail-ish (30d hold)", 999, 7, 30)
run("target +5% / stop -7%", 5, 7, 30)
run("target +4% / stop -6%", 4, 6, 30)
run("target +3% / stop -5%", 3, 5, 30)
run("target +3% / stop -4%", 3, 4, 20)
run("target +2.5% / stop -4%", 2.5, 4, 15)
run("target +2% / stop -3%", 2, 3, 12)
print("\n--- same, but ONLY in healthy market (breadth > 55% above 50-SMA) ---")
run("regime + target +5% / stop -7%", 5, 7, 30, 0.55)
run("regime + target +4% / stop -6%", 4, 6, 30, 0.55)
run("regime + target +3% / stop -5%", 3, 5, 30, 0.55)
run("regime + target +3% / stop -4%", 3, 4, 20, 0.55)
print("\n--- stricter regime (breadth > 65%) ---")
run("regime65 + target +4% / stop -6%", 4, 6, 30, 0.65)
run("regime65 + target +3% / stop -5%", 3, 5, 30, 0.65)
print("\n--- regime filter but RIDE winners (no target) — keep upside? ---")
run("regime55, ride (no target, -7%, 30d)", 999, 7, 30, 0.55)
run("regime65, ride (no target, -7%, 30d)", 999, 7, 30, 0.65)
run("regime65, ride (no target, -8%, 40d)", 999, 8, 40, 0.65)
