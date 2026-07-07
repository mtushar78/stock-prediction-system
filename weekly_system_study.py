"""
WEEKLY TRADING SYSTEM STUDY  (data through 2026-07-06, lookahead-free, close>0)

Answers four questions the user asked after the profitability audit:
  1. FREQUENCY  — how often does the production reversal really fire (esp. 2025-26)?
  2. VALIDITY   — does the reversal edge survive non-overlapping trade counting,
                  a raw-oversold baseline, next-morning-open fills and extra slippage?
  3. FRONTIER   — can gates be relaxed to fire weekly while keeping net edge?
  4. ROTATION   — does an ALWAYS-DEPLOYED weekly mean-reversion rotation (buy the
                  worst losers every week, hold 5/10d) beat costs? vs random picks?

All returns NET of 0.8% round-trip commission where stated. No slippage beyond
the scenarios explicitly modeled. Same feature definitions as breakout_cost_audit.
"""
import sqlite3
import numpy as np
import pandas as pd

COST = 0.8
MIN_AVG_VOL20, MIN_PRICE = 50000, 5.0
ENTRY_MIN = pd.Timestamp('2019-01-01')

con = sqlite3.connect('data/dse_history.db')
raw = pd.read_sql_query(
    "SELECT ticker,date,open,high,low,close,volume FROM stock_data WHERE close>0", con)
con.close()
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])

def wilder_rsi(close, n=14):
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = pd.Series(up).ewm(alpha=1/n, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/n, adjust=False).mean().values
    rs = np.divide(ru, rd, out=np.full_like(ru, np.nan), where=rd != 0)
    return 100 - 100/(1+rs)

frames = []
for tk, g in raw.groupby('ticker', sort=False):
    g = g.reset_index(drop=True)
    n = len(g)
    if n < 141:
        continue
    close = g['close'].to_numpy(float)
    high = g['high'].to_numpy(float)
    low = g['low'].to_numpy(float)
    opn = g['open'].to_numpy(float)
    vol = g['volume'].to_numpy(float)

    avgv20 = pd.Series(vol).shift(1).rolling(20, min_periods=1).mean().to_numpy()
    rvol = np.divide(vol, avgv20, out=np.zeros_like(vol), where=avgv20 > 0)
    hi120 = pd.Series(high).rolling(120, min_periods=120).max().to_numpy()
    hi252 = pd.Series(high).rolling(252, min_periods=60).max().to_numpy()
    lo252 = pd.Series(low).rolling(252, min_periods=60).min().to_numpy()
    life_high = pd.Series(high).cummax().to_numpy()
    rsi = wilder_rsi(close)
    c5 = np.roll(close, 5).astype(float); c5[:5] = np.nan
    ret5 = np.where(c5 > 0, (close - c5) / c5 * 100, np.nan)
    prev = np.roll(close, 1); prev[0] = np.nan
    green = close > prev
    room = np.where(hi120 > 0, (close / hi120 - 1) * 100, np.nan)
    pos_1y = np.where(hi252 - lo252 > 0, (close - lo252) / (hi252 - lo252), np.nan)
    room_life = np.where(close > 0, (life_high / close - 1) * 100, np.nan)

    # forward returns from entry close
    fwd = {}
    for k in (5, 10, 20):
        ck = np.roll(close, -k).astype(float); ck[-k:] = np.nan
        fwd[k] = (ck - close) / close * 100
    # next-morning-open fill: buy open[i+1], sell close[i+10]
    o1 = np.roll(opn, -1).astype(float); o1[-1] = np.nan
    o1 = np.where(o1 > 0, o1, np.nan)
    c10 = np.roll(close, -10).astype(float); c10[-10:] = np.nan
    r10_open = (c10 - o1) / o1 * 100
    gap = (o1 - close) / close * 100

    frames.append(pd.DataFrame(dict(
        ticker=tk, date=g['date'], i=np.arange(n), close=close,
        avgv20=avgv20, rvol=rvol, rsi=rsi, ret5=ret5, green=green,
        room=room, pos_1y=pos_1y, room_life=room_life,
        r5=fwd[5], r10=fwd[10], r20=fwd[20], r10_open=r10_open, gap=gap)))

df = pd.concat(frames, ignore_index=True)
df['liquid'] = (df.avgv20 >= MIN_AVG_VOL20) & (df.close >= MIN_PRICE)
df = df[df.date >= ENTRY_MIN].copy()
df['ym'] = df.date.dt.strftime('%Y-%m')
df['yr'] = df.date.dt.year
MAXD = df.date.max()

