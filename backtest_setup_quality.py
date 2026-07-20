"""Point-in-time check: among Momentum ⚡ Setups (breakout trigger inside a
monthly Stage-2), does entry FRESHNESS separate good buys from late chases?

Motivation (2026-07-20): four Setups fired the same day; the user asked "can I
buy all of them?" The hand answer was "prefer low-RSI / small-recent-run ones"
— this script tests whether that split is real before it ships as a product
verdict (same discipline as backtest_coil.py: PIT first, then thresholds).

Method: identical walk-forward as backtest_momentum.py but MONTHLY checkpoints
(triggers are 1-2 day events; quarterly sampling catches too few), recording
each trigger row's point-in-time RSI and 1-month return, then bucketing forward
returns. Run:  python backtest_setup_quality.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.db_manager import DatabaseManager
from src.momentum_scanner import _analyze_one, MIN_MONTHS
from backtest_momentum import _load_all, _funda_maps, _fwd_return, _pct, H1, H3, H6

FIRST_CHECKPOINT = "2020-06-30"


def _monthly_checkpoints(all_dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(1, index=all_dates)
    m = s.groupby(all_dates.to_period('M')).tail(1)
    return sorted({d for d in m.index if str(d.date()) >= FIRST_CHECKPOINT})


def main():
    db = DatabaseManager()
    try:
        data = _load_all(db.engine)
        funda, divs = _funda_maps(db.engine)
        all_dates = pd.DatetimeIndex(sorted({d for g in data.values() for d in g['date']}))
    finally:
        db.close()
    cps = _monthly_checkpoints(all_dates)
    print(f"{len(data)} tickers, {len(cps)} monthly checkpoints "
          f"({cps[0].date()} .. {cps[-1].date()})")

    recs = []
    for tk, g in data.items():
        dates = g['date'].to_numpy()
        fc = g['close'].to_numpy(dtype=float)
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
            if not row or not row['breakout_trigger']:
                continue   # only trigger days matter here
            recs.append({
                'stage2': row['stage'] in ('STAGE_2', 'EARLY_STAGE_2'),
                'rsi': row['rsi'], 'ret_1m': row['ret_1m'],
                'f1': _fwd_return(fc, pos, H1),
                'f3': _fwd_return(fc, pos, H3),
                'f6': _fwd_return(fc, pos, H6),
            })
    R = pd.DataFrame(recs)
    print(f"{len(R)} trigger observations, of which Stage-2: {int(R.stage2.sum())}\n")

    S = R[R.stage2].copy()
    S['rsi'] = pd.to_numeric(S['rsi'], errors='coerce')
    S['ret_1m'] = pd.to_numeric(S['ret_1m'], errors='coerce')

    def block(title, groups):
        print(f"== {title} ==")
        print(f"{'bucket':26s} {'n':>5s} {'f1':>8s} {'w1':>5s} {'f3':>8s} {'w3':>5s} {'f6':>8s} {'w6':>5s}")
        for label, sub in groups:
            n, m1, _, w1 = _pct(sub['f1'])
            _, m3, _, w3 = _pct(sub['f3'])
            _, m6, _, w6 = _pct(sub['f6'])
            def fmt(x): return f"{x:+.2f}" if x is not None else "    -"
            def fw(x): return f"{x:.0f}%" if x is not None else "  -"
            print(f"{label:26s} {n:5d} {fmt(m1):>8s} {fw(w1):>5s} {fmt(m3):>8s} {fw(w3):>5s} {fmt(m6):>8s} {fw(w6):>5s}")
        print()

    block("SETUPS by RSI at trigger", [
        ("rsi < 60", S[S.rsi < 60]),
        ("60-70", S[(S.rsi >= 60) & (S.rsi < 70)]),
        ("70-80", S[(S.rsi >= 70) & (S.rsi < 80)]),
        ("rsi >= 80", S[S.rsi >= 80]),
    ])
    block("SETUPS by prior 1-month run", [
        ("ret_1m < 5%", S[S.ret_1m < 5]),
        ("5-15%", S[(S.ret_1m >= 5) & (S.ret_1m < 15)]),
        ("15-30%", S[(S.ret_1m >= 15) & (S.ret_1m < 30)]),
        (">= 30%", S[S.ret_1m >= 30]),
    ])
    fresh = S[(S.rsi < 70) & (S.ret_1m < 15)]
    late = S[(S.rsi >= 70) | (S.ret_1m >= 15)]
    block("THE PRODUCT SPLIT (proposed)", [
        ("ALL Stage-2 setups", S),
        ("FRESH (rsi<70 & run<15%)", fresh),
        ("LATE (rsi>=70 | run>=15%)", late),
    ])
    print("Net-of-cost bar: ~1.5% DSE round-trip. A split only ships if FRESH")
    print("clearly beats LATE on f3 with a sane sample on both sides.")


if __name__ == "__main__":
    main()
