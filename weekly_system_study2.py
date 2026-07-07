"""
WEEKLY SYSTEM STUDY, PART 2 — the levers that could make weekly trading viable.

  5. LIMIT ENTRY  — instead of paying the next-morning gap (+1.03% avg), place a
                    limit order 1-2% BELOW the signal close. Flips slippage into
                    a discount. Tested on production + relaxed reversal pools.
  6. REGIME       — condition reversal on market breadth (% liquid > 50-SMA).
                    Why did 2025 fail? Is there a tradeable regime dial?
  7. QUALITY      — fundamentals overlay (static snapshot from prod, so treat
                    pre-2025 results with a LOOKAHEAD caveat: today's EPS was not
                    knowable then).
  8. CANDIDATE    — the combined weekly system spec, measured honestly.

Fills: limit assumed filled at the limit price iff next-day LOW <= limit
(conservative: a gap-down open below the limit actually fills better).
Exit: close at +10 trading days from the SIGNAL day. NET = minus 0.8% round trip.
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
fund = pd.read_sql_query(
    "SELECT ticker,eps,debt_to_equity,sponsor_pct,pe_ratio,market_category,sector FROM fundamentals", con)
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
    if n < 141:
        continue
    close = g['close'].to_numpy(float)
    high = g['high'].to_numpy(float)
    low = g['low'].to_numpy(float)
    opn = g['open'].to_numpy(float)
    vol = g['volume'].to_numpy(float)

    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    hi120 = pd.Series(high).rolling(120, min_periods=120).max().to_numpy()
    rsi = wilder_rsi(close)
    prev = np.roll(close, 1); prev[0] = np.nan
    green = close > prev
    room = np.where(hi120 > 0, (close / hi120 - 1) * 100, np.nan)

    c10 = np.roll(close, -10).astype(float); c10[-10:] = np.nan
    o1 = np.roll(opn, -1).astype(float); o1[-1] = np.nan
    o1 = np.where(o1 > 0, o1, np.nan)
    l1 = np.roll(low, -1).astype(float); l1[-1] = np.nan
    r10_open = (c10 - o1) / o1 * 100

    frames.append(pd.DataFrame(dict(
        ticker=tk, date=g['date'], i=np.arange(n), close=close,
        avgv20=avgv20, rvol=rvol, rsi=rsi, green=green, room=room,
        sma50=sma50, next_low=l1, c10=c10, r10_open=r10_open)))

df = pd.concat(frames, ignore_index=True)
df['liquid'] = (df.avgv20 >= MIN_AVG_VOL20) & (df.close >= MIN_PRICE)
df = df[df.date >= ENTRY_MIN].copy()
df['yr'] = df.date.dt.year
MAXD = df.date.max()
years = (MAXD - ENTRY_MIN).days / 365.25

# market breadth: % of liquid names above 50-SMA per day
liq = df[df.liquid & df.sma50.notna()]
br = liq.groupby('date').apply(lambda d: 100.0 * (d.close > d.sma50).mean()
                               if len(d) >= 30 else np.nan).dropna()
df['breadth'] = df.date.map(br)

df = df.merge(fund, on='ticker', how='left')
df['quality'] = (df.eps.fillna(-1) > 0) & (df.debt_to_equity.fillna(9) < 1.5) \
                & (df.sponsor_pct.fillna(0) >= 30)

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

def limit_stats(pool, disc_pct, label):
    """Limit at close*(1-disc); filled iff next day's low <= limit; exit c10."""
    limit = pool.close * (1 - disc_pct / 100)
    filled = pool[pool.next_low <= limit].copy()
    if len(filled) == 0:
        print(f"  {label:56s} (no fills)"); return None
    fill_px = filled.close * (1 - disc_pct / 100)
    r = (filled.c10 - fill_px) / fill_px * 100
    filled['ret'] = r
    fr = 100 * len(filled) / max(len(pool), 1)
    s = r.dropna(); net = s - COST
    print(f"  {label:56s} fills {len(s):4d}/{len(pool):4d} ({fr:4.1f}%)  "
          f"NET {net.mean():+5.2f}%  win {100*(net>0).mean():4.1f}%")
    return filled

# pools (all deduped to non-overlapping trades)
POOL_PROD = dedup(df[df.liquid & (df.rsi < 30) & df.green & (df.rvol >= 1.5) & (df.room <= -15)])
POOL_R125 = dedup(df[df.liquid & (df.rsi < 30) & df.green & (df.rvol >= 1.25) & (df.room <= -15)])
POOL_RELAX = dedup(df[df.liquid & (df.rsi < 35) & df.green & (df.rvol >= 1.25) & (df.room <= -15)])
POOL_DIP = dedup(df[df.liquid & (df.rsi < 35) & (df.room <= -15)])   # no green/rvol gate: pure dip pool

