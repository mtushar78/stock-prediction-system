"""
EXIT-POLICY STUDY (multi-regime). Hold the ENTRY fixed, vary the EXIT, measure
REALISED return per trade across 2019-2026. Answers: are the live exits
(ATR trail + calendar-10 zombie + -7%) destroying the entry's small edge?

Entry set = "fresh breakout, not extended" (rule D from feature_study), a
liquid-universe momentum entry. Exits simulated forward on real prices with a
Wilder ATR/RSI precomputed per ticker (matches portfolio_manager math).
Read-only.
"""
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager
db = DatabaseManager()

def rsi_w(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn.replace(0, np.nan))

def atr_w(h, l, c, n=14):
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

series = {}      # ticker -> dict of numpy arrays
entries = {'A_current_style': [], 'A_guarded': [], 'D_guarded': []}   # (ticker, idx, year)
for t in db.get_all_tickers():
    df = db.get_stock_data(t)
    if len(df) < 260: continue
    df = df.sort_values('date').reset_index(drop=True)
    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    atr = atr_w(h, l, c); rs = rsi_w(c)
    av20 = v.rolling(20).mean(); sma200 = c.rolling(200).mean()
    hi10 = h.rolling(10).max(); hi20 = h.rolling(20).max(); ret20 = c.pct_change(20)*100
    range10 = (c.rolling(10).max()-c.rolling(10).min())/c.rolling(10).mean()*100
    series[t] = dict(c=c.values, h=h.values, l=l.values, o=df['open'].values,
                     atr=atr.values, rsi=rs.values,
                     date=pd.to_datetime(df['date']).values)
    guards = (c > sma200) & (ret20 < 12) & (av20 >= 50000) & (c >= 5)
    # A) CURRENT-STYLE: near 10d high + tight base + volume pop  (NO guards)
    mA = ((c/hi10-1)*100 > -2) & (range10 < 6) & (v/av20).between(1.8, 3.5)
    # A+guards: the EXACT thing my code change does (guard the current engine)
    mAG = mA & guards
    # D) GUARDED BREAKOUT: 20d-high breakout + guards (different core direction)
    mD = ((c/hi20-1)*100 > -1) & (ret20 < 12) & (v/av20 > 1.5) & (c > sma200) & \
         (av20 >= 50000) & (c >= 5)
    for key, m in (('A_current_style', mA), ('A_guarded', mAG), ('D_guarded', mD)):
        for i in np.where(m.fillna(False).values)[0]:
            if i + 45 < len(c):
                entries[key].append((t, i, pd.Timestamp(df['date'].iloc[i]).year))

for k, v in entries.items():
    print(f"Entry {k}: {len(v)} signals")

def simulate(t, i, policy):
    s = series[t]; buy = s['c'][i]; peak = buy
    n = len(s['c'])
    for step in range(1, 46):                      # up to 45 trading days
        j = i + step
        if j >= n: break
        close = s['c'][j]; peak = max(peak, close)
        atr = s['atr'][j] if not np.isnan(s['atr'][j]) else 0.0
        rsi = s['rsi'][j] if not np.isnan(s['rsi'][j]) else 50.0
        profit = (close-buy)/buy*100
        p = policy
        # hard stop
        if close <= buy*p['stop']: return profit, 'STOP', step
        # profit target
        if p.get('target') and profit >= p['target']: return profit, 'TARGET', step
        # trailing stop
        if p.get('trail'):
            mult = p['trail']
            if p.get('rsi_tighten'):
                mult = 1.0 if rsi > 80 else 1.5 if rsi > 70 else p['trail']
            if atr > 0 and close <= peak - mult*atr: return profit, 'TRAIL', step
        # zombie (calendar days)
        if p.get('zombie_cal'):
            days = (s['date'][j]-s['date'][i])/np.timedelta64(1,'D')
            if days > p['zombie_cal'] and profit < 2: return profit, 'ZOMBIE', step
        # time exit
        if p.get('max_hold') and step >= p['max_hold']: return profit, 'TIME', step
    j = min(i+45, n-1)
    return (s['c'][j]-buy)/buy*100, 'END', 45

POLICIES = {
 'LIVE (-7% + ATR2 trail RSI-tighten + zombie10)':
     dict(stop=0.93, trail=2.0, rsi_tighten=True, zombie_cal=10),
 'no-zombie (-7% + ATR2 trail)':
     dict(stop=0.93, trail=2.0, rsi_tighten=True),
 'looser (-8% + ATR3 trail, no zombie, no tighten)':
     dict(stop=0.92, trail=3.0),
 'time20 (-8% stop, hold 20d, no trail)':
     dict(stop=0.92, max_hold=20),
 'time40 (-8% stop, hold 40d, no trail)':
     dict(stop=0.92, max_hold=40),
 'target+stop (+12% / -8%, max 30d)':
     dict(stop=0.92, target=12, max_hold=30),
 'buy&hold 20d (no stop)':
     dict(stop=0.0, max_hold=20),
 'buy&hold 40d (no stop)':
     dict(stop=0.0, max_hold=40),
}
allyears = sorted({y for v in entries.values() for _,_,y in v if y >= 2019})

def run(signals, pol):
    rows = [(simulate(t,i,pol)[0], y) for (t,i,y) in signals]
    return pd.DataFrame(rows, columns=['ret','year'])

print("\n" + "="*112)
print("HEAD-TO-HEAD: same LIVE exits, CURRENT-STYLE entry vs GUARDED entry, realised return/trade per year")
print("="*112)
live = POLICIES['LIVE (-7% + ATR2 trail RSI-tighten + zombie10)']
print(f"{'entry':24s} {'n':>6s} {'mean':>6s} {'med':>6s} {'win%':>5s}  " + " ".join(f"{y%100:>5d}" for y in allyears))
for key in ('A_current_style', 'A_guarded', 'D_guarded'):
    r = run(entries[key], live)
    win = (r['ret']>0).mean()*100
    per = " ".join(f"{r[r.year==y]['ret'].mean():+5.1f}" if (r.year==y).sum()>=20 else "   . " for y in allyears)
    print(f"{key:24s} {len(r):6d} {r['ret'].mean():+6.2f} {r['ret'].median():+6.2f} {win:5.0f}  {per}")

print("\n" + "="*112)
print(f"EXIT-policy sweep on the GUARDED entry ({len(entries['D_guarded'])} signals)")
print("="*112)
print(f"{'policy':50s} {'mean':>6s} {'med':>6s} {'win%':>5s}  " + " ".join(f"{y%100:>5d}" for y in allyears))
for name, pol in POLICIES.items():
    r = run(entries['D_guarded'], pol)
    win = (r['ret']>0).mean()*100
    per = " ".join(f"{r[r.year==y]['ret'].mean():+5.1f}" if (r.year==y).sum()>=20 else "   . " for y in allyears)
    print(f"{name:50s} {r['ret'].mean():+6.2f} {r['ret'].median():+6.2f} {win:5.0f}  {per}")
