"""Point-in-time reality check for the Stage-2 momentum watchlist.

Question this answers, honestly and lookahead-free: on DSE, does the momentum
scanner's macro STAGE (and its daily entry triggers) actually predict forward
returns — or is it, like the daily breakout in docs/PROFITABILITY_AUDIT.md,
roughly a coin-flip net of nothing?

Method (walk-forward, no lookahead):
  * Load every ticker's full daily history once.
  * At quarterly checkpoints, slice each ticker's data to ONLY what was known by
    that date and run the SAME classifier the live scanner uses (src.momentum_
    scanner._analyze_one) — so the stage/entry_status is exactly the production
    read as of that day.
  * Measure the ticker's REAL forward return over the next ~1/3/6 months from the
    checkpoint close (back-adjusted, so ex-dates aren't counted as moves).
  * Bucket forward returns by stage, by entry_status, by score decile, and
    compare Stage-2-gated breakout triggers vs. all triggers vs. the universe.

CAVEAT: fundamentals (category/EPS/PE/dividends) are only available at their
CURRENT values, so the techno_funda_pass flag here is an approximation applied
to the past. The STAGE and daily-structure reads are fully point-in-time. Treat
the funda-gated rows as indicative, the stage/structure rows as clean.

Run:  python backtest_momentum.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db_manager import DatabaseManager
from src.momentum_scanner import _analyze_one, MIN_MONTHS

# Forward horizons in trading bars (~21 bars/month).
H1, H3, H6 = 21, 63, 126
# Only test checkpoints where at least H6 future bars exist.
FIRST_CHECKPOINT = "2020-06-30"


def _load_all(engine) -> dict[str, pd.DataFrame]:
    df = pd.read_sql_query(
        text("SELECT ticker, date, open, high, low, close, volume FROM stock_data "
             "ORDER BY ticker, date"), engine)
    for col in ('open', 'high', 'low', 'close', 'volume'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close', 'high', 'low'])
    df['date'] = pd.to_datetime(df['date'])
    out = {}
    for tk, g in df.groupby('ticker'):
        g = g[g['close'] > 0].sort_values('date').reset_index(drop=True)
        if len(g) >= MIN_MONTHS * 21:      # need enough for a monthly read + forward room
            out[str(tk)] = g
    return out


def _funda_maps(engine):
    funda, divs = {}, {}
    try:
        fdf = pd.read_sql_query(text("SELECT * FROM fundamentals"), engine)
        for _, fr in fdf.iterrows():
            funda[str(fr['ticker'])] = fr.to_dict()
    except Exception:
        pass
    try:
        ddf = pd.read_sql_query(
            text("SELECT ticker, year FROM dividend_history WHERE cash_pct > 0 OR stock_pct > 0"), engine)
        for tk, g in ddf.groupby('ticker'):
            divs[str(tk)] = [int(y) for y in g['year'].tolist()]
    except Exception:
        pass
    return funda, divs


def _checkpoints(all_dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Quarter-end trading dates from FIRST_CHECKPOINT onward."""
    s = pd.Series(1, index=all_dates)
    # 'Q' quarter-end (older pandas); 'QE' only exists in pandas >=2.2.
    q = s.groupby(all_dates.to_period('Q')).tail(1)
    cps = [d for d in q.index if str(d.date()) >= FIRST_CHECKPOINT]
    # snap each quarter-end to the last actual trading day <= it
    snapped = []
    for d in cps:
        prior = all_dates[all_dates <= d]
        if len(prior):
            snapped.append(prior[-1])
    return sorted(set(snapped))


def _fwd_return(closes: np.ndarray, i: int, h: int) -> float | None:
    """% return from bar i to bar i+h (None if not enough future)."""
    if i + h >= len(closes) or closes[i] <= 0:
        return None
    return (closes[i + h] / closes[i] - 1) * 100.0


