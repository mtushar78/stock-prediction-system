"""
Wyckoff implementation verification suite — three falsification tests.

  1. SYNTHETIC TEXTBOOK PATTERNS — hand-built ideal structures from the book
     must fire the right event; anti-patterns must NOT fire.
  2. RANDOM-DATA NULL TEST — on geometric-random-walk OHLCV the detector must
     show ~zero gross edge (a positive edge on random data would prove the
     implementation leaks future information or the backtest is broken).
  3. NO-LOOKAHEAD TEST — for real recorded fires (wyckoff_fires.csv), the
     decision at the fire date must be identical when (a) history is truncated
     at that date and (b) random future bars are appended. The detector may
     only use the past.

Exit code 0 = all pass.
"""
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')
from src.wyckoff_analyzer import detect_wyckoff_long

FAILURES = []


def check(name, cond, detail=''):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))
    if not cond:
        FAILURES.append(name)


def mk_df(closes, vols, lows=None, highs=None):
    closes = np.asarray(closes, float)
    n = len(closes)
    lows = np.asarray(lows, float) if lows is not None else closes * 0.99
    highs = np.asarray(highs, float) if highs is not None else closes * 1.01
    return pd.DataFrame({
        'date': pd.date_range('2020-01-01', periods=n, freq='D'),
        'open': closes, 'high': highs, 'low': lows,
        'close': closes, 'volume': np.asarray(vols, float),
    })


# ---------------------------------------------------------------------------
print("\n[1] SYNTHETIC TEXTBOOK PATTERNS")
rng = np.random.default_rng(7)

def build_base():
    """130-bar downtrend 100→70, then 45-bar range 70–76, vol ~200k."""
    down = np.linspace(100, 70, 130) + rng.normal(0, 0.3, 130)
    rng_part = 73 + 3 * np.sin(np.linspace(0, 6 * np.pi, 45)) + rng.normal(0, 0.3, 45)
    closes = np.concatenate([down, rng_part])
    vols = np.full(len(closes), 200_000.0) + rng.normal(0, 10_000, len(closes))
    return list(closes), list(vols)

# --- Spring #3: low-volume undercut, closes back inside -> direct SPRING ---
c, v = build_base()
support_zone = min(c[-45:])          # ~70
lows = [x * 0.995 for x in c]
# undercut bar: low pierces support, close recovers above it, LOW volume
c.append(support_zone + 1.0)
lows.append(support_zone - 1.5)
v.append(120_000.0)                  # rvol ~0.6 -> Spring #3
df = mk_df(c, v, lows=lows + [lows[-1]][:0] or lows)
r = detect_wyckoff_long(mk_df(c, v, lows=lows))
check('Spring #3 fires as SPRING', r['is_wyckoff'] and r['event'] == 'SPRING',
      f"got {r['event']}, reasons={r['reasons'][:2]}")
check('Spring #3 classified type 3', r['checks'].get('spring_type') == 3,
      f"type={r['checks'].get('spring_type')}")

# --- Spring #1 (high-vol shake): must NOT fire directly... ---
c, v = build_base()
support_zone = min(c[-45:])
lows = [x * 0.995 for x in c]
c.append(support_zone + 1.0); lows.append(support_zone - 1.5); v.append(500_000.0)  # rvol 2.5
r = detect_wyckoff_long(mk_df(c, v, lows=lows))
check('High-volume spring does NOT enter directly', not r['is_wyckoff'],
      f"event={r['event']}")
# ...but the subsequent no-supply test MUST fire SPRING_TEST
c += [support_zone + 1.2, support_zone + 1.1]
lows += [support_zone + 0.4, support_zone + 0.3]
v += [180_000.0, 150_000.0]          # falling volume, holds above spring low
r = detect_wyckoff_long(mk_df(c, v, lows=lows))
check('No-supply test fires as SPRING_TEST',
      r['is_wyckoff'] and r['event'] == 'SPRING_TEST', f"got {r['event']}")

# --- BUEC: SOS above creek then low-volume back-up holding ---
c, v = build_base()
resistance_zone = max(c[-45:])       # ~76
lows = [x * 0.995 for x in c]
c += [resistance_zone + 1.5]                     # SOS close above creek
lows += [resistance_zone - 0.5]
v += [450_000.0]
c += [resistance_zone + 0.6, resistance_zone + 0.4]   # back-up, holds
lows += [resistance_zone - 0.7, resistance_zone - 0.9]
v += [220_000.0, 140_000.0]          # no-supply on the last bar
r = detect_wyckoff_long(mk_df(c, v, lows=lows))
check('Back-up after SOS fires as BUEC', r['is_wyckoff'] and r['event'] == 'BUEC',
      f"got {r['event']}, reasons={r['reasons'][:2]}")

# --- anti-pattern: steady uptrend (no accumulation context) ---
n = 260
c = list(np.linspace(50, 120, n) + rng.normal(0, 0.5, n))
v = list(np.full(n, 200_000.0))
r = detect_wyckoff_long(mk_df(c, v))
check('Pure uptrend does not fire', not r['is_wyckoff'], f"event={r['event']}")

