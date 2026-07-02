"""
COST-ADJUSTED head-to-head: breakout (v9) vs reversal (v10) vs modified variants.

Every prior study (measure_breakout, win_rate_study, exit_study) reported GROSS
returns. Real DSE round-trip cost = 0.4% buy + 0.4% sell = 0.8% (verified from
the user's own purchase_history commission rows). This script re-runs the exact
production gates lookahead-free and reports NET expectancy, plus the buckets
that matter for the "buys at the top" complaint (distance-to-20d-high deciles).

Variants tested
  BRK        v9 breakout as in production (5 gates)
  BRK+REGIME breakout only when market breadth (% liquid names > 50-SMA) >= 55
  BRK+TIGHT  breakout + base_tight(10d range) < 5% + atr_pct < 4 + rvol <= 3
  BRK 5/3    breakout with +5% target / -3% stop bracket (intraday fills)
  REV        v10 reversal as in production (5 gates)
  REV+DEEP   reversal + deep-value (pos_1y <= 0.20 & room to life high >= 50%)
"""
import sqlite3
import numpy as np
import pandas as pd

COST = 0.8            # % round trip (0.4 each side)
LOOKBACK, TOL, MAX_EXT_20D = 20, 1.0, 12.0
MIN_RVOL, MIN_AVG_VOL20, MIN_PRICE = 1.5, 50000, 5.0
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

# ---------- pass 1: market breadth (% of liquid stock-days above 50-SMA) ----
breadth_num, breadth_den = {}, {}
per_ticker = {}
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    if len(g) < 60:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    liquid = (avgv20 >= MIN_AVG_VOL20) & (close >= MIN_PRICE) & ~np.isnan(sma50)
    dates = g['date'].dt.strftime('%Y-%m-%d').to_numpy()
    for i in np.nonzero(liquid)[0]:
        d = dates[i]
        breadth_den[d] = breadth_den.get(d, 0) + 1
        if close[i] > sma50[i]:
            breadth_num[d] = breadth_num.get(d, 0) + 1
    per_ticker[tk] = g
breadth = {d: 100.0 * breadth_num.get(d, 0) / breadth_den[d]
           for d in breadth_den if breadth_den[d] >= 30}

