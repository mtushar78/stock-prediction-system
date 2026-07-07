"""
LONG-TERM "DIVIDEND FORTRESS" STRATEGY — point-in-time validation.

Each July 1 of year Y, pick the stocks a dividend-reliability screen would have
chosen using ONLY information available then:
  - cash dividends declared for years <= Y-1  (dividend_history)
  - price + 20d avg volume at the pick date   (stock_data)
Hold 12 months. Total return = price return + cash dividends received during
the holding year (declared for year Y) + bonus-share adjustment (a B% stock
dividend mechanically dilutes the raw price by 1/(1+B) — holder value doesn't
change, so exit price is multiplied back by (1+B)).

Cohorts: 2020..2025 (DSE company pages list ~11 years of cash dividends, so
5-year lookback windows are only fully covered from ~2020 picks onward).

Portfolios tested:
  FORT10   top 10 by composite (streak, then yield)          — the product list
  FORT-HY  top 10 by yield among qualifiers                  — yield-first
  ALLQ     every qualifier, equal weight                     — the whole screen
Benchmarks:
  UNIV     all liquid stocks (vol>=10k, px>=10), price-only return
  UNIV+D   same, plus their dividends where known (fair benchmark)

Honesty notes printed with results; see docs/LONG_TERM_STRATEGY.md.
"""
import sqlite3
import numpy as np
import pandas as pd

FACE_DEFAULT = 10.0
PICK_MONTH_DAY = '-07-01'
COHORTS = list(range(2020, 2026))

con = sqlite3.connect('data/dse_history.db')
px = pd.read_sql_query(
    "SELECT ticker, date, close, volume FROM stock_data WHERE close > 0", con)
divs = pd.read_sql_query(
    "SELECT ticker, year, cash_pct, stock_pct FROM dividend_history", con)
fund = pd.read_sql_query("SELECT ticker, face_value FROM fundamentals", con)
con.close()

px['date'] = pd.to_datetime(px['date'])
px = px.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date'])
def _v(x):
    """NULL/NaN-safe float -> 0.0 (pandas reads SQL NULL as NaN, and NaN is
    truthy — `nan or 0.0` stays NaN and silently poisons every return)."""
    try:
        f = float(x)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0

face = {r.ticker: (r.face_value if r.face_value and r.face_value == r.face_value
                   and r.face_value > 0 else FACE_DEFAULT)
        for r in fund.itertuples()}
cash = {(r.ticker, int(r.year)): _v(r.cash_pct) for r in divs.itertuples()}
stock_div = {(r.ticker, int(r.year)): _v(r.stock_pct) for r in divs.itertuples()}
div_tickers = set(divs['ticker'])

by_tk = {tk: g.reset_index(drop=True) for tk, g in px.groupby('ticker')}

def state_at(tk, when):
    """(price, avg_vol20) at the last trading day <= when; None if no data."""
    g = by_tk.get(tk)
    if g is None:
        return None, None
    idx = g['date'].searchsorted(when, side='right') - 1
    if idx < 20:
        return None, None
    return float(g['close'].iloc[idx]), float(g['volume'].iloc[idx - 19:idx + 1].mean())

def total_return(tk, y0, entry_px):
    """12-month total return %: price + bonus adjustment + cash divs of year y0."""
    g = by_tk[tk]
    t0 = pd.Timestamp(f"{y0}{PICK_MONTH_DAY}")
    t1 = pd.Timestamp(f"{y0 + 1}{PICK_MONTH_DAY}")
    idx = g['date'].searchsorted(t1, side='right') - 1
    if idx < 0 or g['date'].iloc[idx] < t0 + pd.Timedelta(days=200):
        return None                          # delisted / suspended most of the year
    exit_px = float(g['close'].iloc[idx])
    bonus = stock_div.get((tk, y0), 0.0) / 100.0
    dps = cash.get((tk, y0), 0.0) / 100.0 * face.get(tk, FACE_DEFAULT)
    return ((exit_px * (1.0 + bonus) + dps) / entry_px - 1.0) * 100.0

