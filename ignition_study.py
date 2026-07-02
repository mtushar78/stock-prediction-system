"""
IGNITION detector — can we catch the BEGINNING of a rise?

From docs/WINNER_ANATOMY.md: 93% of big winners did NOT break a 20d high at
launch; 82% launched from quiet volume; 100% from a coil within 10% of the
20d average; ~36% printed a confirming volume spike within 1-3 days of launch
(the "catchable" ones). This tests exactly that catchable moment:

  COIL    prior 10 bars (excl. today) range <= COIL_MAX_RANGE, quiet volume
  CONTEXT above 200-SMA (variant), upper half of 1y range (variant),
          NOT already extended (ret20 excl. today <= MAX_PRIOR_RET20)
  TRIGGER today: close up >= TRIG_RET on rvol >= TRIG_RVOL — the first
          ignition bar OUT OF the coil (today may make a 20d high but the
          stock must not have been trending before)

Forward +10/+20d, NET of 0.8% round-trip. Variants reported honestly —
this ships only if it survives, same bar as everything else.
"""
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
COST = 0.8
ENTRY_MIN = pd.Timestamp('2019-01-01')

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])

rows, uni10 = [], []
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < 300:
        continue
    c = g['close'].to_numpy(float)
    h = g['high'].to_numpy(float)
    lo = g['low'].to_numpy(float)
    v = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy()

    avgv20 = pd.Series(v).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(v, avgv20, out=np.zeros_like(v), where=avgv20 > 0)
    sma200 = pd.Series(c).rolling(200, min_periods=200).mean().to_numpy()
    hi252 = pd.Series(h).rolling(252, min_periods=60).max().to_numpy()
    lo252 = pd.Series(lo).rolling(252, min_periods=60).min().to_numpy()
    # coil metrics on the 10 bars BEFORE today
    r10h = pd.Series(h).shift(1).rolling(10, min_periods=10).max().to_numpy()
    r10l = pd.Series(lo).shift(1).rolling(10, min_periods=10).min().to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        coil_range = np.where(r10l > 0, (r10h - r10l) / r10l * 100, np.nan)
    quiet = pd.Series(rvol).shift(1).rolling(10, min_periods=10).mean().to_numpy()
    c21 = np.roll(c, 21).astype(float); c21[:21] = np.nan
    c1 = np.roll(c, 1); c1[0] = c[0]
    prior_ret20 = np.where(c21 > 0, (c1 - c21) / c21 * 100, np.nan)  # excl today
    day_ret = np.where(c1 > 0, (c - c1) / c1 * 100, np.nan)

    for i in range(260, n - 20):
        if dates[i] < ENTRY_MIN.to_datetime64():
            continue
        if not (avgv20[i] >= 50000 and c[i] >= 5):
            continue
        fwd10 = (c[i+10] - c[i]) / c[i] * 100
        uni10.append(fwd10)
        if np.isnan(coil_range[i]) or np.isnan(prior_ret20[i]):
            continue
        # base gates
        if not (coil_range[i] <= 10.0 and day_ret[i] >= 2.5 and rvol[i] >= 2.0
                and prior_ret20[i] <= 10.0):
            continue
        pos_1y = ((c[i] - lo252[i]) / (hi252[i] - lo252[i])
                  if hi252[i] - lo252[i] > 0 else np.nan)
        rows.append(dict(
            ticker=tk, date=pd.Timestamp(dates[i]),
            day_ret=day_ret[i], rvol=rvol[i], coil=coil_range[i],
            quiet=quiet[i], prior20=prior_ret20[i],
            above200=bool(sma200[i] > 0 and c[i] > sma200[i]),
            pos1y=pos_1y,
            r10=fwd10, r20=(c[i+20] - c[i]) / c[i] * 100 if i + 20 < n else np.nan))

f = pd.DataFrame(rows)
u = pd.Series(uni10)


def stat(name, m, col='r10'):
    s = f.loc[m, col].dropna() - COST
    if len(s) < 30:
        print(f"  {name:52s} n={len(s):5d} (too few)"); return
    g = f.loc[m].dropna(subset=[col])
    yrs = g.groupby(g['date'].dt.year)[col].apply(lambda x: (x - COST).mean())
    print(f"  {name:52s} n={len(s):5d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%"
          f"  +yrs {(yrs>0).sum()}/{len(yrs)}")


print(f"IGNITION STUDY — universe baseline +10d: {u.mean():+.2f}% ({100*(u>0).mean():.1f}% win, n={len(u)})")
print(f"base ignition fires: {len(f)}\n")
print("[+10d NET of 0.8%]")
all_ = f.index >= 0
stat("BASE: coil<=10 + quiet-prior + day>=2.5% rvol>=2", all_)
stat("+ above 200-SMA", f.above200)
stat("+ upper half of 1y range (pos>=0.5)", f.pos1y >= 0.5)
stat("+ quiet coil volume (prior rvol avg <= 1.1)", f.quiet <= 1.1)
stat("+ strong trigger (day>=4%, rvol>=3)", (f.day_ret >= 4) & (f.rvol >= 3))
stat("above200 + pos>=0.5", f.above200 & (f.pos1y >= 0.5))
stat("above200 + quiet<=1.1", f.above200 & (f.quiet <= 1.1))
stat("above200 + pos>=0.5 + quiet<=1.1", f.above200 & (f.pos1y >= 0.5) & (f.quiet <= 1.1))
stat("FULL anatomy: above200+pos+quiet+strong trigger",
     f.above200 & (f.pos1y >= 0.5) & (f.quiet <= 1.1) & (f.day_ret >= 4) & (f.rvol >= 3))
print("\n[+20d NET]")
stat("BASE", all_, 'r20')
stat("above200 + pos>=0.5", f.above200 & (f.pos1y >= 0.5), 'r20')
stat("above200 + pos>=0.5 + quiet<=1.1", f.above200 & (f.pos1y >= 0.5) & (f.quiet <= 1.1), 'r20')
print("\n[by year, above200 + pos>=0.5, NET +10d]")
m = f.above200 & (f.pos1y >= 0.5)
g = f.loc[m].dropna(subset=['r10'])
for yr, y in g.groupby(g['date'].dt.year):
    s = y['r10'] - COST
    print(f"  {yr}  n={len(s):4d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")
f.to_csv('ignition_fires.csv', index=False)