def _pct(xs):
    # xs is a pandas Series; None forward-returns land as NaN, so filter on
    # finiteness (NaN is NOT None, which is why an `is not None` check leaks it).
    a = pd.to_numeric(pd.Series(xs), errors='coerce').to_numpy(dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return (0, None, None, None)
    return (len(a), float(a.mean()), float(np.median(a)), float((a > 0).mean() * 100))


def main():
    db = DatabaseManager()
    try:
        data = _load_all(db.engine)
        funda, divs = _funda_maps(db.engine)
        all_dates = pd.DatetimeIndex(sorted({d for g in data.values() for d in g['date']}))
    finally:
        db.close()
    cps = _checkpoints(all_dates)
    print(f"Loaded {len(data)} tickers, {len(cps)} quarterly checkpoints "
          f"({cps[0].date()} … {cps[-1].date()})\n")

    # Collect one record per (ticker, checkpoint) that the classifier accepts.
    recs = []
    for tk, g in data.items():
        dates = g['date'].to_numpy()
        # back-adjusted closes for HONEST forward returns
        for cp in cps:
            pos = np.searchsorted(dates, np.datetime64(cp), side='right') - 1
            if pos < MIN_MONTHS * 21:
                continue
            sub = g.iloc[:pos + 1]
            try:
                row = _analyze_one(tk, sub, (funda.get(tk) or {}).get('sector'),
                                   funda.get(tk), divs.get(tk), int(cp.year), None)
            except Exception:
                row = None
            if not row:
                continue
            # forward returns from the adjusted close series of the FULL ticker df
            fc = g['close'].to_numpy(dtype=float)
            recs.append({
                'ticker': tk, 'cp': cp, 'pos': pos,
                'stage': row['stage'], 'entry_status': row['entry_status'],
                'ma_stack': row['ma_stack'], 'launchpad': row['launchpad'],
                'trigger': row['breakout_trigger'], 'tf': row['techno_funda_pass'],
                'score': row['score'],
                'f1': _fwd_return(fc, pos, H1),
                'f3': _fwd_return(fc, pos, H3),
                'f6': _fwd_return(fc, pos, H6),
            })
    R = pd.DataFrame(recs)
    if R.empty:
        print("No records — check data depth.")
        return
    print(f"{len(R)} (ticker, checkpoint) observations.\n")

    def block(title, groups):
        print(f"== {title} ==")
        print(f"{'bucket':22s} {'n':>6s} {'f1 mean':>9s} {'f1 win%':>8s} "
              f"{'f3 mean':>9s} {'f3 win%':>8s} {'f6 mean':>9s} {'f6 win%':>8s}")
        for label, sub in groups:
            n1, m1, _, w1 = _pct(sub['f1'])
            _, m3, _, w3 = _pct(sub['f3'])
            _, m6, _, w6 = _pct(sub['f6'])
            def fmt(x): return f"{x:+.2f}" if x is not None else "   —"
            def fw(x): return f"{x:.0f}%" if x is not None else " —"
            print(f"{label:22s} {n1:6d} {fmt(m1):>9s} {fw(w1):>8s} "
                  f"{fmt(m3):>9s} {fw(w3):>8s} {fmt(m6):>9s} {fw(w6):>8s}")
        print()

    # Baseline (every observation = the universe of liquid, enough-history names).
    block("BASELINE (all observations)", [("universe", R)])

    # By macro stage.
    order = ['EARLY_STAGE_2', 'STAGE_2', 'STAGE_1', 'NEUTRAL', 'STAGE_3', 'STAGE_4']
    block("BY MONTHLY STAGE", [(s, R[R.stage == s]) for s in order if (R.stage == s).any()])

    # By daily entry status.
    block("BY DAILY ENTRY STATUS",
          [(s, R[R.entry_status == s]) for s in
           ['TRIGGER', 'LAUNCHPAD', 'PULLBACK', 'EXTENDED', 'WAITING'] if (R.entry_status == s).any()])

    # The key product question: does gating the breakout trigger on Stage-2 +
    # techno-funda beat the raw trigger and the universe?
    block("BREAKOUT TRIGGER — GATED vs RAW", [
        ("all triggers", R[R.trigger]),
        ("trigger+Stage2", R[R.trigger & R.stage.isin(['EARLY_STAGE_2', 'STAGE_2'])]),
        ("trigger+Stage2+funda", R[R.trigger & R.stage.isin(['EARLY_STAGE_2', 'STAGE_2']) & R.tf]),
        ("trigger+EARLY_S2", R[R.trigger & (R.stage == 'EARLY_STAGE_2')]),
    ])

    # Techno-funda-clean Stage-2 (the actual watchlist) vs the rest.
    wl = R[R.stage.isin(['EARLY_STAGE_2', 'STAGE_2']) & R.tf]
    block("THE WATCHLIST (Stage-2 + techno-funda clean)", [
        ("watchlist", wl),
        ("watchlist + STACKED", wl[wl.ma_stack == 'STACKED_BULL']),
        ("watchlist + launchpad", wl[wl.launchpad]),
    ])

    # Score deciles (does a higher scanner score => higher forward return?).
    R2 = R.dropna(subset=['f3']).copy()
    if len(R2) > 50:
        R2['decile'] = pd.qcut(R2['score'], 5, labels=False, duplicates='drop')
        block("BY SCORE QUINTILE (f3)", [(f"Q{int(q)+1}", R2[R2.decile == q])
                                         for q in sorted(R2['decile'].dropna().unique())])
        rho = R2[['score', 'f3']].corr(method='spearman').iloc[0, 1]
        print(f"Spearman(score, forward 3-month return) = {rho:+.3f}\n")

    print("NOTE: fundamentals are current-value (not point-in-time); stage/structure "
          "reads ARE point-in-time. Net-of-cost edge needs ~1.5% to clear DSE round-trip.")


if __name__ == "__main__":
    main()
