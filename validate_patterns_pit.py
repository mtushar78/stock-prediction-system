"""
Point-in-time validation of the chart-pattern engine's DECISION layer on DSE.

Bulkowski's stats (avg move, fail rate) are US bull-market numbers; the edge
score / grade / verdict built on them has never been checked against DSE
outcomes. This runs PatternAnalyzer.analyze() on history truncated at sample
dates (no look-ahead), collects actionable bullish verdicts, and measures real
forward returns vs the liquid-universe baseline. NET = minus 0.8% round trip.
"""
import sqlite3
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, '.')
from src.pattern_analyzer import PatternAnalyzer

COST = 0.8
WINDOW = 320          # bars of history given to the engine (page uses ~300)
STEP = 42             # sample every ~2 months of trading days
FWD = 20

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])

pa = PatternAnalyzer()
rows, uni = [], []
start = pd.Timestamp('2023-01-01')

for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < WINDOW + FWD:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    first = int(np.searchsorted(g['date'].to_numpy(), start.to_datetime64()))
    for i in range(max(first, WINDOW), n - FWD, STEP):
        if close[i] < 5 or avgv20[i] < 50000:
            continue
        fwd = (close[i + FWD] - close[i]) / close[i] * 100
        uni.append(fwd)
        sub = g.iloc[i - WINDOW + 1:i + 1]
        try:
            res = pa.analyze(sub)
        except Exception:
            continue
        for p in res.get('chart_patterns', []):
            rows.append(dict(
                ticker=tk, date=g['date'].iloc[i], code=p.get('code'),
                direction=p.get('bias'), status=p.get('status'),
                verdict=p.get('verdict'), grade=p.get('grade'),
                edge=p.get('edge'), fwd=fwd))

f = pd.DataFrame(rows)
f.to_csv('pattern_pit_rows.csv', index=False)
ub = pd.Series(uni)

def stat(name, s):
    s = pd.Series(s).dropna()
    if len(s) < 5:
        print(f"  {name:46s} n={len(s):4d}  (too few)"); return
    print(f"  {name:46s} n={len(s):4d}  gross {s.mean():+5.2f}% ({100*(s>0).mean():4.1f}% win)"
          f"  NET {(s-COST).mean():+5.2f}%")

print("=" * 100)
print(f"CHART-PATTERN DECISION LAYER vs DSE REALITY  (+{FWD}d fwd, samples every {STEP} bars, 2023-2026)")
print("=" * 100)
print(f"\nUniverse baseline: n={len(ub)}  gross {ub.mean():+5.2f}% ({100*(ub>0).mean():4.1f}% win)")
print(f"Pattern readings collected: {len(f)}")

print("\n[By verdict — bullish patterns]")
bl = f[f.direction == 'bullish']
for v in ['BUY SETUP', 'WATCH', 'WAIT', 'PLAYED OUT']:
    stat(f"verdict {v}", bl[bl.verdict == v]['fwd'])

print("\n[BUY SETUP by grade]")
bs = bl[bl.verdict == 'BUY SETUP']
for grd in ['A', 'B', 'C', 'D']:
    stat(f"BUY SETUP grade {grd}", bs[bs.grade == grd]['fwd'])

print("\n[Bearish patterns — do EXIT/AVOID verdicts predict drops?]")
br = f[f.direction == 'bearish']
stat("bearish confirmed (any verdict)", br[br.status == 'confirmed']['fwd'])
stat("verdict EXIT / AVOID", br[br.verdict == 'EXIT / AVOID']['fwd'])
stat("DANGER (dead cat bounce)", f[f.verdict == 'DANGER']['fwd'])

print("\n[Top bullish pattern codes by frequency, confirmed only]")
cb = bl[bl.status == 'confirmed']
for code, gg in sorted(cb.groupby('code'), key=lambda kv: -len(kv[1]))[:10]:
    stat(f"{code}", gg['fwd'])
