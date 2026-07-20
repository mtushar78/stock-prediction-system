"""Point-in-time reality check for the coil scanner (src/coil_scanner.py).

The question, honestly and lookahead-free: does the "quiet coiled spring" DNA
from docs/WINNER_ANATOMY.md actually ENRICH the odds of catching a big runner —
or does it just re-describe the whole market?

The right metric is NOT mean return (the study itself says the profile can't
pick winners) — it is enrichment of the study's own winner definition:
    P( +20% or more within the next 30 trading days | coil )
vs the same probability for the whole liquid universe. Plus the downside risk
(P of a -15% hit) so we know what the watchlist costs when it's wrong.

Method (walk-forward, no lookahead):
  * Load every ticker's full daily history once.
  * At MONTHLY checkpoints, slice each ticker to only what was known that day
    and run the SAME classifier production uses (coil_scanner._analyze_one).
  * Forward outcomes from the back-adjusted close: max close-gain within 30
    bars (win if >= +20%), min close within 30 bars (hit if <= -15%), and the
    plain 21/63-bar returns.
  * Compare: universe baseline vs COILED vs CREEPING vs IGNITING, by grade.

Run:  python backtest_coil.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db_manager import DatabaseManager
from src.coil_scanner import _analyze_one, MIN_BARS

H_WIN = 30          # the study's winner window (trading bars)
WIN_PCT = 20.0      # ...and threshold
LOSS_PCT = -15.0    # downside "hit" threshold within the same window
H1, H3 = 21, 63
FIRST_CHECKPOINT = "2023-01-31"


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
        if len(g) >= MIN_BARS + H3:
            out[str(tk)] = g
    return out


def _adj_closes(g: pd.DataFrame) -> np.ndarray:
    """Back-adjust the FULL close series once (same rule as the scanner) so
    forward returns don't count ex-date drops as losses."""
    c = g['close'].to_numpy(dtype=float)
    n = len(c)
    factor = np.ones(n)
    for i in range(1, n):
        if c[i - 1] > 0 and c[i] / c[i - 1] < 0.88:
            factor[:i] *= (c[i] / c[i - 1])
    return c * factor


def _checkpoints(all_dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(1, index=all_dates)
    m = s.groupby(all_dates.to_period('M')).tail(1)
    return sorted(d for d in m.index if str(d.date()) >= FIRST_CHECKPOINT)


def main():
    db = DatabaseManager()
    try:
        data = _load_all(db.engine)
    finally:
        db.close()
    all_dates = pd.DatetimeIndex(sorted({d for g in data.values() for d in g['date']}))
    cps = _checkpoints(all_dates)
    print(f"Loaded {len(data)} tickers, {len(cps)} monthly checkpoints "
          f"({cps[0].date()} ... {cps[-1].date()})\n")

    recs = []
    for tk, g in data.items():
        dates = g['date'].to_numpy()
        fc = _adj_closes(g)
        # liquidity/price context is checked inside the classifier per-slice
        for cp in cps:
            pos = int(np.searchsorted(dates, np.datetime64(cp), side='right') - 1)
            if pos < MIN_BARS or pos + H_WIN >= len(fc) or fc[pos] <= 0:
                continue
            sub = g.iloc[:pos + 1]
            # Universe row (baseline): every liquid-enough slice, coil or not.
            fwd = fc[pos + 1: pos + 1 + H_WIN]
            maxg = (fwd.max() / fc[pos] - 1) * 100.0
            ming = (fwd.min() / fc[pos] - 1) * 100.0
            r1 = (fc[pos + H1] / fc[pos] - 1) * 100.0 if pos + H1 < len(fc) else np.nan
            r3 = (fc[pos + H3] / fc[pos] - 1) * 100.0 if pos + H3 < len(fc) else np.nan
            try:
                row = _analyze_one(tk, sub, None, stale_cutoff=None)
            except Exception:
                row = None
            rec = {
                'ticker': tk, 'cp': cp,
                'coil': row is not None,
                'tier': row['tier'] if row else None,
                'stage': row['stage'] if row else None,
                'score': row['score'] if row else None,
                'grade': row['grade'] if row else None,
                'win': maxg >= WIN_PCT, 'loss': ming <= LOSS_PCT,
                'maxg': maxg, 'ming': ming, 'r1': r1, 'r3': r3,
            }
            if row:
                for k in ('dist_sma20_pct', 'base_range20_pct', 'contraction',
                          'pos_1y', 'ath_room_pct', 'rsi', 'rvol', 'rvol5',
                          'ret_5d', 'ret_20d', 'above_sma200', 'sma200_rising',
                          'sma20_rising', 'sma50_rising', 'price'):
                    rec[k] = row.get(k)
            recs.append(rec)
    R = pd.DataFrame(recs)
    # Per-checkpoint market breadth (% of names above their 50-day SMA) so we
    # can test regime gating offline.
    breadth = {}
    for cp in cps:
        ups = tot = 0
        for tk, g in data.items():
            dates = g['date'].to_numpy()
            pos = int(np.searchsorted(dates, np.datetime64(cp), side='right') - 1)
            if pos < 50:
                continue
            fc = g['close'].to_numpy(dtype=float)
            tot += 1
            if fc[pos] > fc[pos - 49:pos + 1].mean():
                ups += 1
        breadth[cp] = ups / tot * 100.0 if tot else np.nan
    R['breadth'] = R['cp'].map(breadth)
    R.to_csv('coil_pit_rows.csv', index=False)
    print(f"{len(R)} (ticker, month) observations; "
          f"{int(R['coil'].sum())} coil rows "
          f"({R['coil'].mean() * 100:.1f}% of the universe)\n")

    def block(title, groups):
        print(f"== {title} ==")
        print(f"{'bucket':24s} {'n':>6s} {'P(+20%/30d)':>12s} {'P(-15%/30d)':>12s} "
              f"{'avg max+':>9s} {'r21 mean':>9s} {'r63 mean':>9s}")
        for label, sub in groups:
            if len(sub) == 0:
                continue
            r1m = np.nanmean(sub['r1'].to_numpy(dtype=float))
            r3m = np.nanmean(sub['r3'].to_numpy(dtype=float))
            print(f"{label:24s} {len(sub):6d} {sub['win'].mean() * 100:11.1f}% "
                  f"{sub['loss'].mean() * 100:11.1f}% {sub['maxg'].mean():+8.1f}% "
                  f"{r1m:+8.2f}% {r3m:+8.2f}%")
        print()

    block("BASELINE vs THE COIL SCREEN", [
        ("universe (all)", R),
        ("non-coil", R[~R.coil]),
        ("coil (any stage)", R[R.coil]),
    ])
    block("BY TIER", [
        (t, R[R.tier == t]) for t in ['TIGHT', 'WIDE']
    ])
    block("BY STAGE", [
        (s, R[R.stage == s]) for s in ['COILED', 'CREEPING', 'IGNITING']
    ])
    C = R[R.coil]
    block("BY GRADE (coil rows)", [
        (g, C[C.grade == g]) for g in ['A', 'B', 'C', 'D']
    ])
    if len(C) > 50:
        rho = C[['score', 'maxg']].dropna().corr(method='spearman').iloc[0, 1]
        print(f"Spearman(score, 30d max gain) = {rho:+.3f}")
    print("\nNOTE: enrichment (win% vs baseline) is the honest metric — the study "
          "says the profile narrows the field, it cannot pick THE winner. Net "
          "edge also needs ~1.5% to clear a DSE round-trip.")


if __name__ == "__main__":
    main()