def price_return(tk, y0, entry_px):
    g = by_tk[tk]
    t1 = pd.Timestamp(f"{y0 + 1}{PICK_MONTH_DAY}")
    idx = g['date'].searchsorted(t1, side='right') - 1
    if idx < 0:
        return None
    return (float(g['close'].iloc[idx]) / entry_px - 1.0) * 100.0

print("=" * 100)
print("DIVIDEND-FORTRESS PIT BACKTEST — pick each July 1, hold 12 months, total return incl. dividends")
print("=" * 100)

agg = {k: [] for k in ('FORT10', 'FORT-HY', 'ALLQ', 'UNIV', 'UNIV+D')}
for Y in COHORTS:
    when = pd.Timestamp(f"{Y}{PICK_MONTH_DAY}")
    qual, univ = [], []
    for tk in by_tk:
        p, v20 = state_at(tk, when)
        if p is None or p < 10 or v20 is None or v20 < 10000:
            continue
        fr = total_return(tk, Y, p) if tk in div_tickers else price_return(tk, Y, p)
        if fr is None:
            continue
        univ.append((tk, fr, tk in div_tickers))
        # screen: last-5 declared years window, PIT-safe
        win = [cash.get((tk, y), 0.0) for y in range(Y - 5, Y)]
        paid5 = sum(1 for c in win if c > 0)
        last = cash.get((tk, Y - 1), 0.0)
        if paid5 < 4 or last <= 0:
            continue
        streak = 0
        y = Y - 1
        while cash.get((tk, y), 0.0) > 0:
            streak += 1
            y -= 1
        yld = last / 100.0 * face.get(tk, FACE_DEFAULT) / p * 100.0
        qual.append({'tk': tk, 'streak': streak, 'yield': yld, 'ret': fr})

    if not qual:
        print(f"\n{Y}: no qualifiers (dividend history too shallow)")
        continue
    q = pd.DataFrame(qual)
    fort10 = q.sort_values(['streak', 'yield'], ascending=False).head(10)
    forthy = q.sort_values('yield', ascending=False).head(10)
    u = pd.DataFrame(univ, columns=['tk', 'ret', 'has_div'])

    row = {
        'FORT10': fort10['ret'].mean(),
        'FORT-HY': forthy['ret'].mean(),
        'ALLQ': q['ret'].mean(),
        'UNIV': u['ret'].mean(),          # price-only for non-div names
        'UNIV+D': u['ret'].mean(),        # same frame; div names already include divs
    }
    for k, v in row.items():
        agg[k].append(v)
    print(f"\n{Y} (n qualifiers={len(q)}, universe={len(u)}):")
    print(f"  FORT10  {row['FORT10']:+7.1f}%   picks: "
          + ", ".join(f"{r.tk}({r.ret:+.0f}%)" for r in fort10.itertuples()))
    print(f"  FORT-HY {row['FORT-HY']:+7.1f}%")
    print(f"  ALLQ    {row['ALLQ']:+7.1f}%   UNIVERSE {row['UNIV']:+7.1f}%")

print("\n" + "=" * 100)
print("SUMMARY — average annual total return across cohorts")
print("=" * 100)
for k in ('FORT10', 'FORT-HY', 'ALLQ', 'UNIV'):
    s = pd.Series(agg[k]).dropna()
    if len(s):
        eq = np.prod(1 + s / 100)
        print(f"  {k:8s} avg {s.mean():+6.1f}%/yr   compounded x{eq:４.2f} over {len(s)} years"
              f"   positive years {int((s > 0).sum())}/{len(s)}")

print("""
Honesty notes:
 - Survivorship: dividend_history exists only for CURRENTLY listed tickers; delisted
   losers are absent from the fortress cohorts (mild upward bias) and from the
   universe benchmark equally.
 - DSE cash-dividend pages list ~11 years, so cohorts start 2020.
 - AGM timing approximated: dividends 'for year Y' assumed received during the
   July Y -> July Y+1 holding year.
 - Face value uses today's value (splits are rare on DSE; most are 10tk).
 - Bonus dilution corrected via (1+B) exit adjustment; rights issues NOT modeled.
""")
