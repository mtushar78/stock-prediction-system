"""
Within the breakout list, what separates winners from losers? Build a per-stock
quality grade. For every breakout entry (14 yrs) compute candidate quality
features + the forward 10-day return, then measure each feature's rank-IC and
win-rate-by-tercile, and test a composite score. Read-only, local data.
"""
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager
db = DatabaseManager()

def atr_w(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

per_ticker = {}
breadth_rows = []
for t in db.get_all_tickers():
    df = db.get_stock_data(t)
    if len(df) < 260: continue
    df = df[df['close'] > 0].sort_values('date').reset_index(drop=True)
    if len(df) < 260: continue
    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    sma50 = c.rolling(50).mean(); sma200 = c.rolling(200).mean()
    av20 = v.rolling(20).mean(); hi20 = h.rolling(20).max(); ret20 = c.pct_change(20) * 100
    range10 = (c.rolling(10).max() - c.rolling(10).min()) / c.rolling(10).mean() * 100
    atr = atr_w(h, l, c)
    liquid = (av20 >= 50000) & (c >= 5)
    is_brk = ((c / hi20 - 1) * 100 > -1) & (ret20 < 12) & (v / av20 > 1.5) & (c > sma200) & liquid
    prev_brk = is_brk.shift(1, fill_value=False)
    f = pd.DataFrame({
        'd': df['date'].astype(str).str[:10],
        'rvol': v / av20,
        'ret20': ret20,
        'dist_hi': (c / hi20 - 1) * 100,
        'fresh': (is_brk & ~prev_brk).astype(int),
        'dist_sma200': (c / sma200 - 1) * 100,
        'dist_sma50': (c / sma50 - 1) * 100,
        'base_tight': range10,
        'atr_pct': atr / c * 100,
        'fwd10': c.shift(-10) / c * 100 - 100,
        'is_brk': is_brk.fillna(False),
        'idx_ok': np.arange(len(df)) + 10 < len(df),
    })
    per_ticker[t] = f
    bf = pd.DataFrame({'d': f['d'], 'above': (c > sma50).astype(float), 'liquid': liquid.astype(int)})
    breadth_rows.append(bf[bf['liquid'] == 1][['d', 'above']])

breadth = pd.concat(breadth_rows, ignore_index=True).groupby('d')['above'].mean()
pool = pd.concat([f[f['is_brk'] & f['idx_ok']] for f in per_ticker.values()], ignore_index=True)
pool['breadth'] = pool['d'].map(breadth) * 100
pool = pool.dropna(subset=['fwd10'])
print(f"Breakout entries pooled: {len(pool)}  |  base win rate (fwd10>0): {(pool['fwd10']>0).mean()*100:.0f}%  avg {pool['fwd10'].mean():+.2f}%")

feats = ['rvol', 'ret20', 'dist_hi', 'fresh', 'dist_sma200', 'dist_sma50', 'base_tight', 'atr_pct', 'breadth']
print("\n" + "=" * 92)
print("Per-feature: rank-IC vs fwd10, and win% by tercile (low / mid / high feature value)")
print("=" * 92)
ic = {}
for col in feats:
    s = pool[[col, 'fwd10']].dropna()
    rc = s[col].rank().corr(s['fwd10'].rank())
    ic[col] = rc
    try:
        s = s.copy(); s['t'] = pd.qcut(s[col], 3, labels=['lo', 'mid', 'hi'], duplicates='drop')
        wr = s.groupby('t', observed=True).apply(lambda g: (g['fwd10'] > 0).mean() * 100)
        wrs = "  ".join(f"{k}:{v:3.0f}%" for k, v in wr.items())
    except Exception:
        wrs = "(n/a)"
    print(f"{col:12s} IC {rc:+.3f}   win% {wrs}")

# composite: features with |IC|>=0.03, signed; standardize and sum
strong = {k: v for k, v in ic.items() if abs(v) >= 0.03}
print(f"\nUsing predictive features (|IC|>=0.03): {[(k, round(v,3)) for k,v in strong.items()]}")
z = pool.copy()
score = pd.Series(0.0, index=z.index)
for k, v in strong.items():
    col = (z[k] - z[k].mean()) / (z[k].std() or 1)
    score += np.sign(v) * col
z['quality'] = score
z2 = z.dropna(subset=['quality', 'fwd10'])
z2 = z2.assign(q=pd.qcut(z2['quality'], 4, labels=['D', 'C', 'B', 'A'], duplicates='drop'))
print("\n" + "=" * 92)
print("COMPOSITE QUALITY GRADE — win% and avg fwd10 by quartile (A=best)")
print("=" * 92)
g = z2.groupby('q', observed=True).agg(n=('fwd10', 'size'),
        win=('fwd10', lambda s: (s > 0).mean() * 100), avg=('fwd10', 'mean'))
for q, r in g.iterrows():
    print(f"  Grade {q}: n={int(r['n']):4d}  win {r['win']:3.0f}%  avg fwd10 {r['avg']:+.2f}%")
