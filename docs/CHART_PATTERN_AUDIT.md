# Chart-Pattern Engine — Bulkowski Fidelity Audit

Two audits of `src/pattern_analyzer.py` against Thomas Bulkowski's *Encyclopedia
of Chart Patterns* (2nd ed.), plus the fixes applied.

## Audit 1 — Code vs Book (four independent reviewers)

Every detector's identification rules, `STATS` numbers, and measure rule were
cross-checked against the book text (`docs/_encyc.txt`). The engine was **mostly
faithful** — nearly all stats, confirmation rules, and measure rules already
matched. Real bugs found and **fixed**:

| # | Pattern | Bug | Fix |
|---|---------|-----|-----|
| 1 | Triple Top | measure rule used HALF height (double-top rule) | FULL height (book p.789) |
| 2 | Falling Wedge | up-target was `band_top + height` | wedge's **highest high** (p.796) |
| 3 | Rising Wedge | down-target was `band_bot − height` | wedge's **lowest low** (p.822–3) |
| 4 | Double Top E&E | throwback 62 | **59** (book) |
| 5 | Symmetrical Triangle | throwback 54 (matched neither dir) | **37** (up-breakout) |
| 6 | Pennant | dead STATS entry — never detected | added converging-consolidation detection |
| 7 | Pipe Bottom/Top | weekly stats used on daily bars | now **resamples to weekly** before detecting |
| 8 | Triangles/Wedges | height used pivot means | uses pattern **extremes** |

Also: populated Bulkowski **ranks** for every pattern; relabeled Cup & Rounding
Bottom as **continuation**; H&S-top stop moved to the neckline troughs.

Accepted simplifications (documented, not bugs): volume is treated as a
performance modifier (not an identification gate); flags model horizontal
consolidations; DCB event decline is detected on a single session.

## Audit 2 — 50 Random Point-in-Time Readings

`audit_empirical.py` picks random (ticker, as-of-date) pairs, runs the analyzer
on history up to that date, then **independently re-derives** the book's
identification rules and measure-rule target from the raw OHLCV and checks the
engine agrees.

**Result: 125/125 checks passed (100%)** across 50 readings spanning the full
catalog — including the fixed Triple-Top (full height), Double-Top (half
height), both wedge targets, and weekly pipes.

Reproduce: `python audit_empirical.py` (fixed seed 20260701).
