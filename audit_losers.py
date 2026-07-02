"""
Replay the analyzer AS OF each holding's buy date to see exactly what
score/signal drove the purchase, plus v8 entry-guidance quality at the
price paid. Answers: "why are these in loss — was the signal sound or
did we chase / enter late?"
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from sqlalchemy import create_engine, text
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 60)

url = open('.env').read().strip().split('=', 1)[1].strip()
engine = create_engine(url)
from src.analyzer import StockAnalyzer, compute_entry_guidance

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
    def get_all_tickers(self): return []

db = _DB(engine); an = StockAnalyzer(db)

# ticker -> (buy_date, avg_cost_paid)
holdings = {
    'ACIFORMULA': ('2026-06-11', 144.70),
    'NTLTUBES':   ('2026-06-14', 69.50),
    'RENATA':     ('2026-06-14', 442.90),
    # winners for contrast
    'SEMLIBBLSF': ('2026-06-15', 6.20),
    'ENVOYTEX':   ('2026-06-15', 51.70),
}

for t, (buy_date, paid) in holdings.items():
    raw = db.get_stock_data(t)
    bd = pd.to_datetime(buy_date)
    sub = raw[raw['date'] <= bd].copy()
    print("\n" + "=" * 110)
    if sub.empty:
        print(f"{t}: no data <= {buy_date}"); continue
    ind = an.calculate_indicators(sub)
    last = ind.iloc[-1]
    asof = str(last['date'].date())
    res = an.calculate_score(last, ind, paid_up_capital=None)
    sig = an.generate_signal(res['score'])
    early = an.calculate_early_score(last, ind)
    sma = last.get('sma_200')
    dist = (last['close'] - sma) / sma * 100 if pd.notna(sma) and sma > 0 else 0
    le = res['v5_details'].get('late_entry', {})
    coil = res['v5_details'].get('pre_breakout_coil', {})

    # entry guidance at the price actually paid
    eg = compute_entry_guidance(last['close'], last['low'], last['high'],
                                sub.iloc[-2]['close'] if len(sub) >= 2 else None)

    print(f"{t}  bought {buy_date} @ {paid}   (data as-of {asof}, close={last['close']:.2f})")
    print(f"  MAIN score={res['score']:>3} ({sig})   raw={res['raw_score']}   "
          f"EARLY score={early['score']:>3} ({early['signal']})")
    print(f"  rvol={last['rvol']:.2f}  5d_ret={le.get('return_5d_pct')}%  "
          f"dist_SMA200={dist:+.1f}%  late_entry_pts={le.get('score')} {le.get('flags')}")
    print(f"  coil: {coil.get('score')}pts range={coil.get('range_pct')}% contracting={coil.get('atr_contracting')}")
    print(f"  ENTRY-GUIDANCE at buy bar: quality={eg['entry_quality']} "
          f"range_pos={eg['range_position']} rec_limit={eg['recommended_entry']} "
          f"day_low={eg['day_low']} day_high={eg['day_high']}")
    if eg['entry_warning']:
        print(f"    WARN: {eg['entry_warning']}")
    print(f"  main reasons : {res['reasons']}")
    print(f"  early reasons: {early['reasons']}")

    # what happened AFTER the buy (forward bars)
    after = raw[raw['date'] > bd].head(6)
    if not after.empty:
        path = "  ".join(f"{r['date'].date().isoformat()[5:]}:{r['close']:.2f}"
                         for _, r in after.iterrows())
        print(f"  forward closes: {path}")
