"""
MEASURE the current dse-sniper breakout signal's real historical edge.

Faithful, lookahead-free replication of analyzer.calculate_breakout_signal's 5
gates + the exact production indicator formulas (calculate_indicators), scanned
over the WHOLE clean price history (close>0), not a 5-week window.

For every day a breakout WOULD have fired we record the real forward return at
+5/+10/+20 trading days and the realised P&L under the live exit ruleset
(-7% stop / ATR trail / cal-10 zombie). We compare against the universe baseline
(every stock-day) so we can isolate signal edge from "the market just went up".
"""
import sqlite3
import numpy as np
import pandas as pd

# ---- exact production thresholds (analyzer.__init__) ----
LOOKBACK = 20          # break the 20-day high
TOL = 1.0              # within 1% of (or above) it
MAX_EXT_20D = 12.0     # reject if 20-day return >= 12%
MIN_RVOL = 1.5
MIN_AVG_VOL20 = 50000
MIN_PRICE = 5.0
SMA_PERIOD = 200
RVOL_PERIOD = 20

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0",
    con)
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

fire = []          # one row per breakout firing
uni_r20 = []       # universe baseline: every stock-day's +20d return
ENTRY_MIN = pd.Timestamp('2019-01-01')   # years across multiple regimes

for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < LOOKBACK + 21:
        continue
    close = g['close'].to_numpy(float)
    high = g['high'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy()

    sma200 = pd.Series(close).rolling(SMA_PERIOD, min_periods=1).mean().to_numpy()
    avgv20 = pd.Series(vol).shift(1).rolling(RVOL_PERIOD, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    high20 = pd.Series(high).rolling(LOOKBACK, min_periods=LOOKBACK).max().to_numpy()
    # ATR (Wilder ewm on true range) — production calculate_atr
    prev_close = np.roll(close, 1); prev_close[0] = close[0]
    tr = np.maximum(high - g['low'].to_numpy(float),
                    np.maximum(np.abs(high - prev_close), np.abs(g['low'].to_numpy(float) - prev_close)))
    atr = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().to_numpy()
    rsi = wilder_rsi(close)

    c20 = np.roll(close, 20).astype(float); c20[:20] = np.nan
    ret20 = np.where(c20 > 0, (close - c20)/c20*100, np.nan)
    dist_hi = np.where(high20 > 0, (close/high20 - 1)*100, np.nan)

    for i in range(LOOKBACK + 20, n):           # enough history for all gates
        # universe baseline (only liquid, investable days, +20d forward exists)
        if i + 20 < n and close[i] >= MIN_PRICE and avgv20[i] >= MIN_AVG_VOL20:
            uni_r20.append((close[i+20]-close[i])/close[i]*100)

        if dates[i] < ENTRY_MIN.to_datetime64():
            continue
        ok = (not np.isnan(dist_hi[i]) and dist_hi[i] > -TOL
              and sma200[i] > 0 and close[i] > sma200[i]
              and not np.isnan(ret20[i]) and ret20[i] < MAX_EXT_20D
              and rvol[i] >= MIN_RVOL
              and avgv20[i] >= MIN_AVG_VOL20
              and close[i] >= MIN_PRICE)
        if not ok:
            continue
        entry = close[i]
        rec = dict(ticker=tk, date=pd.Timestamp(dates[i]), entry=entry,
                   r5=np.nan, r10=np.nan, r20=np.nan, realised=np.nan, reason='OPEN')
        for k in (5, 10, 20):
            if i + k < n:
                rec[f'r{k}'] = (close[i+k]-entry)/entry*100
        # realised under live exit rules (-7% / ATR trail / cal-10 zombie)
        peak = entry
        for j in range(i+1, min(i+121, n)):
            cl = close[j]; peak = max(peak, cl)
            mult = 1.0 if rsi[j] > 80 else 1.5 if rsi[j] > 70 else 2.0
            prof = (cl-entry)/entry*100
            cdays = (pd.Timestamp(dates[j]) - pd.Timestamp(dates[i])).days
            if cl <= entry*0.93:
                rec['realised'], rec['reason'] = prof, 'STOP'; break
            if atr[j] > 0 and cl <= peak - mult*atr[j]:
                rec['realised'], rec['reason'] = prof, 'TRAIL'; break
            if cdays > 10 and prof < 2:
                rec['realised'], rec['reason'] = prof, 'ZOMBIE'; break
        else:
            last = close[min(i+120, n-1)]
            rec['realised'] = (last-entry)/entry*100
        fire.append(rec)

f = pd.DataFrame(fire)
ub = np.array(uni_r20)

def stat(name, s):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        print(f"  {name:34s} (none)"); return
    print(f"  {name:34s} n={len(s):5d}  win {100*(s>0).mean():4.1f}%  "
          f"avg {s.mean():+6.2f}%  median {s.median():+6.2f}%")

print("="*78)
print(f"BREAKOUT SIGNAL — historical edge   (entries {ENTRY_MIN.date()} .. {raw['date'].max().date()})")
print("="*78)
print(f"\nTotal breakout firings: {len(f)}   across {f['ticker'].nunique()} stocks")
print("\n[Buy & hold forward return — pure SIGNAL quality]")
stat("Breakout +5 trading days", f['r5'])
stat("Breakout +10 trading days", f['r10'])
stat("Breakout +20 trading days", f['r20'])
print("\n[Universe baseline — EVERY liquid stock-day, +20d]")
stat("Universe +20 trading days", ub)
edge = pd.Series(f['r20']).dropna().mean() - ub.mean()
ew = 100*(pd.Series(f['r20']).dropna()>0).mean() - 100*(ub>0).mean()
print(f"\n  >> EDGE vs universe (+20d): {edge:+.2f}%  avg,  {ew:+.1f} pts win-rate")
print("\n[Realised P&L under LIVE exit rules — what you'd actually pocket]")
stat("All firings (realised)", f['realised'])
print(f"  exit mix: {dict(pd.Series([r for r in f['reason']]).value_counts())}")
print(f"  sum realised: {f['realised'].sum():+.0f}%   per-trade mean: {f['realised'].mean():+.2f}%")

print("\n[By year — consistency check, +20d buy&hold]")
f['yr'] = f['date'].dt.year
for yr, gg in f.groupby('yr'):
    s = gg['r20'].dropna()
    if len(s):
        print(f"  {yr}  n={len(s):4d}  win {100*(s>0).mean():4.1f}%  avg {s.mean():+6.2f}%")
