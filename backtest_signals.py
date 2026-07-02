"""
Walk-forward EDGE TEST of the DSE Sniper signals (lookahead-free).

For each entry date D (wrapped so the production analyzer sees only data <= D):
  - run analyze_ticker on every ticker
  - for every survival-passing ticker, record score / early_score / signals
    and the REAL forward return at +5/+10/+20 trading days and to data-end.
Then answer:
  1. Do signal stocks beat the universe average? (edge vs market regime)
  2. Does a higher score predict a higher forward return? (signal quality)
  3. What does the LIVE exit ruleset actually realise on the signals?

Touches nothing on the live site.
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np
import pandas as pd
from src.db_manager import DatabaseManager
from src.analyzer import StockAnalyzer
from src.portfolio_manager import PortfolioManager

db = DatabaseManager(); analyzer = StockAnalyzer(db); pm = PortfolioManager()
try: paid_up_data = db.get_all_fundamentals()
except Exception: paid_up_data = {}

all_dates = [str(d)[:10] for d in
             pd.read_sql_query("SELECT DISTINCT date FROM stock_data ORDER BY date", db.engine)['date']]
max_date = all_dates[-1]
orig_get = db.get_stock_data
full_cache = {}
def full_hist(t):
    if t not in full_cache:
        h = orig_get(t).sort_values('date').reset_index(drop=True)
        h['d'] = h['date'].astype(str).str[:10]
        full_cache[t] = h
    return full_cache[t]

def fwd_returns(ticker, D, entry):
    """Real forward returns at fixed trading-day horizons and to end (buy&hold)."""
    h = full_hist(ticker)
    fut = h[h['d'] > D]
    out = {}
    for k in (5, 10, 20):
        out[f'r{k}'] = ((float(fut.iloc[k-1]['close']) - entry)/entry*100
                        if len(fut) >= k else np.nan)
    out['rEnd'] = (float(fut.iloc[-1]['close']) - entry)/entry*100 if len(fut) else np.nan
    return out

# entry dates: need >=20 trading days of forward data
entry_dates = [d for d in all_dates if '2026-02-15' <= d <= '2026-03-24'][::3]
print("Entry dates:", entry_dates)
tickers = db.get_all_tickers()

recs = []
for D in entry_dates:
    def capped(ticker, start_date=None, end_date=None, _D=D):
        return orig_get(ticker, start_date=start_date, end_date=_D)
    db.get_stock_data = capped
    n_uni = n_sig = 0
    for t in tickers:
        try: r = analyzer.analyze_ticker(t, paid_up_data.get(t))
        except Exception: continue
        if r.get('status') != 'success' or r['date'] != D: continue
        n_uni += 1
        entry = float(r['close'])
        is_buy = r['signal'] == 'BUY'; is_early = r.get('early_signal') == 'EARLY'
        sig = is_buy or is_early
        if sig: n_sig += 1
        fr = fwd_returns(t, D, entry)
        recs.append(dict(D=D, ticker=t, score=r['score'], early_score=r.get('early_score', 0),
                         buy=is_buy, early=is_early, signal=sig, entry=entry, **fr))
    db.get_stock_data = orig_get
    print(f"  {D}: universe={n_uni}  signals={n_sig}")

df = pd.DataFrame(recs)
print(f"\nTotal universe rows={len(df)}  signal rows={df['signal'].sum()}")

def line(name, sub, col):
    s = sub[col].dropna()
    if len(s) == 0: return f"{name:28s} (no data)"
    win = (s > 0).mean()*100
    return f"{name:28s} n={len(s):4d}  avg {s.mean():+6.2f}%  med {s.median():+6.2f}%  win {win:3.0f}%"

print("\n" + "="*92)
print("1) SIGNAL COHORT vs UNIVERSE  — buy & hold, no exits (pure signal edge)")
print("="*92)
for col, lbl in [('r5','+5 trading days'), ('r10','+10 days'), ('r20','+20 days'), ('rEnd','to data-end')]:
    print(f"\n[{lbl}]")
    print("  " + line("Universe (all survivors)", df, col))
    print("  " + line("Signals (BUY or EARLY)", df[df['signal']], col))
    print("  " + line("  BUY only (score>=50)", df[df['buy']], col))
    print("  " + line("  EARLY only", df[df['early']], col))
    print("  " + line("Non-signal universe", df[~df['signal']], col))

print("\n" + "="*92)
print("2) DOES SCORE PREDICT RETURN?  mean +20d return by score bucket")
print("="*92)
for label, col in [('main score', 'score'), ('early_score', 'early_score')]:
    print(f"\n[{label}]")
    bins = [0,20,30,40,50,60,70,101]
    df['_b'] = pd.cut(df[col], bins, right=False)
    g = df.groupby('_b', observed=True)['r20'].agg(['mean','median','count'])
    for idx, row in g.iterrows():
        print(f"  {str(idx):12s} n={int(row['count']):4d}  mean20d {row['mean']:+6.2f}%  med {row['median']:+6.2f}%")
    # rank correlation (Spearman = Pearson on ranks; avoids scipy)
    sub = df[[col,'r20']].dropna()
    rc = sub[col].rank().corr(sub['r20'].rank())
    print(f"  Spearman corr({label}, r20) = {rc:+.3f}  (negative = higher score -> worse return)")

# ---- 3) realised P&L of LIVE exit ruleset on the signals ----
def simulate_exit(ticker, D, buy_price):
    h = full_hist(ticker); fut = [d for d in all_dates if d > D]
    highest = buy_price; buy_dt = pd.to_datetime(D)
    for d in fut:
        win = h[h['d'] <= d]
        if win.empty or win['d'].iloc[-1] != d: continue
        row = win.iloc[-1]; close = float(row['close'])
        highest = max(highest, close)
        win30 = win.tail(30).sort_values('date', ascending=False)
        atr = pm.calculate_atr(win30, 14) or 0.0
        rsi = pm.calculate_rsi(win30, 14) if len(win30) >= 15 else 50.0
        mult = 1.0 if rsi > 80 else 1.5 if rsi > 70 else 2.0
        trail = (highest - mult*atr) if atr > 0 else highest*0.95
        profit = (close-buy_price)/buy_price*100
        days = (pd.to_datetime(d)-buy_dt).days
        if close <= buy_price*0.93: return ('STOP_LOSS', profit)
        if atr > 0 and close <= trail: return ('TRAIL', profit)
        if days > 10 and profit < 2: return ('ZOMBIE', profit)
    last = h[h['d'] <= max_date].iloc[-1]
    return ('OPEN_END', (float(last['close'])-buy_price)/buy_price*100)

sig = df[df['signal']].copy()
exits = [simulate_exit(r.ticker, r.D, r.entry) for r in sig.itertuples()]
sig['reason'] = [e[0] for e in exits]; sig['realised'] = [e[1] for e in exits]
print("\n" + "="*92)
print("3) REALISED P&L under LIVE exit rules (zombie cal-10 + ATR trail + -7%)")
print("="*92)
print("  " + line("All signals (realised)", sig.rename(columns={'realised':'x'}), 'x'))
print(f"  exit mix: {dict(sig['reason'].value_counts())}")
print(f"  Mean realised per trade: {sig['realised'].mean():+.2f}%  (sum {sig['realised'].sum():+.0f}%)")
