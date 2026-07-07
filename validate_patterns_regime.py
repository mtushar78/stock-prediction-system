"""
Chart-pattern decision layer vs DSE reality, take 2 — DENSE + REGIME-AWARE.

Extends validate_patterns_pit.py per the audit's own open item (STEP=10 for
larger n) and the 2026-07 weekly-system finding that the reversal edge is
breadth-gated. Questions answered:

  1. With ~4x the samples and data through 2026-07, do bullish confirmations /
     BUY-shaped verdicts still lose money net on DSE?
  2. Does the pattern buy-side come alive in weak tape (breadth < 45) the way
     the quant reversal does?
  3. Do the two previously-positive patterns (triple_bottom, double_bottom_ea)
     survive the bigger sample, and in which regime?
  4. Does the bearish EXIT/AVOID side still correctly predict underperformance
     (worth keeping as a SELL tool)?

Point-in-time: engine sees only bars <= sample date. NET = minus 0.8%.
"""
import sqlite3
import sys
import time
import numpy as np
import pandas as pd

sys.path.insert(0, '.')
from src.pattern_analyzer import PatternAnalyzer

COST = 0.8
WINDOW = 320
STEP = 10
FWD = 20            # primary horizon (matches page framing)
START = pd.Timestamp('2022-01-01')

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])

# ---- market breadth (% liquid names above 50-SMA), same as weekly studies ----
br_frames = []
for tk, g in raw.groupby('ticker', sort=False):
    if len(g) < 60:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    m = (avgv20 >= 50000) & (close >= 5) & ~np.isnan(sma50)
    br_frames.append(pd.DataFrame(dict(date=g['date'].to_numpy()[m], up=(close > sma50)[m])))
br_all = pd.concat(br_frames)
cnt = br_all.groupby('date').size()
breadth = (br_all.groupby('date')['up'].mean() * 100)[cnt >= 30]

pa = PatternAnalyzer()
rows, uni = [], []
t0 = time.time()
n_calls = 0

for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < WINDOW + FWD:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    dates = g['date']
    first = int(np.searchsorted(dates.to_numpy(), START.to_datetime64()))
    for i in range(max(first, WINDOW), n - FWD, STEP):
        if close[i] < 5 or avgv20[i] < 50000:
            continue
        d = dates.iloc[i]
        b = breadth.get(d, np.nan)
        fwd20 = (close[i + FWD] - close[i]) / close[i] * 100
        fwd10 = (close[i + 10] - close[i]) / close[i] * 100
        uni.append(dict(fwd10=fwd10, fwd20=fwd20, breadth=b))
        sub = g.iloc[i - WINDOW + 1:i + 1]
        try:
            res = pa.analyze(sub)
            n_calls += 1
        except Exception:
            continue
        for p in res.get('chart_patterns', []):
            rows.append(dict(
                ticker=tk, date=d, code=p.get('code'),
                direction=p.get('bias'), status=p.get('status'),
                verdict=p.get('verdict'), grade=p.get('grade'),
                edge=p.get('edge'), breadth=b, fwd10=fwd10, fwd20=fwd20))

print(f"# engine calls: {n_calls}  wall: {time.time()-t0:.0f}s")
f = pd.DataFrame(rows)
f.to_csv('pattern_pit_rows_regime.csv', index=False)
ub = pd.DataFrame(uni)
f['yr'] = f.date.dt.year

def stat(name, s, col='fwd20'):
    s = pd.Series(s).dropna()
    if len(s) < 5:
        print(f"  {name:56s} n={len(s):5d}  (too few)"); return
    print(f"  {name:56s} n={len(s):5d}  gross {s.mean():+5.2f}%  NET {(s-COST).mean():+5.2f}%"
          f"  win {100*((s-COST)>0).mean():4.1f}%")

BUCKETS = [(0, 45, 'breadth <45 (weak)'), (45, 101, 'breadth >=45 (strong)')]

print("=" * 106)
print(f"PATTERN DECISION LAYER, DENSE + REGIME  (2022-01 .. {raw['date'].max().date()}, STEP={STEP}, +{FWD}d, NET {COST}%)")
print("=" * 106)
print(f"\nUniverse baseline (+20d): n={len(ub)}  gross {ub.fwd20.mean():+5.2f}%  "
      f"win {100*(ub.fwd20>0).mean():4.1f}%")
for lo, hi, lbl in BUCKETS:
    u = ub[(ub.breadth >= lo) & (ub.breadth < hi)]
    print(f"  baseline {lbl:24s} n={len(u):6d}  gross {u.fwd20.mean():+5.2f}%")

print("\n[1] Bullish verdicts, all regimes (+20d)")
bl = f[f.direction == 'bullish']
for v in ['BUY SETUP', 'WATCH', 'WAIT', 'PLAYED OUT']:
    stat(f"verdict {v}", bl[bl.verdict == v]['fwd20'])
stat("bullish confirmed (any verdict)", bl[bl.status == 'confirmed']['fwd20'])

print("\n[2] Bullish confirmed by REGIME (+20d)")
cb = bl[bl.status == 'confirmed']
for lo, hi, lbl in BUCKETS:
    stat(f"confirmed bullish, {lbl}", cb[(cb.breadth >= lo) & (cb.breadth < hi)]['fwd20'])
print()
for lo, hi, lbl in BUCKETS:
    stat(f"BUY-shaped (BUY SETUP or WATCH), {lbl}",
         bl[bl.verdict.isin(['BUY SETUP', 'WATCH']) & (bl.breadth >= lo) & (bl.breadth < hi)]['fwd20'])

print("\n[3] Per-pattern, confirmed bullish (+20d) — all regimes, then weak tape only")
for code, gg in sorted(cb.groupby('code'), key=lambda kv: -len(kv[1]))[:12]:
    stat(f"{code}", gg['fwd20'])
print("\n  -- weak tape (breadth <45) only --")
cw = cb[cb.breadth < 45]
for code, gg in sorted(cw.groupby('code'), key=lambda kv: -len(kv[1]))[:12]:
    stat(f"{code}", gg['fwd20'])

print("\n[4] The two prior survivors, by regime and horizon")
for code in ['triple_bottom', 'double_bottom_ea', 'double_bottom_aa', 'double_bottom_ae']:
    sub = cb[cb.code == code]
    if len(sub) == 0:
        continue
    stat(f"{code} ALL (+20d)", sub['fwd20'])
    stat(f"{code} weak tape (+20d)", sub[sub.breadth < 45]['fwd20'])
    stat(f"{code} strong tape (+20d)", sub[sub.breadth >= 45]['fwd20'])
    stat(f"{code} weak tape (+10d)", sub[sub.breadth < 45]['fwd10'])

print("\n[5] Bearish side — is EXIT/AVOID still a valid SELL tool? (+20d, vs baseline)")
br = f[f.direction == 'bearish']
stat("bearish confirmed (any)", br[br.status == 'confirmed']['fwd20'])
stat("verdict EXIT / AVOID", br[br.verdict == 'EXIT / AVOID']['fwd20'])
stat("DANGER (dead cat bounce)", f[f.verdict == 'DANGER']['fwd20'])
for lo, hi, lbl in BUCKETS:
    stat(f"EXIT/AVOID, {lbl}", br[(br.verdict == 'EXIT / AVOID') & (br.breadth >= lo) & (br.breadth < hi)]['fwd20'])

print("\n[6] By year — bullish confirmed NET (+20d)")
for yr, y in cb.groupby('yr'):
    s = y['fwd20'].dropna() - COST
    if len(s):
        print(f"  {yr}  n={len(s):5d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")

print("\nDone.")
