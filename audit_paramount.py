"""
Deep-audit: replay analyzer day-by-day on PARAMOUNT using Neon Postgres.
For each candidate signal date we:
  1. slice raw history to rows <= that date
  2. recompute indicators
  3. score the row, and print component breakdown

This shows EXACTLY which day the BUY signal first fires and what drove it.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sqlalchemy import create_engine, text
pd.set_option('display.width', 220)
pd.set_option('display.max_columns', 60)

# --- direct PG access ---
url = open('.env').read().strip().split('=',1)[1].strip()
engine = create_engine(url)

from src.analyzer import StockAnalyzer

class _StubDB:
    def __init__(self, eng): self.engine = eng
    def get_stock_data(self, ticker):
        with self.engine.connect() as c:
            df = pd.read_sql_query(
                text("SELECT date,open,high,low,close,volume,"
                     "COALESCE(is_final,1) AS is_final "
                     "FROM stock_data WHERE ticker=:t ORDER BY date"),
                c, params={'t': ticker})
        df['date'] = pd.to_datetime(df['date'])
        return df
    def get_all_tickers(self): return []

db = _StubDB(engine)
an = StockAnalyzer(db)

TICKER = sys.argv[1] if len(sys.argv) > 1 else 'PARAMOUNT'
raw = db.get_stock_data(TICKER)
print(f"Loaded {len(raw)} rows for {TICKER}. Range: {raw['date'].min().date()} .. {raw['date'].max().date()}")

dates_to_test = [
    '2026-05-14','2026-05-17','2026-05-21','2026-05-23',
    '2026-05-24','2026-06-01','2026-06-02','2026-06-03',
    '2026-06-04','2026-06-07','2026-06-08','2026-06-09','2026-06-10',
]

print("\n" + "="*160)
print(f"{'date':12} {'close':>7} {'%chg':>6} {'vol':>10} {'rvol':>6} {'dist%':>7} "
      f"{'raw':>5} {'score':>5} {'sig':>6}  | {'eScore':>6} {'eSig':>6}  reasons")
print("="*160)

rows = []
for d in dates_to_test:
    sub = raw[raw['date'] <= pd.to_datetime(d)].copy()
    if sub.empty: continue
    ind = an.calculate_indicators(sub)
    last = ind.iloc[-1]
    if str(last['date'].date()) != d:
        print(f"{d}: skip (no row)")
        continue
    res = an.calculate_score(last, ind, paid_up_capital=None)
    sig = an.generate_signal(res['score'])
    early = an.calculate_early_score(last, ind)
    dist = (last['close']-last['sma_200'])/last['sma_200']*100 if pd.notna(last['sma_200']) and last['sma_200']>0 else 0
    pc = last['price_change_pct'] if pd.notna(last['price_change_pct']) else 0
    early_reasons = ', '.join(early['reasons'])[:70]
    main_reasons = ', '.join(res['reasons'])[:50]
    combined = f"main: {main_reasons} | early: {early_reasons}"
    print(f"{d}  {last['close']:7.2f}  {pc:+5.1f}%  {int(last['volume']):>10,}  "
          f"{last['rvol']:6.2f}  {dist:+7.2f}  {res['raw_score']:5d}  "
          f"{res['score']:5d}  {sig:>6}  | {early['score']:6d} {early['signal']:>6}  {combined[:80]}")
    rows.append({'date':d,'close':float(last['close']),'rvol':float(last['rvol']),
                 'raw':res['raw_score'],'score':res['score'],'signal':sig,
                 'early_score':early['score'],'early_signal':early['signal'],
                 'early_reasons':early['reasons'],
                 'reasons':res['reasons'],'details':res['v5_details']})

with open(f'audit_{TICKER}_breakdown.json','w') as f:
    json.dump(rows, f, indent=2, default=str)

print("\n" + "="*140)
print("PER-COMPONENT BREAKDOWN ON KEY DATES")
print("="*140)
for d in ['2026-05-21','2026-06-02','2026-06-04','2026-06-07','2026-06-08','2026-06-10']:
    sub = raw[raw['date'] <= pd.to_datetime(d)].copy()
    if sub.empty: continue
    ind = an.calculate_indicators(sub)
    last = ind.iloc[-1]
    if str(last['date'].date()) != d: continue
    res = an.calculate_score(last, ind, paid_up_capital=None)
    print(f"\n--- {d} (close={last['close']:.2f} rvol={last['rvol']:.2f} "
          f"raw={res['raw_score']} score={res['score']} signal={an.generate_signal(res['score'])}) ---")
    for k,v in res['v5_details'].items():
        if isinstance(v, dict):
            pts = v.get('points', v.get('score', 0))
        else:
            pts = 0
        print(f"   {k:30s}: {pts:+4d} pts  {v}")
