"""Validate the IMPLEMENTED breakout_signal through the real analyzer,
head-to-head vs legacy BUY/EARLY, on the same lookahead-free walk-forward."""
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import numpy as np, pandas as pd
from src.db_manager import DatabaseManager
from src.analyzer import StockAnalyzer
from src.portfolio_manager import PortfolioManager
db = DatabaseManager(); az = StockAnalyzer(db); pm = PortfolioManager()
try: pud = db.get_all_fundamentals()
except Exception: pud = {}
orig = db.get_stock_data
alld = [str(d)[:10] for d in pd.read_sql_query("SELECT DISTINCT date FROM stock_data ORDER BY date", db.engine)['date']]
maxd = alld[-1]
cache = {}
def hist(t):
    if t not in cache:
        h = orig(t).sort_values('date').reset_index(drop=True); h['d']=h['date'].astype(str).str[:10]; cache[t]=h
    return cache[t]
def realised(t, D, buy):
    h = hist(t); fut=[d for d in alld if d>D]; peak=buy; bd=pd.to_datetime(D)
    for d in fut:
        w=h[h['d']<=d]
        if w.empty or w['d'].iloc[-1]!=d: continue
        cl=float(w.iloc[-1]['close']); peak=max(peak,cl)
        w30=w.tail(30).sort_values('date',ascending=False)
        atr=pm.calculate_atr(w30,14) or 0.0; rsi=pm.calculate_rsi(w30,14) if len(w30)>=15 else 50.0
        mult=1.0 if rsi>80 else 1.5 if rsi>70 else 2.0
        prof=(cl-buy)/buy*100; days=(pd.to_datetime(d)-bd).days
        if cl<=buy*0.93: return prof
        if atr>0 and cl<=peak-mult*atr: return prof
        if days>10 and prof<2: return prof
    last=h[h['d']<=maxd].iloc[-1]; return (float(last['close'])-buy)/buy*100

dates=[d for d in alld if '2026-02-15'<=d<='2026-03-24'][::3]
rows=[]
for D in dates:
    db.get_stock_data=lambda t,start_date=None,end_date=None,_D=D: orig(t,end_date=_D)
    for t in db.get_all_tickers():
        try: r=az.analyze_ticker(t,pud.get(t))
        except Exception: continue
        if r.get('status')!='success' or r['date']!=D: continue
        rows.append(dict(D=D,t=t,buy=r['signal']=='BUY',early=r.get('early_signal')=='EARLY',
                         brk=r.get('breakout_signal'),entry=float(r['close'])))
    db.get_stock_data=orig
df=pd.DataFrame(rows)
def show(name,sub):
    if len(sub)==0: print(f"  {name:32s} (none)"); return
    rs=np.array([realised(x.t,x.D,x.entry) for x in sub.itertuples()])
    print(f"  {name:32s} n={len(sub):3d}  realised avg {rs.mean():+5.2f}%  win {(rs>0).mean()*100:3.0f}%  med {np.median(rs):+5.2f}%")
print(f"Universe success rows: {len(df)}")
show("Legacy BUY or EARLY", df[df.buy|df.early])
show("Legacy BUY only", df[df.buy])
show("Legacy EARLY only", df[df.early])
show("NEW breakout_signal", df[df.brk==True])