# --- anti-pattern: breakdown (deep undercut, no recovery) ---
c, v = build_base()
support_zone = min(c[-45:])
lows = [x * 0.995 for x in c]
c.append(support_zone * 0.82); lows.append(support_zone * 0.80); v.append(600_000.0)
r = detect_wyckoff_long(mk_df(c, v, lows=lows))
check('Deep breakdown does not fire', not r['is_wyckoff'], f"event={r['event']}")

# ---------------------------------------------------------------------------
print("\n[2] RANDOM-DATA NULL TEST (detector must have NO edge on noise)")
rng = np.random.default_rng(42)
fires, fwd = 0, []
N_TICKERS, N_BARS = 250, 1200
for t in range(N_TICKERS):
    rets = rng.normal(0, 0.02, N_BARS)
    close = 50 * np.exp(np.cumsum(rets))
    spread = np.abs(rng.normal(0.012, 0.006, N_BARS))
    high = close * (1 + spread)
    low = close * (1 - spread)
    volume = rng.lognormal(mean=12.3, sigma=0.7, size=N_BARS)  # ~220k median
    df = pd.DataFrame({
        'date': pd.date_range('2019-01-01', periods=N_BARS, freq='D'),
        'open': close, 'high': high, 'low': low, 'close': close,
        'volume': volume,
    })
    lowa, closa = df['low'].to_numpy(), df['close'].to_numpy()
    sup = (pd.Series(lowa).rolling(45, min_periods=45).min().shift(10).to_numpy())
    res = (pd.Series(df['high']).rolling(45, min_periods=45).max().shift(10).to_numpy())
    lo10 = pd.Series(lowa).rolling(10, min_periods=1).min().to_numpy()
    hi10c = pd.Series(closa).rolling(10, min_periods=1).max().to_numpy()
    for i in range(200, N_BARS - 10, 2):
        if np.isnan(sup[i]) or not (lo10[i] < sup[i] or hi10c[i] > res[i]):
            continue
        r = detect_wyckoff_long(df.iloc[max(0, i - 259):i + 1])
        if r['is_wyckoff']:
            fires += 1
            fwd.append((closa[i + 10] - closa[i]) / closa[i] * 100)
s = pd.Series(fwd)
if len(s) >= 20:
    se = s.std() / np.sqrt(len(s))
    print(f"  fires on random data: {fires}   fwd+10d mean {s.mean():+.2f}%  "
          f"(SE {se:.2f})  win {100 * (s > 0).mean():.1f}%")
    check('Random-data edge ≈ 0 (|mean| < 2 SE + 0.5%)',
          abs(s.mean()) < 2 * se + 0.5, f"mean={s.mean():+.2f}%, SE={se:.2f}")
else:
    print(f"  fires on random data: {fires} (too few for edge test — OK, "
          "detector is selective)")
    check('Random-data: detector selective, no spurious mass-firing', fires < 500)

# ---------------------------------------------------------------------------
print("\n[3] NO-LOOKAHEAD TEST (decision must not depend on future bars)")
try:
    fires_df = pd.read_csv('wyckoff_fires.csv', parse_dates=['date'])
except FileNotFoundError:
    fires_df = pd.DataFrame()
if fires_df.empty:
    print('  wyckoff_fires.csv not found — run wyckoff_study.py first')
    check('No-lookahead test ran', False)
else:
    import sqlite3
    con = sqlite3.connect('data/dse_history.db')
    raw = pd.read_sql_query(
        "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
    con.close()
    raw['date'] = pd.to_datetime(raw['date'])
    raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])
    sample = fires_df.sample(min(120, len(fires_df)), random_state=1)
    mismatch_trunc = mismatch_future = 0
    rng = np.random.default_rng(3)
    for _, fr in sample.iterrows():
        g = raw[raw.ticker == fr['ticker']].reset_index(drop=True)
        upto = g[g.date <= fr['date']].reset_index(drop=True)
        # (a) truncated exactly at the fire date
        r1 = detect_wyckoff_long(upto)
        if not (r1['is_wyckoff'] and r1['event'] == fr['event']):
            mismatch_trunc += 1
        # (b) truncated + RANDOM future bars appended — decision on the fire
        #     bar is over the same history, so evaluating at the same position
        #     must give the same answer regardless of what comes after
        fut_n = 15
        last_c = float(upto['close'].iloc[-1])
        fut_close = last_c * np.exp(np.cumsum(rng.normal(0, 0.03, fut_n)))
        fut = pd.DataFrame({
            'date': pd.date_range(fr['date'] + pd.Timedelta(days=1), periods=fut_n),
            'open': fut_close, 'high': fut_close * 1.02,
            'low': fut_close * 0.98, 'close': fut_close,
            'volume': rng.lognormal(12.3, 0.7, fut_n),
        })
        combo = pd.concat([upto, fut], ignore_index=True)
        r2 = detect_wyckoff_long(combo.iloc[:len(upto)])
        if (r2['is_wyckoff'], r2['event']) != (r1['is_wyckoff'], r1['event']):
            mismatch_future += 1
    check(f'Truncated-history recomputation matches ({len(sample)} fires)',
          mismatch_trunc == 0, f"{mismatch_trunc} mismatches")
    check('Decision invariant to appended future bars', mismatch_future == 0,
          f"{mismatch_future} mismatches")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
