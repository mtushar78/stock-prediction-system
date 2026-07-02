"""
Does the UI's A-D breakout grade (breakoutGrade.ts weights) actually separate
winners from losers NET of costs? Exact replication of the frontend scoring:
  breadth >=65 ->40 / >=45 ->20 / else 0   (max 40)
  base_tight <5 ->25 / <8 ->15 / <12 ->5   (max 25)
  atr_pct <4 ->20 / <6 ->10                (max 20)
  rvol 1.5-3 ->15 / <=4.5 ->8              (max 15)
  score = pts/max*100;  A>=70, B>=50, C>=30, else D
"""
import sqlite3
import numpy as np
import pandas as pd

COST = 0.8
con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])

# breadth per day
bn, bd = {}, {}
per = {}
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    if len(g) < 60:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    av = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    ok = (av >= 50000) & (close >= 5) & ~np.isnan(sma50)
    ds = g['date'].dt.strftime('%Y-%m-%d').to_numpy()
    for i in np.nonzero(ok)[0]:
        bd[ds[i]] = bd.get(ds[i], 0) + 1
        if close[i] > sma50[i]:
            bn[ds[i]] = bn.get(ds[i], 0) + 1
    per[tk] = g
breadth = {d: 100.0 * bn.get(d, 0) / bd[d] for d in bd if bd[d] >= 30}

rows = []
for tk, g in per.items():
    n = len(g)
    if n < 141:
        continue
    close = g['close'].to_numpy(float); high = g['high'].to_numpy(float)
    low = g['low'].to_numpy(float); vol = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy(); ds = g['date'].dt.strftime('%Y-%m-%d').to_numpy()
    sma200 = pd.Series(close).rolling(200, min_periods=1).mean().to_numpy()
    av = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, av, out=np.zeros_like(vol), where=av > 0)
    high20 = pd.Series(high).rolling(20, min_periods=20).max().to_numpy()
    prevc = np.roll(close, 1); prevc[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prevc), np.abs(low - prevc)))
    atr = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().to_numpy()
    atrp = np.divide(atr, close, out=np.zeros_like(atr), where=close > 0) * 100
    c20 = np.roll(close, 20).astype(float); c20[:20] = np.nan
    ret20 = np.where(c20 > 0, (close - c20) / c20 * 100, np.nan)
    dh = np.where(high20 > 0, (close / high20 - 1) * 100, np.nan)
    r10h = pd.Series(high).rolling(10, min_periods=10).max().to_numpy()
    r10l = pd.Series(low).rolling(10, min_periods=10).min().to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        bt = np.where(r10l > 0, (r10h - r10l) / r10l * 100, np.nan)
    for i in range(140, n - 10):
        if dates[i] < np.datetime64('2019-01-01'):
            continue
        if not (av[i] >= 50000 and close[i] >= 5 and not np.isnan(dh[i]) and dh[i] > -1.0
                and sma200[i] > 0 and close[i] > sma200[i]
                and not np.isnan(ret20[i]) and ret20[i] < 12.0 and rvol[i] >= 1.5):
            continue
        pts = mx = 0
        b = breadth.get(ds[i])
        if b is not None:
            pts += 40 if b >= 65 else 20 if b >= 45 else 0; mx += 40
        if not np.isnan(bt[i]):
            pts += 25 if bt[i] < 5 else 15 if bt[i] < 8 else 5 if bt[i] < 12 else 0; mx += 25
        pts += 20 if atrp[i] < 4 else 10 if atrp[i] < 6 else 0; mx += 20
        pts += 15 if 1.5 <= rvol[i] <= 3 else 8 if rvol[i] <= 4.5 else 0; mx += 15
        sc = 100 * pts / mx if mx else 0
        grade = 'A' if sc >= 70 else 'B' if sc >= 50 else 'C' if sc >= 30 else 'D'
        rows.append(dict(grade=grade, fwd=(close[i+10] - close[i]) / close[i] * 100))

f = pd.DataFrame(rows)
print(f"breakout entries graded: {len(f)}")
for grd in 'ABCD':
    s = f[f.grade == grd]['fwd']
    if len(s):
        print(f"  Grade {grd}  n={len(s):5d}  gross {s.mean():+5.2f}% ({100*(s>0).mean():4.1f}% win)"
              f"  NET {(s-COST).mean():+5.2f}% ({100*((s-COST)>0).mean():4.1f}% win)")
