"""
FEATURE-EDGE STUDY (multi-regime) — what actually predicts forward return on DSE?

Vectorized per ticker over full history, then pooled. For each (ticker, date)
in a liquid, tradable universe we compute candidate features and the REAL
forward 10/20-trading-day return (close-to-close). We then measure each
feature's rank Information Coefficient (Spearman corr with fwd return),
overall AND per calendar year, to see which signals carry a STABLE edge
rather than a one-regime fluke.

Read-only on the DB.
"""
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager

db = DatabaseManager()
tickers = db.get_all_tickers()

def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100/(1+rs)

frames = []
for t in tickers:
    df = db.get_stock_data(t)
    if len(df) < 260:
        continue
    df = df.sort_values('date').reset_index(drop=True)
    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    f = pd.DataFrame({'ticker': t, 'date': df['date'], 'close': c})
    # --- candidate features (all computed from data up to that row only) ---
    f['ret_5d']   = c.pct_change(5)*100
    f['ret_10d']  = c.pct_change(10)*100
    f['ret_20d']  = c.pct_change(20)*100
    hi20 = h.rolling(20).max(); hi10 = h.rolling(10).max()
    f['dist_hi20'] = (c/hi20 - 1)*100          # 0 = at 20d high, neg = below
    f['dist_hi10'] = (c/hi10 - 1)*100
    lo20 = l.rolling(20).min()
    f['dist_lo20'] = (c/lo20 - 1)*100          # 0 = at 20d low
    f['rsi14'] = rsi(c)
    sma50 = c.rolling(50).mean(); sma200 = c.rolling(200).mean()
    f['dist_sma50']  = (c/sma50 - 1)*100
    f['dist_sma200'] = (c/sma200 - 1)*100
    f['above_sma200'] = (c > sma200).astype(int)
    av20 = v.rolling(20).mean()
    f['rvol'] = v/av20
    # 10d close range as % (tight base) — the current EARLY ingredient
    f['range10_pct'] = (c.rolling(10).max() - c.rolling(10).min())/c.rolling(10).mean()*100
    f['avg_vol20'] = av20
    # --- forward returns (the targets) ---
    f['fwd10'] = c.shift(-10)/c*100 - 100
    f['fwd20'] = c.shift(-20)/c*100 - 100
    f['year'] = pd.to_datetime(df['date']).dt.year
    frames.append(f)

pool = pd.concat(frames, ignore_index=True)
# tradable universe: liquid + not a penny floor + valid history
pool = pool[(pool['avg_vol20'] >= 50000) & (pool['close'] >= 5) & pool['fwd20'].notna()
            & pool['dist_sma200'].notna()]
print(f"Pooled tradable observations: {len(pool):,}  (years {pool['year'].min()}-{pool['year'].max()})")

feat_cols = ['ret_5d','ret_10d','ret_20d','dist_hi20','dist_hi10','dist_lo20',
             'rsi14','dist_sma50','dist_sma200','rvol','range10_pct']

def ic(sub, col, tgt='fwd20'):
    s = sub[[col, tgt]].dropna()
    if len(s) < 100: return np.nan
    return s[col].rank().corr(s[tgt].rank())

print("\n" + "="*100)
print("RANK IC vs fwd-20d return  (positive = higher feature -> higher return).  Stability across years:")
print("="*100)
years = sorted(pool['year'].unique())
recent = [y for y in years if y >= 2018]
hdr = "feature        overall " + " ".join(f"{y%100:>4d}" for y in recent)
print(hdr)
for col in feat_cols:
    overall = ic(pool, col)
    per = [ic(pool[pool['year']==y], col) for y in recent]
    cells = " ".join((f"{x:+.2f}" if not np.isnan(x) else "  . ") for x in per)
    print(f"{col:14s} {overall:+6.2f}  {cells}")

# decile table for the most promising mean-reversion features
print("\n" + "="*100)
print("fwd-20d mean return by decile of key features (pooled)")
print("="*100)
for col in ['dist_hi20','dist_sma200','rsi14','ret_20d','dist_lo20']:
    s = pool[[col,'fwd20']].dropna().copy()
    s['dec'] = pd.qcut(s[col], 10, labels=False, duplicates='drop')
    g = s.groupby('dec')['fwd20'].agg(['mean','count'])
    line = "  ".join(f"d{int(d)}:{r['mean']:+5.1f}%" for d,r in g.iterrows())
    print(f"{col:14s} (low->high decile)  {line}")
print("\nUniverse baseline fwd20 mean: %.2f%%  median: %.2f%%" % (pool['fwd20'].mean(), pool['fwd20'].median()))

# ============================================================================
# CANDIDATE SIGNAL RULES — does any composite robustly beat the universe?
# ============================================================================
P = pool
candidates = {
 # A) proxy for the CURRENT engine: near the high + tight base + volume pop
 'A_current_proxy (near-high+tight+volpop)':
     (P['dist_hi10'] > -2) & (P['range10_pct'] < 6) & (P['rvol'].between(1.8, 3.5)),
 # B) pullback inside an uptrend (mean-reversion entry)
 'B_pullback_in_uptrend':
     (P['above_sma200'] == 1) & (P['dist_hi20'].between(-12, -4)) &
     (P['rsi14'].between(35, 55)) & (P['dist_sma200'] < 15),
 # C) quiet uptrend, not extended, mild interest
 'C_quiet_not_extended':
     (P['above_sma200'] == 1) & (P['ret_20d'] < 5) & (P['dist_sma200'] < 12) &
     (P['range10_pct'] < 8) & (P['rvol'] > 1.3),
 # D) fresh breakout that is NOT already extended
 'D_fresh_breakout':
     (P['dist_hi20'] > -1) & (P['ret_20d'] < 12) & (P['rvol'] > 1.5) &
     (P['above_sma200'] == 1),
 # E) deep value bounce: beaten down vs SMA200 but turning (RSI rising off lows)
 'E_oversold_uptrend':
     (P['above_sma200'] == 1) & (P['rsi14'].between(30, 45)) & (P['ret_5d'] > 0),
}
print("\n" + "="*100)
print("CANDIDATE RULE PERFORMANCE  (fwd-20d). Universe mean = %.2f%%" % P['fwd20'].mean())
print("="*100)
recent = [y for y in years if y >= 2019]
print(f"{'rule':42s} {'n':>6s} {'mean':>6s} {'med':>6s} {'win%':>5s}  per-year mean: " +
      " ".join(f"{y%100:>5d}" for y in recent))
for name, mask in candidates.items():
    sub = P[mask]
    if len(sub) < 50:
        print(f"{name:42s} n={len(sub)} too few"); continue
    win = (sub['fwd20'] > 0).mean()*100
    per = []
    for y in recent:
        ss = sub[sub['year']==y]['fwd20']
        per.append(f"{ss.mean():+5.1f}" if len(ss) >= 20 else "   . ")
    print(f"{name:42s} {len(sub):6d} {sub['fwd20'].mean():+6.2f} {sub['fwd20'].median():+6.2f} "
          f"{win:5.0f}  {' '.join(per)}")
print("\n(Edge = rule mean minus universe mean; want POSITIVE and consistent across years.)")
