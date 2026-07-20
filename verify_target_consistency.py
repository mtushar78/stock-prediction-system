"""Guard: THE upside target is identical for every stock across every path.

The "target says 78 in the list but 72 on the chart" class of bug comes from more
than one piece of code computing a target. This script proves the invariant that
prevents it: for ALL tickers, the ONE canonical target
(src.rebound_scanner.canonical_target) is the same value no matter which backend
path produces it —

  * canonical_target(ticker, full_history)   ← what the chart headline uses
  * targets_for(engine, [tickers])           ← what the chart-pattern list uses
  * scan()[ticker].target                    ← what the Rebounds list uses

If this passes, any remaining list-vs-chart mismatch is a FRONTEND bug (a view
showing a non-canonical number such as a Bulkowski measure-rule target or a local
swing-high estimate) — never the backend. The frontend contract: only the
canonical `rebound_target` is ever shown as "Target"; if it is null, show "—",
never a second guess.

Run:  python verify_target_consistency.py   (exit 0 = consistent, 1 = drift)
"""
from __future__ import annotations

import sys

from src.db_manager import DatabaseManager
from src.rebound_scanner import scan, canonical_target, targets_for

TOL = 0.001


def main() -> int:
    db = DatabaseManager()
    try:
        tickers = [t[0] for t in db.conn.cursor()
                   .execute("SELECT DISTINCT ticker FROM stock_data").fetchall()]

        # Path A vs B: single canonical (chart) vs bulk (pattern list).
        bulk = targets_for(db.engine, tickers)
        ab_mismatch, both_null = [], 0
        single_map = {}
        for tk in tickers:
            single = canonical_target(tk, db.get_stock_data(tk))
            single_map[tk] = single
            b = bulk.get(tk)
            if single is None and b is None:
                both_null += 1
                continue
            if (single is None) != (b is None):
                ab_mismatch.append((tk, single, b, "null-diff"))
            elif abs(single - b) > TOL:
                ab_mismatch.append((tk, single, b))

        # Path C: the Rebounds scan target must equal the canonical for each
        # stock that qualifies as a rebound (that list opens the same chart).
        res = scan(db.engine)
        c_mismatch = []
        for s in res["stocks"]:
            tk, list_tgt = s["ticker"], s.get("target")
            chart_tgt = single_map.get(tk)
            if list_tgt is None and chart_tgt is None:
                continue
            if (list_tgt is None) != (chart_tgt is None):
                c_mismatch.append((tk, list_tgt, chart_tgt, "null-diff"))
            elif abs(list_tgt - chart_tgt) > TOL:
                c_mismatch.append((tk, list_tgt, chart_tgt))
    finally:
        db.close()

    print(f"tickers checked           : {len(tickers)}")
    print(f"both-null (thin history)  : {both_null}")
    print(f"chart vs pattern-list     : {len(ab_mismatch)} mismatch(es)")
    print(f"chart vs rebounds-list    : {len(c_mismatch)} mismatch(es)")
    for m in (ab_mismatch + c_mismatch)[:40]:
        print("   DRIFT", m)

    ok = not ab_mismatch and not c_mismatch
    print("\nRESULT:", "OK - one target everywhere" if ok
          else "DRIFT - backend targets disagree")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
