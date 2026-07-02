"""
Wyckoff accumulation entries — historical validation on real DSE data.

Runs src/wyckoff_analyzer.detect_wyckoff_long — the EXACT production function —
point-in-time over the full clean history (close>0), lookahead-free (each call
sees only bars up to the evaluation date). A vectorized pre-screen prunes bars
that cannot possibly fire (no recent undercut/creek-cross), then every
candidate is confirmed by the real function.

Reports, per event type (SPRING / SPRING_TEST / BUEC) and combined:
  - forward +5/+10/+20d buy&hold, gross and NET of 0.8% round-trip commission
  - the BOOK's trade plan simulated: stop below spring low / target = creek +
    range height (cause & effect), intraday touches, 40-bar cap
  - by-year consistency, universe baseline, overlap with the reversal signal
"""
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '.')
from src.wyckoff_analyzer import (detect_wyckoff_long, RANGE_WINDOW,
                                  RANGE_EXCLUDE, DOWNTREND_LOOKBACK,
                                  MIN_AVG_VOL20, MIN_PRICE)

COST = 0.8
ENTRY_MIN = pd.Timestamp('2019-01-01')
NEED = DOWNTREND_LOOKBACK + RANGE_WINDOW + RANGE_EXCLUDE + 1
CTX = 260                      # bars of context handed to the detector

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


# market breadth (% liquid names above 50-SMA) — the one regime factor with
# validated predictive weight (docs/PROFITABILITY_AUDIT.md §3.3)
bn, bd = {}, {}
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    if len(g) < 60:
        continue
    close = g['close'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    sma50 = pd.Series(close).rolling(50, min_periods=50).mean().to_numpy()
    av = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    ok = (av >= MIN_AVG_VOL20) & (close >= MIN_PRICE) & ~np.isnan(sma50)
    ds = g['date'].dt.strftime('%Y-%m-%d').to_numpy()
    for i in np.nonzero(ok)[0]:
        bd[ds[i]] = bd.get(ds[i], 0) + 1
        if close[i] > sma50[i]:
            bn[ds[i]] = bn.get(ds[i], 0) + 1
breadth = {d: 100.0 * bn.get(d, 0) / bd[d] for d in bd if bd[d] >= 30}

rows, uni10, uni20 = [], [], []
checked = 0
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < NEED + 21:
        continue
    close = g['close'].to_numpy(float)
    low = g['low'].to_numpy(float)
    high = g['high'].to_numpy(float)
    vol = g['volume'].to_numpy(float)
    dates = g['date'].to_numpy()

    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    # support/resistance exactly as find_trading_range: window of RANGE_WINDOW
    # bars ending RANGE_EXCLUDE bars back
    sup = (pd.Series(low).rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).min()
           .shift(RANGE_EXCLUDE).to_numpy())
    res = (pd.Series(high).rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).max()
           .shift(RANGE_EXCLUDE).to_numpy())
    lo10 = pd.Series(low).rolling(10, min_periods=1).min().to_numpy()
    hi10c = pd.Series(close).rolling(10, min_periods=1).max().to_numpy()

    # reversal-signal firing (for overlap stat) — production gates
    rsi = wilder_rsi(close)
    hi120 = pd.Series(high).rolling(120, min_periods=120).max().to_numpy()
    rvol_arr = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    prev_c = np.roll(close, 1); prev_c[0] = close[0]
    rev_fire = ((rsi < 30) & (close > prev_c) & (prev_c > 0)
                & (rvol_arr >= 1.5) & (hi120 > 0)
                & ((close / hi120 - 1) * 100 <= -15.0)
                & (avgv20 >= MIN_AVG_VOL20) & (close >= MIN_PRICE))

    for i in range(NEED, n):
        if dates[i] < ENTRY_MIN.to_datetime64():
            continue
        liquid = avgv20[i] >= MIN_AVG_VOL20 and close[i] >= MIN_PRICE
        if liquid:
            if i + 10 < n:
                uni10.append((close[i+10]-close[i])/close[i]*100)
            if i + 20 < n:
                uni20.append((close[i+20]-close[i])/close[i]*100)
        if not liquid or np.isnan(sup[i]):
            continue
        # pre-screen: a fire requires a recent undercut of support or a recent
        # close above resistance — otherwise skip the expensive confirm
        if not (lo10[i] < sup[i] or hi10c[i] > res[i]):
            continue
        checked += 1
        r = detect_wyckoff_long(g.iloc[max(0, i - CTX + 1):i + 1])
        if not r['is_wyckoff']:
            continue
        entry = close[i]
        # ---- book-faithful QUALITY features for the refinement analysis ----
        rs, re_ = i - RANGE_EXCLUDE - RANGE_WINDOW + 1, i - RANGE_EXCLUDE
        half = (rs + re_) // 2
        v1 = float(np.mean(vol[rs:half])) if half > rs else np.nan
        v2 = float(np.mean(vol[half:re_ + 1])) if re_ + 1 > half else np.nan
        absorb = v2 / v1 if v1 and v1 > 0 else np.nan   # <1 = volume drying up
        day_rng = high[i] - low[i]
        cpos = (close[i] - low[i]) / day_rng if day_rng > 0 else 0.5  # demand?
        rec = dict(ticker=tk, date=pd.Timestamp(dates[i]), event=r['event'],
                   entry=entry, rev_overlap=bool(rev_fire[i]),
                   absorb=absorb, cpos=cpos,
                   depth=r['checks'].get('spring_depth_pct'),
                   spring_rvol=r['checks'].get('spring_rvol'),
                   height=r['checks'].get('range_height_pct'),
                   decline=r['checks'].get('decline_into_range_pct'),
                   rsi=float(rsi[i]),
                   breadth=breadth.get(pd.Timestamp(dates[i]).strftime('%Y-%m-%d'), np.nan),
                   r5=np.nan, r10=np.nan, r20=np.nan)
        for k in (5, 10, 20):
            if i + k < n:
                rec[f'r{k}'] = (close[i+k]-entry)/entry*100
        # fresh = no wyckoff fire in the prior 5 bars (episode start)
        rec['fresh'] = not any(
            rr['ticker'] == tk and (rec['date'] - rr['date']).days <= 7
            for rr in rows[-6:])
        # ---- the book's trade plan: stop / cause-effect target ----
        stop = r['checks'].get('stop')
        target = r['checks'].get('target')
        plan = np.nan
        if stop and target and stop < entry < target:
            for j in range(i + 1, min(i + 41, n)):
                if low[j] <= stop:
                    plan = (stop - entry) / entry * 100; break
                if high[j] >= target:
                    plan = (target - entry) / entry * 100; break
            else:
                j = min(i + 40, n - 1)
                plan = (close[j] - entry) / entry * 100
        rec['plan'] = plan
        rec['stop_pct'] = (stop - entry) / entry * 100 if stop else np.nan
        rec['target_pct'] = (target - entry) / entry * 100 if target else np.nan
        rows.append(rec)

