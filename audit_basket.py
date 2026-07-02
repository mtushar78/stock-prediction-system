"""
Re-score every ticker in today's CURRENT BUY list under v7 to check:
- Already-extended ones drop out of BUY
- Fresh setups get correctly flagged EARLY
- No silent false positives
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sqlalchemy import create_engine, text
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 60)

url = open('.env').read().strip().split('=',1)[1].strip()
engine = create_engine(url)

from src.analyzer import StockAnalyzer

class _DB:
    def __init__(self, eng): self.engine = eng
    def get_stock_data(self, ticker):
        with self.engine.connect() as c:
            df = pd.read_sql_query(
                text("SELECT date,open,high,low,close,volume,"
                     "COALESCE(is_final,1) AS is_final "
                     "FROM stock_data WHERE ticker=:t ORDER BY date"),
                c, params={'t': ticker})
        df['date'] = pd.to_datetime(df['date']); return df
    def get_all_tickers(self):
        with self.engine.connect() as c:
            return [r[0] for r in c.execute(text("SELECT DISTINCT ticker FROM stock_data"))]

db = _DB(engine); an = StockAnalyzer(db)

# Today's current BUY list (from running PG query earlier)
buy_list = ['PARAMOUNT','PHENIXINS','SHYAMPSUG','TILIL','NAVANACNG',
            'DACCADYE','NTLTUBES','AAMRANET','MTB','MATINSPINN','MERCINS','MAGURAPLEX']

print(f"\n{'Ticker':12} {'Close':>7} {'5d%':>6} {'Dist%':>7} {'RVOL':>5} | "
      f"{'oScore':>6} {'NewScore':>8} {'NewSig':>7} | {'eScore':>6} {'eSig':>6} | verdict")
print("-"*155)

# Reference: original v6 scores read from signals_today
with engine.connect() as c:
    orig = pd.read_sql_query(
        text("SELECT ticker, score, signal FROM signals_today WHERE ticker = ANY(:t)"),
        c, params={'t': buy_list}
    ).set_index('ticker')

for t in buy_list:
    try:
        r = an.analyze_ticker(t)
        if r.get('status') != 'success':
            print(f"{t:12} {r.get('status'):>7} {r.get('message','')[:40]}")
            continue
        old_score = int(orig.at[t,'score']) if t in orig.index else 0
        old_sig = orig.at[t,'signal'] if t in orig.index else '-'
        # 5d return — quick calc
        sub = db.get_stock_data(t)
        ret5 = ((sub['close'].iloc[-1] - sub['close'].iloc[-6])/sub['close'].iloc[-6]*100) if len(sub)>=6 else 0
        verdict = ''
        if old_sig == 'BUY' and r['signal'] != 'BUY':
            verdict = '[OK] correctly demoted (late entry)'
        elif old_sig == 'BUY' and r['signal'] == 'BUY' and r.get('is_fresh_buy'):
            verdict = '[OK] fresh BUY (still actionable)'
        elif r['early_signal'] == 'EARLY':
            verdict = '[FIRE] EARLY fired'
        elif r['signal'] == 'BUY':
            verdict = '[WARN] stale BUY'
        print(f"{t:12} {r['close']:>7.2f} {ret5:+6.1f}% {(r['close']/(r['sma_200'] or 1)-1)*100:+7.1f} {r['rvol']:5.2f} | "
              f"{old_score:>6} ({old_sig:>4}) {r['score']:>5} {r['signal']:>7} | "
              f"{r['early_score']:>6} {r['early_signal']:>6} | {verdict}")
    except Exception as e:
        print(f"{t:12} ERROR: {e}")
