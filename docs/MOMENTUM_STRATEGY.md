# Momentum (Stage-2) Watchlist — Strategy & Reality Check

A medium-term (3–9 month) momentum framework distilled from three DSE strategy
videos (`docs/fromVideos/*`), implemented as the **Momentum** page. It is the
top-of-funnel the system was missing: a slow, monthly-refreshed watchlist of
fundamentally clean stocks that are in an *early Stage-2 advance* on the monthly
chart, with the daily breakout as the entry trigger.

## The framework (what the videos teach)

1. **Filter the universe (techno-funda hygiene).** A-category, positive EPS,
   P/E < 30 (waived for insurers), a recent dividend, adequate market cap. Cuts
   ~400 names to a few dozen candidates.
2. **Monthly stage analysis (Stan Weinstein).** Classify the macro stage from
   the 10- and 20-month moving averages:
   - **Stage 1** — basing/accumulation (flat MAs after a decline).
   - **Early Stage 2** — a *fresh* break out of the base (the "launchpad"). ★
   - **Stage 2** — established advance (price stacked above rising MAs).
   - **Stage 3** — topping (advance stalling, MAs flattening).
   - **Stage 4** — declining (price below falling MAs).
3. **Daily execution.** Wait for a volume-backed trigger: a break of the 20-day
   high on ≥1.5× average volume, a pullback to a rising 20-day SMA, or a
   launchpad (10/20/50-day SMAs compressed into a tight cluster). Trail the
   20-day SMA; don't chase extended names (FOMO).
4. **Discipline.** Maintain 10–15 names, refresh the list **monthly**, and
   commit to it — the videos' core message is that churning (chasing whatever is
   halted today) is what bleeds retail capital.

## The reality check (point-in-time backtest)

`backtest_momentum.py` walks the classifier forward, lookahead-free, over 396
tickers and 26 quarterly checkpoints (2020–2026). Forward returns are gross;
DSE round-trip cost is ~1.5%, so an edge must clear that.

| Bucket | n | +1mo | +3mo | +6mo |
|---|---:|---:|---:|---:|
| **Baseline** (universe) | 6503 | +0.5% | +2.1% | +1.9% |
| Stage 2 | 1741 | +1.5% | +2.0% | +4.0% |
| Early Stage 2 | 31 | −0.7% | +2.0% | −0.7% |
| Stage 3 (topping) | 154 | +0.3% | **−2.3%** | **−7.1%** |
| Stage 4 (declining) | 2123 | −0.1% | +1.8% | −0.5% |
| Raw breakout trigger | 313 | +2.8% | +2.6% | +2.5% |
| **Trigger × Stage-2** | 119 | **+4.6%** | **+8.2%** | **+8.8%** |
| Trigger × Stage-2 × funda | 37 | −0.3% | −4.3% | −2.3% |
| Watchlist (Stage-2 + funda) | 624 | +1.9% | +1.1% | +1.9% |
| Watchlist + stacked daily MAs | 139 | +4.5% | +5.3% | +0.3% |

### What this means (and how the product is framed)

- **The stage label is an *avoidance* filter, not a standalone buy.** Stage-2
  membership alone ≈ buy-everything, but **Stage 3 and Stage 4 clearly
  underperform**. Use the stage as context and to stay out of topping/declining
  names, not as a reason to buy by itself.
- **The one validated edge is a daily breakout TRIGGER inside Stage-2** — roughly
  +8% over three months vs +2% for the universe and +2.6% for raw triggers. This
  is the actionable tier and it validates the videos' actual thesis (buy Stage-2
  daily breakouts, not the stage label in isolation).
- **The techno-funda gate is NOT additive** — gating triggers on fundamentals
  turned the edge *negative* in testing (small sample, and fundamentals are
  current-value not point-in-time, so treat as indicative). It is kept as
  **hygiene / capital-protection context** — the videos' own rationale — never as
  the return driver. This echoes `docs/PROFITABILITY_AUDIT.md`.
- The composite scanner score is a reasonable **ranking heuristic** but has ~0
  rank-correlation with 3-month returns; don't read it as a return forecast.

### Bottom line

Shipped as a **watchlist + monthly-lock discipline tool** (the videos' real
value), honestly labelled as structural. The **⚡ TRIGGER-in-Stage-2** rows are
highlighted as the single combination that showed a real forward edge in the
point-in-time test. Everything else is context to watch, not a promise.

Momentum wants **healthy** market breadth (the opposite of the reversal edge,
which pays in weak tape — see `weekly-system-regime-study`). The page shows the
season so you can tell whether the tape favours new momentum entries at all.

## Setup "freshness" does NOT rank setups (tested 2026-07-20)

When several ⚡ Setups fire the same day, intuition says prefer the "fresh" ones
(low RSI, small prior run) over "late/chased" ones. `backtest_setup_quality.py`
tested this point-in-time on 341 Stage-2 trigger observations (monthly
checkpoints, 2020–2026):

| Bucket | n | +1mo | +3mo (win%) |
|---|---:|---:|---:|
| ALL Stage-2 setups | 341 | +5.5% | +9.6% (48%) |
| FRESH (RSI<70 & 1-mo run<15%) | 123 | +3.1% | +10.9% (53%) |
| LATE (RSI≥70 or run≥15%) | 218 | +6.9% | +8.9% (46%) |
| …of which prior run ≥30% | 77 | **+14.3%** | **+15.4%** (69% w1) |

FRESH does not clearly beat LATE (f3 gap is noise-level, f1 is *reversed*, and
the hottest bucket — already up 30%+ in a month — was the best performer, the
classic strength-begets-strength result). **Verdict: no quality split ships.**
Every ⚡ Setup is equally buy-eligible; the only tie-breakers are position-cap,
liquidity, and whether one share fits the 10% sizing slot. The badge reads
"⚡ BUY SETUP" and says so. (Same discipline as backtest_coil.py: an intuition
only becomes product after it survives PIT.)

## Files

- `src/momentum_scanner.py` — the scanner (monthly stage + daily state + funda).
- `backtest_momentum.py` — the point-in-time reality check above.
- `backtest_setup_quality.py` — the fresh-vs-late test (no split validated).
- `/api/momentum` (`backend/main.py`) — live scan + the locked monthly watchlist.
- `frontend/app/momentum/page.tsx` — the Momentum page.