def stat(name, s, cost=COST):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        print(f"  {name:52s} (none)"); return None
    net = s - cost
    print(f"  {name:52s} n={len(s):5d}  gross {s.mean():+5.2f}%  NET {net.mean():+5.2f}%  win {100*(net>0).mean():4.1f}%")
    return net.mean()

# ============================================================================
print("=" * 104)
print(f"SECTION 1 — PRODUCTION REVERSAL FIRE FREQUENCY (data through {MAXD.date()})")
print("=" * 104)
rev = df[df.liquid & (df.rsi < 30) & df.green & (df.rvol >= 1.5) & (df.room <= -15)].copy()
per_month = rev[rev.date >= '2024-01-01'].groupby('ym').size()
months = pd.period_range('2024-01', MAXD.strftime('%Y-%m'), freq='M').strftime('%Y-%m')
print("\nFires per month (distinct ticker-days):")
for m in months:
    cnt = int(per_month.get(m, 0))
    bar = '#' * cnt
    print(f"  {m}  {cnt:3d}  {bar}")
print(f"\nFires per year:")
for yr, s in rev.groupby('yr').size().items():
    print(f"  {yr}: {s}")
recent = rev[rev.date >= MAXD - pd.Timedelta(days=90)]
print(f"\nLast 90 days: {len(recent)} fires:")
for r in recent.itertuples():
    print(f"  {r.date.date()}  {r.ticker:14s} close {r.close:8.1f}  RSI {r.rsi:4.1f}  rvol {r.rvol:4.1f}  room {r.room:+5.1f}%")

# ============================================================================
print("\n" + "=" * 104)
print("SECTION 2 — VALIDITY: non-overlap, baselines, fills, slippage  (+10d hold unless stated)")
print("=" * 104)
# non-overlapping per ticker (>=10 trading days between accepted fires)
rev_s = rev.sort_values(['ticker', 'i'])
keep = []
last = {}
for r in rev_s.itertuples():
    if r.ticker not in last or r.i - last[r.ticker] >= 10:
        keep.append(True); last[r.ticker] = r.i
    else:
        keep.append(False)
rev_s['indep'] = keep
indep = rev_s[rev_s.indep]

print("\n[A] Overlap correction")
stat("REV all fires (as audited before)", rev['r10'])
stat("REV NON-OVERLAPPING trades only", indep['r10'])
print(f"      independent trades: {len(indep)} of {len(rev)} fires "
      f"({len(indep)/max(len(rev),1)*100:.0f}%)")

print("\n[B] Does the signal beat raw oversold-ness? (baselines, same liquidity floor)")
base_rsi = df[df.liquid & (df.rsi < 30)]
stat("BASELINE any RSI<30 day (no other gates)", base_rsi['r10'])
stat("BASELINE any RSI<30 + green day", df[df.liquid & (df.rsi < 30) & df.green]['r10'])
stat("BASELINE all liquid stock-days (universe)", df[df.liquid]['r10'])
stat("REV production (for comparison)", rev['r10'])

print("\n[C] Fill realism — you can only buy the NEXT morning")
g = rev['gap'].dropna()
print(f"  overnight gap after fire day: mean {g.mean():+.2f}%  median {g.median():+.2f}%  "
      f">+2% in {100*(g>2).mean():.0f}% of fires")
stat("REV filled at signal-day close (backtest)", rev['r10'])
stat("REV filled at NEXT-DAY OPEN (realistic)", rev['r10_open'])
stat("REV next-open + extra 0.5% slippage", rev['r10_open'], cost=COST+0.5)
stat("REV next-open + extra 1.0% slippage", rev['r10_open'], cost=COST+1.0)
stat("REV non-overlap + next-open fill", indep['r10_open'])
stat("REV non-overlap + next-open + 1.0% slip", indep['r10_open'], cost=COST+1.0)

print("\n[D] By year — non-overlapping, next-open fill, NET")
for yr, y in indep.groupby('yr'):
    s = y['r10_open'].dropna() - COST
    if len(s):
        print(f"  {yr}  n={len(s):4d}  NET {s.mean():+5.2f}%  win {100*(s>0).mean():4.1f}%")

