"""
LIVE walk-forward backtest — out-of-sample validation on real prod data.

For each trading day in an entry window (default: May 2026) the production
analyzer is run lookahead-free (data wrapped to <= that day), every BUY /
EARLY / BREAKOUT signal is "bought" at that day's close, then tracked forward
to the latest date in the DB using BOTH:
  * buy & hold to latest close, and
  * the REAL portfolio exit rules (-7% stop, ATR trailing, calendar-10 zombie).

Compares the legacy signals (BUY, EARLY) against the new v9 BREAKOUT signal.

Usage:  python backtest_live.py [START] [END] [STEP]
        defaults: 2026-05-01  2026-05-31  1   (every Nth trading day = STEP)
Read-only: never writes to the DB or touches the portfolio.
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager
from src.analyzer import StockAnalyzer
from src.portfolio_manager import PortfolioManager

START = sys.argv[1] if len(sys.argv) > 1 else '2026-05-01'
END   = sys.argv[2] if len(sys.argv) > 2 else '2026-05-31'
STEP  = int(sys.argv[3]) if len(sys.argv) > 3 else 1

db = DatabaseManager(); az = StockAnalyzer(db); pm = PortfolioManager()
try: pud = db.get_all_fundamentals()
except Exception: pud = {}
orig = db.get_stock_data
alld = [str(d)[:10] for d in
        pd.read_sql_query("SELECT DISTINCT date FROM stock_data ORDER BY date", db.engine)['date']]
maxd = alld[-1]
entry_dates = [d for d in alld if START <= d <= END][::STEP]
print(f"DB spans {alld[0]} .. {maxd}.  Entry window {START}..{END} -> {len(entry_dates)} dates (step {STEP}).")
print(f"Forward-tracking every signal to latest close {maxd}.\nEntry dates: {entry_dates}\n")

cache = {}
def hist(t):
    if t not in cache:
        h = orig(t)
        # DSE records NON-TRADING days as close=0/volume=0 (is_final=1).
        # Those are not real prices — drop them so forward tracking never
        # sees a phantom crash-to-zero (which would fire false -100% stops).
        h = h[h['close'] > 0].sort_values('date').reset_index(drop=True)
        h['d'] = h['date'].astype(str).str[:10]; cache[t] = h
    return cache[t]

def track(t, D, buy):
    """Return (bh_ret_to_latest, realised_ret, exit_reason, exit_date)."""
    h = hist(t); fut = [d for d in alld if d > D]
    if not fut: return None
    peak = buy; bd = pd.to_datetime(D); realised = None; reason = 'OPEN'; xdate = maxd
    for d in fut:
        w = h[h['d'] <= d]
        if w.empty or w['d'].iloc[-1] != d: continue
        cl = float(w.iloc[-1]['close']); peak = max(peak, cl)
        w30 = w.tail(30).sort_values('date', ascending=False)
        atr = pm.calculate_atr(w30, 14) or 0.0
        rsi = pm.calculate_rsi(w30, 14) if len(w30) >= 15 else 50.0
        mult = 1.0 if rsi > 80 else 1.5 if rsi > 70 else 2.0
        prof = (cl - buy) / buy * 100; days = (pd.to_datetime(d) - bd).days
        if realised is None:
            if cl <= buy * 0.93: realised, reason, xdate = prof, 'STOP_LOSS', d
            elif atr > 0 and cl <= peak - mult * atr: realised, reason, xdate = prof, ('TAKE_PROFIT' if prof > 0 else 'TREND_EXIT'), d
            elif days > 10 and prof < 2: realised, reason, xdate = prof, 'ZOMBIE', d
    last = h[h['d'] <= maxd].iloc[-1]; bh = (float(last['close']) - buy) / buy * 100
    if realised is None: realised, reason, xdate = bh, 'STILL_OPEN', maxd
    return bh, realised, reason, xdate

tickers = db.get_all_tickers()
sig = []
uni_bh = []
for D in entry_dates:
    db.get_stock_data = lambda t, start_date=None, end_date=None, _D=D: orig(t, end_date=_D)
    nb = ne = nk = 0
    for t in tickers:
        try: r = az.analyze_ticker(t, pud.get(t))
        except Exception: continue
        if r.get('status') != 'success' or r['date'] != D: continue
        tr = track(t, D, float(r['close']))
        if tr is None: continue
        bh, real, reason, xdate = tr
        uni_bh.append(bh)
        is_b = r['signal'] == 'BUY'; is_e = r.get('early_signal') == 'EARLY'; is_k = bool(r.get('breakout_signal'))
        if is_b or is_e or is_k:
            sig.append(dict(D=D, t=t, buy=is_b, early=is_e, brk=is_k, score=r['score'],
                            early_score=r.get('early_score'), entry=float(r['close']),
                            bh=bh, realised=real, reason=reason, xdate=xdate))
            nb += is_b; ne += is_e; nk += is_k
    db.get_stock_data = orig
    print(f"  {D}: BUY={nb}  EARLY={ne}  BREAKOUT={nk}")

df = pd.DataFrame(sig)
print(f"\nUniverse buy&hold-to-{maxd}: avg {np.mean(uni_bh):+.2f}%  win {(np.array(uni_bh)>0).mean()*100:.0f}%  (n={len(uni_bh)})")
if df.empty:
    print("No signals."); sys.exit()

def summ(name, sub):
    if len(sub) == 0: print(f"  {name:26s} (none)"); return
    bh = sub['bh']; rl = sub['realised']
    print(f"  {name:26s} n={len(sub):3d} | buy&hold avg {bh.mean():+6.2f}% win {(bh>0).mean()*100:3.0f}% "
          f"| realised avg {rl.mean():+6.2f}% win {(rl>0).mean()*100:3.0f}% med {rl.median():+6.2f}%")

print("\n" + "="*104)
print(f"COHORT PERFORMANCE  (entries {START}..{END}, tracked to {maxd})")
print("="*104)
summ("Legacy BUY (score>=50)", df[df.buy])
summ("Legacy EARLY", df[df.early])
summ("Legacy BUY or EARLY", df[df.buy | df.early])
summ("NEW BREAKOUT (v9)", df[df.brk])
summ("BREAKOUT & not legacy", df[df.brk & ~(df.buy | df.early)])

print("\n--- BREAKOUT signals detail (the proven rule) ---")
b = df[df.brk].sort_values('realised')
if len(b):
    show = b[['D','t','entry','bh','realised','reason','xdate']].copy()
    show['bh'] = show['bh'].round(1); show['realised'] = show['realised'].round(1)
    print(show.to_string(index=False))

print("\n--- a sample of legacy EARLY signals detail ---")
e = df[df.early].sort_values('realised')
show = e[['D','t','score','early_score','entry','bh','realised','reason','xdate']].head(40).copy()
show['bh'] = show['bh'].round(1); show['realised'] = show['realised'].round(1)
print(show.to_string(index=False))