# ---------- pass 2: signals ------------------------------------------------
rows = []
for tk, g in per_ticker.items():
    n = len(g)
    if n < 141:
        continue
    close = g['close'].to_numpy(float)
    high = g['high'].to_numpy(float)
    low = g['low'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy()
    dstr = g['date'].dt.strftime('%Y-%m-%d').to_numpy()

    sma200 = pd.Series(close).rolling(200, min_periods=1).mean().to_numpy()
    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    high20 = pd.Series(high).rolling(20, min_periods=20).max().to_numpy()
    hi120 = pd.Series(high).rolling(120, min_periods=120).max().to_numpy()
    hi252 = pd.Series(high).rolling(252, min_periods=60).max().to_numpy()
    lo252 = pd.Series(low).rolling(252, min_periods=60).min().to_numpy()
    life_high = pd.Series(high).cummax().to_numpy()
    rsi = wilder_rsi(close)
    prev_close = np.roll(close, 1); prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().to_numpy()
    atr_pct = np.divide(atr, close, out=np.zeros_like(atr), where=close > 0) * 100
    c20 = np.roll(close, 20).astype(float); c20[:20] = np.nan
    ret20 = np.where(c20 > 0, (close - c20) / c20 * 100, np.nan)
    dist_hi = np.where(high20 > 0, (close / high20 - 1) * 100, np.nan)
    # 10d range tightness (base)
    r10hi = pd.Series(high).rolling(10, min_periods=10).max().to_numpy()
    r10lo = pd.Series(low).rolling(10, min_periods=10).min().to_numpy()
    base_tight = np.where(r10lo > 0, (r10hi - r10lo) / r10lo * 100, np.nan)

    for i in range(140, n):
        if dates[i] < ENTRY_MIN.to_datetime64():
            continue
        liquid = avgv20[i] >= MIN_AVG_VOL20 and close[i] >= MIN_PRICE
        if not liquid:
            continue
        entry = close[i]

        brk = (not np.isnan(dist_hi[i]) and dist_hi[i] > -TOL
               and sma200[i] > 0 and entry > sma200[i]
               and not np.isnan(ret20[i]) and ret20[i] < MAX_EXT_20D
               and rvol[i] >= MIN_RVOL)
        green = close[i] > close[i-1] > 0
        room = (entry / hi120[i] - 1) * 100 if hi120[i] > 0 else np.nan
        rev = (rsi[i] < 30 and green and rvol[i] >= MIN_RVOL
               and not np.isnan(room) and room <= -15.0)
        if not brk and not rev:
            continue

        rec = dict(ticker=tk, date=pd.Timestamp(dates[i]), kind='BRK' if brk else 'REV',
                   entry=entry, dist_hi=dist_hi[i], rvol=rvol[i],
                   base_tight=base_tight[i], atr_pct=atr_pct[i],
                   breadth=breadth.get(dstr[i], np.nan),
                   r10=np.nan, r20=np.nan, realised=np.nan, bracket=np.nan)
        if brk and rev:
            rec['kind'] = 'BRK'          # never overlaps in practice (RSI)
        pos_1y = ((entry - lo252[i]) / (hi252[i] - lo252[i])
                  if hi252[i] - lo252[i] > 0 else np.nan)
        room_life = (life_high[i] / entry - 1) * 100 if entry > 0 else np.nan
        rec['deep'] = bool(pos_1y == pos_1y and pos_1y <= 0.20
                           and room_life == room_life and room_life >= 50)
        for k in (10, 20):
            if i + k < n:
                rec[f'r{k}'] = (close[i+k] - entry) / entry * 100
        # realised under LIVE exits (-7% / RSI-tightened ATR trail / cal-10 zombie)
        peak = entry
        for j in range(i+1, min(i+121, n)):
            cl = close[j]; peak = max(peak, cl)
            mult = 1.0 if rsi[j] > 80 else 1.5 if rsi[j] > 70 else 2.0
            prof = (cl - entry) / entry * 100
            cdays = (pd.Timestamp(dates[j]) - pd.Timestamp(dates[i])).days
            if cl <= entry * 0.93 or (atr[j] > 0 and cl <= peak - mult * atr[j]) \
               or (cdays > 10 and prof < 2):
                rec['realised'] = prof
                break
        else:
            rec['realised'] = (close[min(i+120, n-1)] - entry) / entry * 100
        # +5%/-3% bracket, intraday fills, stop checked first, 30-bar cap
        tgt, stp = entry * 1.05, entry * 0.97
        filled = False
        for j in range(i+1, min(i+31, n)):
            if low[j] <= stp:
                rec['bracket'] = -3.0; filled = True; break
            if high[j] >= tgt:
                rec['bracket'] = 5.0; filled = True; break
        if not filled and i + 1 < n:
            rec['bracket'] = (close[min(i+30, n-1)] - entry) / entry * 100
        rows.append(rec)

f = pd.DataFrame(rows)

def stat(name, s, cost=COST):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        print(f"  {name:44s} (none)"); return
    net = s - cost
    print(f"  {name:44s} n={len(s):5d}  gross {s.mean():+5.2f}% ({100*(s>0).mean():4.1f}% win)"
          f"  NET {net.mean():+5.2f}% ({100*(net>0).mean():4.1f}% win)")

print("=" * 100)
print(f"COST-ADJUSTED SIGNAL AUDIT  (entries {ENTRY_MIN.date()} .. {raw['date'].max().date()},"
      f"  round-trip cost {COST}%)")
print("=" * 100)

brk = f[f.kind == 'BRK']; rev = f[f.kind == 'REV']
print(f"\nBreakout firings: {len(brk)}   Reversal firings: {len(rev)}")

print("\n[+10 trading days, buy & hold]")
stat("BRK  breakout (production)", brk['r10'])
stat("BRK+REGIME  breadth >= 55%", brk[brk.breadth >= 55]['r10'])
stat("BRK+TIGHT  base<5 atr<4 rvol<=3", brk[(brk.base_tight < 5) & (brk.atr_pct < 4) & (brk.rvol <= 3)]['r10'])
stat("REV  reversal (production)", rev['r10'])
stat("REV+DEEP  deep-value subset", rev[rev.deep]['r10'])

print("\n[+20 trading days, buy & hold]")
stat("BRK  breakout (production)", brk['r20'])
stat("BRK+REGIME  breadth >= 55%", brk[brk.breadth >= 55]['r20'])
stat("BRK+TIGHT", brk[(brk.base_tight < 5) & (brk.atr_pct < 4) & (brk.rvol <= 3)]['r20'])
stat("REV  reversal (production)", rev['r20'])
stat("REV+DEEP", rev[rev.deep]['r20'])

print("\n[Realised under LIVE exit rules (-7%/ATR trail/zombie)]")
stat("BRK  breakout", brk['realised'])
stat("REV  reversal", rev['realised'])

print("\n[+5%/-3% bracket, 30-bar cap, intraday fills]")
stat("BRK  breakout", brk['bracket'])
stat("BRK+REGIME  breadth >= 55%", brk[brk.breadth >= 55]['bracket'])
stat("REV  reversal", rev['bracket'])

print("\n[BRK: forward +10d by distance-to-20d-high bucket — the 'buying the top' question]")
b = brk.dropna(subset=['r10'])
for lo, hi, lbl in [(-1.0, -0.5, 'just under high (-1.0..-0.5%)'),
                    (-0.5, 0.0, 'at the high (-0.5..0%)'),
                    (0.0, 99.0, 'ABOVE the 20d high (>0%)')]:
    s = b[(b.dist_hi > lo) & (b.dist_hi <= hi)]['r10']
    stat(f"dist_hi {lbl}", s)

print("\n[By year, NET +10d]")
for kind, gg in f.groupby('kind'):
    gg = gg.copy(); gg['yr'] = gg['date'].dt.year
    print(f"  {kind}:")
    for yr, y in gg.groupby('yr'):
        s = y['r10'].dropna() - COST
        if len(s):
            print(f"    {yr}  n={len(s):4d}  NET avg {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")

print("\n[Taka expectancy on a 10,000 tk position]")
for lbl, s in [('BRK production (+10d hold)', brk['r10']),
               ('BRK+REGIME (+10d hold)', brk[brk.breadth >= 55]['r10']),
               ('REV production (+10d hold)', rev['r10']),
               ('REV+DEEP (+10d hold)', rev[rev.deep]['r10'])]:
    s = pd.Series(s).dropna() - COST
    if len(s):
        print(f"  {lbl:34s} {s.mean()/100*10000:+7.0f} tk per trade")