# ============================================================================
print("\n" + "=" * 104)
print("SECTION 3 — FREQUENCY vs EDGE FRONTIER (relaxed reversal, non-overlap, next-open fill, NET)")
print("=" * 104)
years = (MAXD - ENTRY_MIN).days / 365.25
print(f"\n  {'RSI<':5s} {'rvol>=':7s} {'room<=':7s} {'n':>5s} {'fires/wk':>8s} {'NET+10d':>8s} {'win%':>5s}")
for max_rsi in (30, 35, 40):
    for min_rvol in (1.0, 1.25, 1.5):
        for min_room in (10, 15):
            cand = df[df.liquid & (df.rsi < max_rsi) & df.green
                      & (df.rvol >= min_rvol) & (df.room <= -min_room)]
            cand = cand.sort_values(['ticker', 'i'])
            keep, last = [], {}
            for r in cand.itertuples():
                if r.ticker not in last or r.i - last[r.ticker] >= 10:
                    keep.append(True); last[r.ticker] = r.i
                else:
                    keep.append(False)
            c = cand[np.array(keep, dtype=bool)] if len(cand) else cand
            s = c['r10_open'].dropna() - COST
            if len(s) == 0:
                continue
            print(f"  {max_rsi:<5d} {min_rvol:<7.2f} -{min_room:<6d} {len(s):5d} "
                  f"{len(s)/years/52:8.2f} {s.mean():+8.2f} {100*(s>0).mean():5.1f}")

# ============================================================================
print("\n" + "=" * 104)
print("SECTION 4 — ALWAYS-DEPLOYED WEEKLY ROTATION (the 'we cannot sit idle' test)")
print("=" * 104)
all_dates = np.sort(df.date.unique())
liq = df[df.liquid].set_index(['date'])

def rotation(hold, selector, label, n_pick=5, seed=None):
    """Every `hold` trading days pick n stocks at close, sell at close `hold` days on."""
    rng = np.random.default_rng(seed)
    rebs = all_dates[::hold]
    rets, yr_rets = [], {}
    col = 'r5' if hold == 5 else 'r10'
    for d in rebs:
        try:
            day = liq.loc[[pd.Timestamp(d)]]
        except KeyError:
            continue
        day = day.dropna(subset=[col])
        if len(day) == 0:
            continue
        picks = selector(day, rng, n_pick)
        if picks is None or len(picks) == 0:
            continue
        r = picks[col].mean() - COST          # full rotation: round trip each hold
        rets.append(r)
        yr = pd.Timestamp(d).year
        yr_rets.setdefault(yr, []).append(r)
    if not rets:
        print(f"  {label:52s} (none)"); return
    rets = np.array(rets)
    eq = np.prod(1 + rets/100)
    ann = eq ** (1/years) - 1
    # max drawdown of the compounded curve
    curve = np.cumprod(1 + rets/100)
    dd = (curve / np.maximum.accumulate(curve) - 1).min() * 100
    print(f"  {label:52s} n={len(rets):4d} rebs  NET/hold {rets.mean():+5.2f}%  "
          f"win {100*(rets>0).mean():4.1f}%  eq x{eq:5.2f}  ann {ann*100:+6.1f}%  maxDD {dd:5.1f}%")
    yline = "     "
    for yr in sorted(yr_rets):
        m = np.mean(yr_rets[yr])
        yline += f"{yr}:{m:+.1f}%  "
    print(yline)

sel_worst5 = lambda day, rng, n: day.nsmallest(n, 'ret5')
sel_lowrsi = lambda day, rng, n: day.nsmallest(n, 'rsi')
sel_worst_rsi40 = lambda day, rng, n: day[day.rsi < 40].nsmallest(n, 'ret5')
sel_worst_green = lambda day, rng, n: day[(day.rsi < 40) & day.green].nsmallest(n, 'ret5')
sel_random = lambda day, rng, n: day.sample(min(n, len(day)), random_state=int(rng.integers(1e9)))
sel_universe = lambda day, rng, n: day

print("\n[5-trading-day hold, rotate every week, 5 picks, NET of 0.8% per rotation]")
rotation(5, sel_worst5,      "ROT worst 5d losers")
rotation(5, sel_lowrsi,      "ROT lowest RSI")
rotation(5, sel_worst_rsi40, "ROT worst losers among RSI<40")
rotation(5, sel_worst_green, "ROT worst losers, RSI<40 + green day")
rotation(5, sel_random,      "ROT RANDOM 5 picks (baseline)", seed=42)
rotation(5, sel_universe,    "ROT entire liquid universe (baseline)")

print("\n[10-trading-day hold, rotate every 2 weeks, 5 picks, NET of 0.8% per rotation]")
rotation(10, sel_worst5,      "ROT worst 5d losers")
rotation(10, sel_lowrsi,      "ROT lowest RSI")
rotation(10, sel_worst_rsi40, "ROT worst losers among RSI<40")
rotation(10, sel_worst_green, "ROT worst losers, RSI<40 + green day")
rotation(10, sel_random,      "ROT RANDOM 5 picks (baseline)", seed=42)

print("\nDone.")
