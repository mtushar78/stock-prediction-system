"""
Does Wyckoff ACCUMULATION-RANGE CONTEXT improve the proven reversal signal?

For every production reversal fire (v10 gates), classify whether it happened as
a structural SPRING — inside/below the support of an established lateral range
(same range definition as src/wyckoff_analyzer) — and compare net forward
returns. If context helps, it ships as a badge/grade factor on the reversal
list; if not, Wyckoff stays annotation-only.
"""
import sys
import sqlite3

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from src.wyckoff_analyzer import (RANGE_WINDOW, RANGE_EXCLUDE,
                                  DOWNTREND_LOOKBACK, DOWNTREND_MIN_PCT,
                                  RANGE_MAX_HEIGHT, RANGE_MIN_HEIGHT,
                                  MIN_AVG_VOL20, MIN_PRICE)

COST = 0.8
ENTRY_MIN = pd.Timestamp('2019-01-01')

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])


def wilder_rsi(close, n=14):
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = pd.Series(up).ewm(alpha=1/n, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/n, adjust=False).mean().values
    rs = np.divide(ru, rd, out=np.full_like(ru, np.nan), where=rd != 0)
    return 100 - 100/(1+rs)


rows = []
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < DOWNTREND_LOOKBACK + RANGE_WINDOW + RANGE_EXCLUDE + 21:
        continue
    close = g['close'].to_numpy(float)
    low = g['low'].to_numpy(float)
    high = g['high'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy()

    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    rsi = wilder_rsi(close)
    hi120 = pd.Series(high).rolling(120, min_periods=120).max().to_numpy()
    # range structure exactly as wyckoff_analyzer.find_trading_range
    sup = (pd.Series(low).rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).min()
           .shift(RANGE_EXCLUDE).to_numpy())
    res = (pd.Series(high).rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).max()
           .shift(RANGE_EXCLUDE).to_numpy())
    peak_before = (pd.Series(high).rolling(DOWNTREND_LOOKBACK, min_periods=30)
                   .max().shift(RANGE_EXCLUDE + RANGE_WINDOW).to_numpy())

    for i in range(140, n - 10):
        if dates[i] < ENTRY_MIN.to_datetime64():
            continue
        if not (avgv20[i] >= MIN_AVG_VOL20 and close[i] >= MIN_PRICE):
            continue
        # production reversal gates (v10)
        with np.errstate(divide='ignore', invalid='ignore'):
            room = (close[i] / hi120[i] - 1) * 100 if hi120[i] > 0 else np.nan
        fire = (rsi[i] < 30 and close[i] > close[i-1] > 0 and rvol[i] >= 1.5
                and not np.isnan(room) and room <= -15.0)
        if not fire:
            continue
        # ---- Wyckoff structural context at this fire ----
        in_range = False
        spring_ctx = False
        if not np.isnan(sup[i]) and sup[i] > 0 and not np.isnan(res[i]):
            height_pct = (res[i] - sup[i]) / sup[i] * 100
            valid_range = RANGE_MIN_HEIGHT <= height_pct <= RANGE_MAX_HEIGHT
            decline_ok = (not np.isnan(peak_before[i]) and peak_before[i] > 0
                          and (peak_before[i] - sup[i]) / peak_before[i] * 100
                          >= DOWNTREND_MIN_PCT)
            if valid_range and decline_ok:
                in_range = True
                # spring context: recent lows undercut the range support and
                # today's close is back at/above it
                recent_lo = float(np.min(low[max(0, i - 3):i + 1]))
                spring_ctx = recent_lo < sup[i] and close[i] >= sup[i] * 0.99
        rec = dict(date=pd.Timestamp(dates[i]), in_range=in_range,
                   spring=spring_ctx, r10=np.nan, r20=np.nan)
        for k in (10, 20):
            if i + k < n:
                rec[f'r{k}'] = (close[i+k] - close[i]) / close[i] * 100
        rows.append(rec)

f = pd.DataFrame(rows)


def stat(name, m, col='r10'):
    s = f.loc[m, col].dropna() - COST
    if len(s) < 10:
        print(f"  {name:48s} n={len(s):4d} (too few)"); return
    g = f.loc[m].dropna(subset=[col])
    yrs = g.groupby(g['date'].dt.year)[col].apply(lambda x: (x - COST).mean())
    print(f"  {name:48s} n={len(s):4d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%"
          f"  +yrs {(yrs>0).sum()}/{len(yrs)}")


print(f"reversal fires total: {len(f)}   in accumulation range: {int(f.in_range.sum())}"
      f"   with spring context: {int(f.spring.sum())}")
print("\n[+10d NET of 0.8%]")
stat("ALL reversal fires (baseline)", f.index >= 0)
stat("reversal INSIDE accumulation range", f.in_range)
stat("reversal + SPRING context (undercut+recover)", f.spring)
stat("reversal outside any range", ~f.in_range)
print("\n[+20d NET]")
stat("ALL reversal fires (baseline)", f.index >= 0, 'r20')
stat("reversal INSIDE accumulation range", f.in_range, 'r20')
stat("reversal + SPRING context", f.spring, 'r20')
stat("reversal outside any range", ~f.in_range, 'r20')
