"""
WEEKLY SYSTEM STUDY, PART 3 — what works in STRONG tape (breadth >= 55-60)?

Today's breadth is ~68% (strongest regime in the dataset) and the reversal edge
is measured dead there. Before telling the user "sit idle", test the strong-tape
candidates, all non-overlapping, next-open fills, NET of 0.8%:

  P1  PULLBACK-IN-UPTREND  close>200-SMA, 5d return <= -3% (a real dip),
                           green day (turn), liquid — the "buy the dip in a
                           winner" play that should suit a strong market.
  P2  P1 + rvol >= 1.25    volume-confirmed turn.
  M1  MOMENTUM WINNERS     top-decile 20d return among liquid names that day,
                           i.e. buy the strongest, hold 10d.
  B1  BREAKOUT (v9 gates)  the production breakout for reference.

Each is reported by breadth bucket to find the regime where it pays.
"""
import sqlite3
import numpy as np
import pandas as pd

COST = 0.8
MIN_AVG_VOL20, MIN_PRICE = 50000, 5.0
ENTRY_MIN = pd.Timestamp('2019-01-01')

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
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

frames = []
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < 221:
        continue
    close = g['close'].to_numpy(float)
    high = g['high'].to_numpy(float)
    opn = g['open'].to_numpy(float)
    vol = g['volume'].to_numpy(float)

    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    sma200 = pd.Series(close).rolling(200, min_periods=200).mean().to_numpy()
    high20 = pd.Series(high).rolling(20, min_periods=20).max().to_numpy()
    rsi = wilder_rsi(close)
    prev = np.roll(close, 1); prev[0] = np.nan
    green = close > prev
    c5 = np.roll(close, 5).astype(float); c5[:5] = np.nan
    ret5 = np.where(c5 > 0, (close - c5) / c5 * 100, np.nan)
    c20 = np.roll(close, 20).astype(float); c20[:20] = np.nan
    ret20 = np.where(c20 > 0, (close - c20) / c20 * 100, np.nan)
    dist_hi = np.where(high20 > 0, (close / high20 - 1) * 100, np.nan)

    c10 = np.roll(close, -10).astype(float); c10[-10:] = np.nan
    o1 = np.roll(opn, -1).astype(float); o1[-1] = np.nan
    o1 = np.where(o1 > 0, o1, np.nan)
    r10_open = (c10 - o1) / o1 * 100

    frames.append(pd.DataFrame(dict(
        ticker=tk, date=g['date'], i=np.arange(n), close=close,
        avgv20=avgv20, rvol=rvol, rsi=rsi, green=green, ret5=ret5, ret20=ret20,
        sma50=sma50, sma200=sma200, dist_hi=dist_hi, r10_open=r10_open)))

df = pd.concat(frames, ignore_index=True)
df['liquid'] = (df.avgv20 >= MIN_AVG_VOL20) & (df.close >= MIN_PRICE)
df = df[df.date >= ENTRY_MIN].copy()
df['yr'] = df.date.dt.year
MAXD = df.date.max()
years = (MAXD - ENTRY_MIN).days / 365.25

liq = df[df.liquid & df.sma50.notna()]
br = liq.groupby('date').apply(lambda d: 100.0 * (d.close > d.sma50).mean()
                               if len(d) >= 30 else np.nan).dropna()
df['breadth'] = df.date.map(br)

# momentum decile rank per day among liquid names
df['mom_rank'] = df[df.liquid].groupby('date')['ret20'].rank(pct=True)

def dedup(c, gap=10):
    c = c.sort_values(['ticker', 'i'])
    keep, last = [], {}
    for r in c.itertuples():
        if r.ticker not in last or r.i - last[r.ticker] >= gap:
            keep.append(True); last[r.ticker] = r.i
        else:
            keep.append(False)
    return c[np.array(keep, dtype=bool)] if len(c) else c

def stat(name, s, cost=COST):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        print(f"  {name:56s} (none)"); return
    net = s - cost
    print(f"  {name:56s} n={len(s):5d} ({len(s)/years/52:4.2f}/wk)  gross {s.mean():+5.2f}%"
          f"  NET {net.mean():+5.2f}%  win {100*(net>0).mean():4.1f}%")

P1 = dedup(df[df.liquid & (df.close > df.sma200) & (df.ret5 <= -3) & df.green])
P2 = dedup(df[df.liquid & (df.close > df.sma200) & (df.ret5 <= -3) & df.green & (df.rvol >= 1.25)])
M1 = dedup(df[df.liquid & (df.mom_rank >= 0.9)])
B1 = dedup(df[df.liquid & (df.dist_hi > -1.0) & (df.close > df.sma200)
              & (df.ret20 < 12) & (df.rvol >= 1.5)])

BUCKETS = [(0, 30, 'breadth <30'), (30, 45, 'breadth 30-45'),
           (45, 60, 'breadth 45-60'), (60, 101, 'breadth >=60')]

print("=" * 106)
print(f"STRONG-TAPE CANDIDATES by regime  (non-overlap, next-open fill, +10d, NET {COST}%; data to {MAXD.date()})")
print("=" * 106)
for pool, nm in [(P1, 'P1 PULLBACK uptrend dip>=3% green'),
                 (P2, 'P2 PULLBACK + rvol>=1.25'),
                 (M1, 'M1 MOMENTUM top-decile 20d'),
                 (B1, 'B1 BREAKOUT v9 gates')]:
    print(f"\n  -- {nm} --")
    stat("ALL regimes", pool['r10_open'])
    for lo, hi, lbl in BUCKETS:
        p = pool[(pool.breadth >= lo) & (pool.breadth < hi)]
        stat(lbl, p['r10_open'])

print("\n[Per-year NET for the pools in strong tape only (breadth >= 55)]")
for pool, nm in [(P1, 'P1 PULLBACK'), (P2, 'P2 PULLBACK+vol'), (M1, 'M1 MOMENTUM'), (B1, 'B1 BREAKOUT')]:
    p = pool[pool.breadth >= 55]
    print(f"\n  {nm} (breadth>=55):")
    for yr, y in p.groupby('yr'):
        s = y['r10_open'].dropna() - COST
        if len(s):
            print(f"    {yr}  n={len(s):4d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")

print("\nDone.")