f = pd.DataFrame(rows)
u10, u20 = pd.Series(uni10), pd.Series(uni20)


def stat(name, s, cost=COST):
    s = pd.Series(s).dropna()
    if len(s) < 5:
        print(f"  {name:40s} n={len(s):5d}  (too few)"); return
    net = s - cost
    print(f"  {name:40s} n={len(s):5d}  gross {s.mean():+5.2f}% ({100*(s>0).mean():4.1f}% win)"
          f"  NET {net.mean():+5.2f}% ({100*(net>0).mean():4.1f}% win)")


print("=" * 100)
print(f"WYCKOFF ACCUMULATION ENTRIES vs DSE  (entries {ENTRY_MIN.date()} .. "
      f"{raw['date'].max().date()}, cost {COST}%, candidates confirmed: {checked})")
print("=" * 100)
print(f"\nTotal fires: {len(f)}   fresh episodes: {int(f['fresh'].sum()) if len(f) else 0}"
      f"   overlap with reversal signal: {int(f['rev_overlap'].sum()) if len(f) else 0}")
print(f"Universe baseline: +10d {u10.mean():+.2f}% ({100*(u10>0).mean():.1f}% win)"
      f"   +20d {u20.mean():+.2f}% ({100*(u20>0).mean():.1f}% win)")

if len(f):
    print("\n[+10 trading days, buy & hold]")
    stat("ALL wyckoff entries", f['r10'])
    for ev in ('SPRING', 'SPRING_TEST', 'BUEC'):
        stat(f"  {ev}", f[f.event == ev]['r10'])
    stat("ALL, fresh episode only", f[f.fresh]['r10'])
    stat("ALL, excl. reversal-overlap days", f[~f.rev_overlap]['r10'])

    print("\n[+20 trading days, buy & hold]")
    stat("ALL wyckoff entries", f['r20'])
    for ev in ('SPRING', 'SPRING_TEST', 'BUEC'):
        stat(f"  {ev}", f[f.event == ev]['r20'])

    print("\n[The BOOK's trade plan: stop below spring low / cause-effect target, 40-bar cap]")
    stat("ALL wyckoff entries", f['plan'])
    for ev in ('SPRING', 'SPRING_TEST', 'BUEC'):
        stat(f"  {ev}", f[f.event == ev]['plan'])
    ok = f.dropna(subset=['stop_pct', 'target_pct'])
    if len(ok):
        print(f"  avg risk {ok['stop_pct'].mean():.1f}%  avg reward {ok['target_pct'].mean():.1f}%"
              f"  (R:R ~ {abs(ok['target_pct'].mean()/ok['stop_pct'].mean()):.1f})")

    print("\n[By year, NET +10d, all events]")
    f['yr'] = f['date'].dt.year
    for yr, gg in f.groupby('yr'):
        s = gg['r10'].dropna() - COST
        if len(s):
            print(f"  {yr}  n={len(s):4d}  NET avg {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")

    f.to_csv('wyckoff_fires.csv', index=False)
    print("\nraw fires -> wyckoff_fires.csv")