print("=" * 106)
print(f"SECTION 5 — LIMIT-ORDER ENTRY (fill = next-day low touches limit; exit +10d close; NET of {COST}%)")
print("=" * 106)
print("\n[Reference — market-order at next open]")
stat("PROD REV, next-open fill", POOL_PROD['r10_open'])
stat("RELAX RSI<35 rvol>=1.25, next-open fill", POOL_RELAX['r10_open'])
print("\n[Limit 1% below signal close]")
limit_stats(POOL_PROD, 1, "PROD REV, limit -1%")
limit_stats(POOL_R125, 1, "PROD+rvol1.25, limit -1%")
limit_stats(POOL_RELAX, 1, "RELAX RSI<35 rvol>=1.25, limit -1%")
limit_stats(POOL_DIP, 1, "DIP RSI<35 room>=15 (no rvol/green), limit -1%")
print("\n[Limit 2% below signal close]")
limit_stats(POOL_PROD, 2, "PROD REV, limit -2%")
limit_stats(POOL_R125, 2, "PROD+rvol1.25, limit -2%")
f_relax2 = limit_stats(POOL_RELAX, 2, "RELAX RSI<35 rvol>=1.25, limit -2%")
f_dip2 = limit_stats(POOL_DIP, 2, "DIP RSI<35 room>=15 (no rvol/green), limit -2%")

print("\n" + "=" * 106)
print("SECTION 6 — REGIME: reversal edge by market breadth (non-overlap, next-open fill)")
print("=" * 106)
print("\nAverage breadth by year: ", end="")
for yr, b in df.groupby('yr')['breadth'].mean().items():
    print(f"{yr}:{b:4.0f}% ", end="")
print()
for lo, hi, lbl in [(0, 30, 'breadth < 30 (deep bear)'), (30, 45, 'breadth 30-45 (weak)'),
                    (45, 60, 'breadth 45-60 (neutral)'), (60, 101, 'breadth >= 60 (strong)')]:
    p = POOL_R125[(POOL_R125.breadth >= lo) & (POOL_R125.breadth < hi)]
    stat(f"REV(rvol>=1.25) when {lbl}", p['r10_open'])
print()
for lo, hi, lbl in [(0, 30, 'breadth < 30'), (30, 45, 'breadth 30-45'),
                    (45, 60, 'breadth 45-60'), (60, 101, 'breadth >= 60')]:
    p = POOL_RELAX[(POOL_RELAX.breadth >= lo) & (POOL_RELAX.breadth < hi)]
    stat(f"RELAX RSI<35 when {lbl}", p['r10_open'])

print("\n" + "=" * 106)
print("SECTION 7 — QUALITY OVERLAY (static snapshot — pre-2025 numbers carry LOOKAHEAD, read direction only)")
print("=" * 106)
print(f"\nquality = eps>0 & D/E<1.5 & sponsor>=30%  ({df.drop_duplicates('ticker').quality.sum()} of "
      f"{df.ticker.nunique()} tickers qualify)")
for pool, nm in [(POOL_R125, 'REV(rvol>=1.25)'), (POOL_RELAX, 'RELAX RSI<35'), (POOL_DIP, 'DIP RSI<35')]:
    stat(f"{nm} QUALITY names", pool[pool.quality]['r10_open'])
    stat(f"{nm} non-quality", pool[~pool.quality]['r10_open'])
print("\n[2024+ only — snapshot is closest to truth here]")
for pool, nm in [(POOL_R125, 'REV(rvol>=1.25)'), (POOL_RELAX, 'RELAX RSI<35')]:
    p = pool[pool.yr >= 2024]
    stat(f"{nm} 2024+ QUALITY", p[p.quality]['r10_open'])
    stat(f"{nm} 2024+ non-quality", p[~p.quality]['r10_open'])

print("\n" + "=" * 106)
print("SECTION 8 — CANDIDATE WEEKLY SYSTEM (all conditions together, honest per-year numbers)")
print("=" * 106)
print("""
  SPEC: signal day = liquid & RSI<35 & rvol>=1.25 & >=15% below 120d high & green day
        entry      = LIMIT order next day at signal close -1%  (skip if never touched)
        exit       = +10 trading days (or app's -10%/+25%/20d bracket)
        regime     = only when market breadth >= 30 (skip deep-bear tape)
        quality    = prefer quality names when >1 candidate
""")
cand = POOL_RELAX[POOL_RELAX.breadth >= 30]
limit = cand.close * 0.99
fc = cand[cand.next_low <= limit].copy()
fpx = fc.close * 0.99
fc['ret'] = (fc.c10 - fpx) / fpx * 100
s = fc['ret'].dropna() - COST
print(f"  ALL:      n={len(s)} ({len(s)/years/52:.2f}/wk)  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")
sq = fc[fc.quality]['ret'].dropna() - COST
print(f"  QUALITY:  n={len(sq)} ({len(sq)/years/52:.2f}/wk)  NET {sq.mean():+5.2f}%  win {100*(sq>0).mean():4.1f}%")
print("\n  Per year (ALL):")
for yr, y in fc.groupby('yr'):
    sy = y['ret'].dropna() - COST
    if len(sy):
        print(f"    {yr}  n={len(sy):4d}  NET {sy.mean():+5.2f}%  win {100*(sy>0).mean():4.1f}%")
print("\n  Per year (QUALITY):")
for yr, y in fc[fc.quality].groupby('yr'):
    sy = y['ret'].dropna() - COST
    if len(sy):
        print(f"    {yr}  n={len(sy):4d}  NET {sy.mean():+5.2f}%  win {100*(sy>0).mean():4.1f}%")
print("\nDone.")
