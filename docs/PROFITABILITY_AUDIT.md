# Profitability Audit — Breakout Signal & Chart Analyst

**Date:** 2026-07-02 · **Data:** full DSE history in `data/dse_history.db` (2012 → 2026-04-23 for backtests; prod DB through 2026-07-02 for live checks) · **Costs:** every number marked NET subtracts the real round-trip commission of **0.8%** (0.4% per side, verified against your own `purchase_history` rows).

New evidence produced for this audit (all lookahead-free, all filter `close>0`):

| Script | What it measures |
|---|---|
| `breakout_cost_audit.py` | Breakout v9 vs Reversal v10 vs modified variants, **net of costs**, 2019–2026 |
| `breakout_grade_audit.py` | Does the UI's A–D breakout grade separate winners net of costs? |
| `validate_patterns_pit.py` | Point-in-time run of the chart-pattern engine over 2023–2026: do its verdicts predict DSE forward returns? (raw rows in `pattern_pit_rows.csv`) |

---

## 1. Verdict (TL;DR)

1. **The breakout signal is not profitable enough to trade after costs.** Gross +1.13% per trade sounds fine; net it is **+0.33% per trade, 41% win rate — ৳33 on a ৳10,000 position**. Four of eight years are negative net. It is not "wrong", it is *too thin to survive commission* in a mean-reverting market.
2. **"It detects stocks near their top" is by design, and the design is the problem.** Gate #1 literally requires price within 1% of the 20-day high (`analyzer.py:1299`). Every one of your recent buys was within ~2% of the 20-day high. In DSE, that entry style has almost no edge — the WINNER_ANATOMY study already showed **93% of real big winners did NOT break a 20-day high at launch**.
3. **The chart-pattern engine is well-built but its bullish verdicts lose money on DSE.** Implementation is faithful to Bulkowski (previous 125/125 point-in-time audit, no look-ahead, zero-close rows filtered — reconfirmed). But the edge score/grade/verdict is calibrated on Bulkowski's **US bull-market statistics**. Validated point-in-time on DSE 2023–2026: **verdict "BUY SETUP" returned −2.98% gross, 25% win rate (n=40)**. Grade-A BUY SETUPs: 0 wins in 7. The bearish side (EXIT/AVOID, Dead-Cat-Bounce) has mild real validity.
4. **The system already contains the profitable strategy — the Reversal signal — and the product keeps steering you away from it.** Net of costs: **+5.13% per trade, 65.5% win (n=525)**; the deep-value subset **+6.44% net, 67.9% win**. That is ৳513–644 per ৳10,000 trade, ~15× the breakout expectancy. Your actual purchases (ACIFORMULA, RENATA, EBL, PADMAOIL) all came from the momentum-flavored list; none were reversal fires.

**Bottom line to "will it be profitable?":** as currently used — no. Traded through the Reversal list with the modifications in §6 — the measured edge is real, consistent (7 of 8 years positive net), and large enough to matter.

---

## 2. Your actual trades, measured

Current holdings (prod DB, prices = 2026-07-02 close):

| Ticker | Bought | Entry | vs 20d-high at buy | 20d run-up before buy | Now | P/L gross |
|---|---|---|---|---|---|---|
| ACIFORMULA | 06-11 | 144.7 | −0.2% | +1.7% | 152.7 | **+5.5%** (+৳400) |
| RENATA | 06-14 | 442.9 | +0.2% | +8.1% | 456.3 | **+3.0%** (+৳268) |
| EBL | 06-18 | 25.0 | −2.0% | +7.3% | 24.7 | **−1.2%** (−৳30) |
| PADMAOIL | 06-23 | 186.0 | −0.3% | +7.4% | 197.1 | **+6.0%** (+৳555) |

- Every entry was at or within ~2% of the 20-day high — you were structurally buying local tops because that is what the signal requires. The ~৳77 combined loss you saw on the two breakout-list buys (EBL + PADMAOIL around late June, net of fees) is exactly the expected experience of a +0.33%-net-edge signal: outcomes are dominated by noise, and commission eats the mean.
- Attribution detail: EBL was actually an **EARLY** signal (06-17) — the legacy engine with *proven negative edge* — which the UI still surfaces and top-sorts (see §6-M2). PADMAOIL's breakout flag fired 06-29, *after* you bought.
- The most expensive event isn't in the table: **SHYAMPSUG**, bought 06-08 at 195.1, no longer in the portfolio, is at **272.6 (+39.7%)**. It dipped to 162.9 (−16%) first — if the −7% stop took you out, that stop turned the biggest winner of the season into a loss. There is no sell history table, so this is unverifiable — which is itself a finding (§6-M6).

---

## 3. Breakout signal — deep analysis

### 3.1 The entry criteria guarantee "buying near the top"

`src/analyzer.py:1286–1371`, five gates, all required: within 1% of the 20-day high · above 200-SMA · 20-day return < 12% · RVOL ≥ 1.5× · liquidity floor. The 12% extension cap and 200-SMA gate genuinely help (see `exit_study.py`: the unguarded style is much worse). But the core premise — momentum continuation after a local high — is the one style DSE does not reward.

### 3.2 The numbers, net of real costs (2019 → 2026-04, `breakout_cost_audit.py`)

+10 trading-day hold, 2,734–2,769 firings:

| Variant | Gross | Gross win | **NET** | NET win | ৳ per 10k trade |
|---|---|---|---|---|---|
| Breakout (production) | +1.13% | 46% | **+0.33%** | 41% | **+33** |
| Breakout, only when market breadth ≥ 55% | +1.67% | 52% | **+0.87%** | 48% | +87 |
| Breakout + tight base/low ATR filter | −0.08% | 44% | **−0.88%** | 31% | −88 |
| Breakout, +5%/−3% bracket exit | +0.79% | 47% | **−0.01%** | 46% | −1 |
| Breakout under LIVE exit rules (−7%/trail/zombie) | +1.50% | 41% | **+0.70%** | 35% | +70 |
| **Reversal (production)** | **+5.93%** | **67%** | **+5.13%** | **65%** | **+513** |
| **Reversal, deep-value subset** | **+7.24%** | **70%** | **+6.44%** | **68%** | **+644** |

By year (NET, +10d): breakout is negative in 2019, 2022, 2024, 2025; reversal is positive in 7 of 8 years (only 2025, n=35, −2.9%).

Within the breakout pool, distance-to-high buckets ("just under" vs "at the high") barely differ (+0.26% vs +0.43% net) — so there is **no tweak of the proximity threshold that fixes it**. The edge is thin everywhere in that pool.

### 3.3 The A–D quality grade: directionally right, not enough

Exact replication of `breakoutGrade.ts` weights (`breakout_grade_audit.py`): Grade A nets **+0.66% (48% win)**, D nets +0.03%. The ordering works, but the *best* breakout bucket is still ~8× weaker than the *average* reversal trade. Also: the tight-base and low-ATR sub-factors, isolated, are **negative** after costs — of the four factors only market breadth carries real weight. The grade's headline ("A wins ~54%") is a gross, pre-cost number.

### 3.4 Why this is structural, not a bug

DSE is a mean-reverting, syndicate-driven market (docs/DSE_SNIPER_THEORY.md's own thesis). Three independent measurements now agree:

- Quant breakouts (this audit): ~zero net edge.
- Bulkowski bullish pattern breakouts (§4): *negative* net edge.
- WINNER_ANATOMY: 82% of real winners launched on *below-normal* volume from *inside* the range; the visible breakout day is usually the middle/end of the move, not the start.

Everything that buys strength loses to costs here; everything that buys confirmed weakness wins. The system's data has been saying this consistently — the product surface just hasn't caught up.

---

## 4. Chart Analyst audit

### 4.1 Engine implementation — sound ✅

Independently re-verified in this audit: no look-ahead (confirmation scans start at `start_idx+1`, trend checks look backward only), zero-close/non-trading rows filtered before detection (`clean_history`, `pattern_analyzer.py:119–143`), NaN-safe serialization, Bulkowski stats table matches the 2nd-edition book (spot-checked HTF, H&S top, rounding bottom; prior fixes in docs/CHART_PATTERN_AUDIT.md hold). Measured-move rules incl. the half-height double-top and wedge-extreme special cases are book-correct. This is good engineering.

### 4.2 Decision layer — fails DSE validation ❌

`validate_patterns_pit.py`: engine run point-in-time (320-bar windows, samples every 42 bars, 2023–2026, liquid names only), +20d forward returns, universe baseline −0.13% gross:

| Signal from the page | n | Gross | Win | NET |
|---|---|---|---|---|
| Bullish verdict **BUY SETUP** | 40 | **−2.98%** | 25% | **−3.78%** |
| … of which Grade A | 7 | −11.33% | 0% | −12.13% |
| Bullish verdict WATCH | 479 | +0.37% | 40% | −0.43% |
| Bearish confirmed (any) | 720 | −1.02% | 41% | −1.82% |
| Bearish verdict EXIT/AVOID | 512 | −0.73% | — | (correctly predicts underperformance) |
| DANGER (dead-cat bounce) | 43 | +0.00% | 40% | (flat ≠ bounce-and-recover; warning justified) |

Per-pattern (confirmed bullish): only `triple_bottom` (+1.68% net, n=82) and `double_bottom_ea` (+2.24% net, n=45) are positive; `pipe_bottom` (−4.41%, n=53) and `hs_bottom` (−4.05%, n=21) are badly negative. Note the two positive patterns are the most *reversal-shaped* ones — consistent with §3.4.

Caveats: BUY SETUP n=40 is small (the verdict requires fresh confirmation ≤10 bars at a sample date), and 2023–2026 skews bearish. But the burden of proof is on the signal, and nothing in this data supports showing users "BUY SETUP" on bullish pattern confirmations.

**Interpretation:** the page's *identification* is correct; its *promises* (edge score built from US avg-move/fail-rate stats, "~35% average rise") do not transfer. The bearish half of the page — EXIT/AVOID on topping patterns, DCB suppression — is directionally validated (~0.9%/20d below baseline) and worth keeping.

Also: the **confluence boost** (`backend/main.py:1092–1108`, +12 edge and WATCH→BUY SETUP upgrade when the quant breakout agrees) compounds two near-zero-edge signals into a stronger-looking one. Confluence with the *reversal* signal is the only justified version.

### 4.3 Books integration

The Bulkowski book is deeply integrated (stats, measure rules, tutorial). The Lynch book currently only surfaces as the Graham-style Quality Screen — it is **not** connected to any buy decision. §6-M8 proposes the one connection likely to pay: fundamentals as a *filter on reversal picks*, not as a separate page.

### 4.4 Frontend/UX findings (secondary)

- `QualityScreen.tsx` fetches once, never refreshes, shows no data-age timestamp — stale fundamentals presented as current.
- `ChartDetailModal` silently drops null OHLCV bars and pattern-line points on missing dates → geometry can render broken/misaligned with no warning.
- Verdict reasons hidden behind hover; confluence 🚀 doesn't say which quant signal or why.
- Target/stop lines drawn as exact prices with no variance context, over-implying precision (Bulkowski "meet target" rates are 46–90%).
- Tutorial teaches archetypes with no link to live DSE examples of each pattern.

---

## 5. What actually works (keep and amplify)

- **Reversal v10** (`analyzer.py:1373`): +5.13% NET, 65.5% win, 525 fires ≈ 70/year ≈ 1–2/week — tradeable frequency. Deep-value subset even better. This matches the live `reversal_tracker` sample (ALARABANK +31% target hit).
- **Bearish warnings**: overheated/decliner logic and pattern EXIT/AVOID verdicts — the predictable side of DSE per the decliner study (overbought + extended + climax volume). Downside is gravity; keep this loud.
- **Coil watchlist** (WINNER_ANATOMY): quiet, tight, above-200-SMA names as a *watchlist + alert*, explicitly not a buy signal.
- **Market breadth regime**: the one breakout grade factor with teeth; useful globally (position sizing / go-to-cash), not just for breakouts.

---

## 6. Required modifications (prioritized)

### P0 — stop the bleeding

- **M1. Reframe the Breakouts list as informational, not a buy list.** Either (a) demote it below Reversals with an honest label ("historically +0.3%/trade net of commission — watch, don't chase"), or (b) gate it on breadth ≥ 55% (net +0.87%) and show it only then. Show NET expectancy on the card, not gross.
- **M2. Remove or bury the legacy BUY/EARLY signals.** `/api/sniper-signals` still surfaces them and sorts the whole list by `signal_strength = max(score, early_score)` (`backend/main.py:654–670`) — a ranking dominated by a signal with **measured negative edge** (backtest_signals: −1.2%/trade, 20% win). You bought EBL off an EARLY. Sort reversals first; if legacy signals stay visible at all, label them "experimental — negative historical edge."
- **M3. Chart Analyst: kill the bullish "BUY SETUP" verdict until DSE-calibrated.** Map bullish confirmations to WATCH with a candid note ("pattern confirmed; bullish confirmations have not shown positive net edge on DSE"). Keep EXIT/AVOID and DANGER as-is. Replace the US `STATS` numbers in the edge score with DSE-measured per-pattern stats — `pattern_pit_rows.csv` is the seed; extend the sampling (STEP=10) to grow n before re-enabling any bullish buy verdict. Exception worth testing first: `triple_bottom` and `double_bottom_ea`, the only net-positive patterns.
- **M4. Make Reversal the front-and-center buy surface.** Default tab/sort = Reversals, deep-value badge prominent, and surface the +10d/+20d net expectancy and win rate on each card so position-level expectations are anchored (~৳500/10k, not ~lottery).

### P1 — improve the edge you keep

- **M5. Fix reversal exits.** The −7% stop + zombie rules were tuned for breakouts and cost the reversal ~1.3%/trade (realized +3.79% vs +5.13% simple 10-day hold); live tracker shows 2 of 5 stopped at −7% and then recovered double digits. For reversals use: time-based exit at +10 to +20 trading days (or the +25% target already in the tracker), stop at −10% or below the signal-day low, no zombie rule (reversals start slow by construction).
- **M6. Record sells.** Add a `sale_history` table (mirror of `purchase_history`) + realized P/L view. Right now sold positions vanish — you cannot audit your own trading (the SHYAMPSUG question is unanswerable). This also enables a "your trades vs the signals" report card.
- **M7. Confluence: only reversal-side.** Remove the +12 edge / verdict upgrade for breakout confluence in `backend/main.py:1092–1108`; keep (and strengthen) it when a bullish pattern coincides with a reversal fire — that combination is untested but both legs independently pass.
- **M8. Lynch layer where it can pay:** add a fundamentals overlay (EPS growth, D/E, sponsor holding from the Quality Screen) as a *badge/filter on reversal candidates* — "falling knife with sound fundamentals" is the Lynch thesis and is testable immediately against the 525-fire history.

### P2 — polish

- **M9. Recalibrate the breakout grade** if the list survives: keep breadth (40→60 pts), drop tight-base and ATR as standalone positives (measured negative), state net-of-cost stats in the tooltip.
- **M10. Frontend**: QualityScreen auto-refresh + "as of" timestamp; warn when OHLCV bars/pattern points are dropped in ChartDetailModal; verdict-reason column in PatternScope; show which quant signal drove the confluence flag; link each Tutorial pattern to live DSE examples.
- **M11. Global regime dial**: show market breadth on the dashboard header; when breadth < 45%, say so and shrink suggested position sizes — it is the strongest single conditioning variable found in any of the studies.

---

## 6.5 Implementation status (2026-07-02)

| Item | Status | Where |
|---|---|---|
| M1 Breakouts demoted to honest watchlist | ✅ Done | `SignalsTable.tsx` (Reversals now first + default; breakout copy/legend/tooltips state net-of-cost numbers), `BreakoutDetailModal.tsx` |
| M2 Legacy BUY/EARLY buried; reversal-first API sort | ✅ Done | `backend/main.py` (/api/sniper-signals ORDER BY reversal→breakout→legacy), legacy section labeled "Do NOT trade" |
| M3 Bullish "BUY SETUP" verdict killed until DSE-calibrated | ✅ Done | `src/pattern_analyzer.py` (fresh bullish confirmations → WATCH with candid reason). Bearish EXIT/AVOID + DCB kept. DSE per-pattern recalibration still pending (seed: `pattern_pit_rows.csv`) |
| M4 Reversal front-and-center with net expectancy | ✅ Done | Default list = Reversals; +5.1% net / 65% win shown on list, modal, tooltips |
| M5 Reversal exits fixed | ✅ Done | `src/reversal_tracker.py`: −10% stop / +25% target / 20-day expiry (was −7%/40d); exit plan shown in `ReversalDetailModal` |
| M6 Sell journal + realized P&L | ✅ Done | `sale_history` table (`db_manager.py`), `remove_position` journals price/commission/realized P&L (`portfolio_manager.py`), DELETE /api/trade accepts `sell_price`, new GET /api/sale-history, sell-price prompt + `RealizedPnl.tsx` card |
| M7 Confluence reversal-only | ✅ Done | `backend/main.py`: +12 edge & WATCH→BUY SETUP only for reversal confluence; breakout confluence informational (`PatternScope` shows 🚀 REV vs gray BRK) |
| M8 Lynch quality layer on reversals | ✅ Done (badge) | Graham 0–6 score badge (`Q5/6`) on reversal rows via /api/quality-screen; backtest of the quality-filtered reversal cohort still worth running |
| M9 Breakout grade recalibrated | ✅ Done | `breakoutGrade.ts`: breadth 60 pts / volume 15 pts; base+ATR informational only (measured net-negative) |
| M10 Frontend polish | ✅ Mostly | QualityScreen auto-refresh + "as of" stamp; ChartDetailModal dropped-bars warning; PatternScope verdict-reason subtext. Tutorial live-DSE examples still pending |
| M11 Breadth dial | ✅ Pre-existing | `MarketHealthMeter` already on the dashboard |

Still open: per-pattern DSE stats to replace Bulkowski's US numbers in the edge score (extend `validate_patterns_pit.py` with STEP=10 for larger n); portfolio-level exit advisor still applies the −7% stop to all positions because positions don't record which signal sourced them (add an origin field on buy); tutorial → live example links.

## 7. Wyckoff Method validation (added 2026-07-02)

The Wyckoff Method ("The Wyckoff Methodology in Depth", Villahermosa — `docs/_wyckoff.txt`) was implemented and validated as a candidate replacement for the Bulkowski framework, since its operator/accumulation model matches DSE's market structure and the WINNER_ANATOMY findings.

**Implementation** (`src/wyckoff_analyzer.py`): accumulation trading-range detection (lateral structure after a ≥12% decline), the book's three entries — Spring #3 (low-volume undercut + recovery, direct entry), Spring test (the book's explicit "volume lower than the previous two candles" no-supply rule, held above the spring low), and BUEC (SOS close above the creek + low-volume back-up) — plus the book's trade plan (stop below the spring low, cause-and-effect target = creek + range height).

**Verification — all passed** (`verify_wyckoff.py`): 7/7 synthetic textbook structures fire the correct event and anti-patterns don't; on 250 random-walk tickers the detector's forward return is statistically zero (+0.18% ± 0.06 SE — no look-ahead leak); 120 real fires recompute identically on truncated history and are invariant to appended future bars. **The implementation is faithful; the results below are properties of the market, not bugs.**

**Results on real DSE data** (`wyckoff_study.py`, 2019–2026, net of 0.8% costs, n=14,865):

| Entry | NET +10d | Win | Note |
|---|---|---|---|
| All Wyckoff entries | **−0.72%** | 38.7% | worse than the +0.11% universe baseline |
| Spring | −0.71% | 41.2% | best of the three, still negative |
| Spring test | −1.04% | 34.4% | the book's *preferred* entry is the worst |
| BUEC | −0.54% | 39.2% | |
| Book's stop/target plan | −1.46% | 30.2% | R:R ~3.1 doesn't survive the low hit rate |

No book-faithful quality cut rescues it (absorption volume, slight-reach springs, demand closes, deeper cause, breadth regime — best cell +1.13% net at 50% win, mostly a breadth effect, cherry-picked from ~15 cells). Notably the detector wins 49.6% on random noise but only ~39% on real DSE — the market actively fades these entries.

**Wyckoff context does not improve the reversal signal either** (`wyckoff_reversal_context.py`): reversal fires *inside* an accumulation range net **+3.29%** (59.8% win) vs **+5.97%** (68.1%) for reversals *outside* any range. The best reversals are free-falling capitulations, not range-bound springs — gating reversals on structure would destroy edge.

**Disposition:** Wyckoff ships as **context annotation only** — the Chart Analyst detail view now shows the detected accumulation range (support/creek/height/decline) and any spring/test/back-up event with an explicit "no net edge — context, not a buy trigger" note (`/api/chart-analysis/{ticker}` → `wyckoff` block, `ChartDetailModal`). It is deliberately NOT a signal list, NOT a grade factor, and NOT a confluence booster.

**The pattern across all three audits is now unambiguous:** quant breakouts (+0.33% net), Bulkowski bullish confirmations (−3.78% net), Wyckoff structural entries (−0.72% net) — every "buy strength/confirmation" style fails after costs on DSE, while buying deep capitulation (+5.13% net) works. The books describe markets correctly; DSE simply pays a different entry.

### 7.1 Ignition (catch-the-rise-early) validation — also no edge

`ignition_study.py` tested the WINNER_ANATOMY "catchable launch": a quiet coil (10-day range ≤10%, subdued prior volume, not extended) printing its first strong up-day on ≥2× volume — the pattern 36% of real winners showed at launch. Result: **best variant +0.11% net at +10d (41% win, n=1,978), negative in 4 of 8 years** — indistinguishable from zero across every anatomy-faithful cut (above-200-SMA, upper-half-of-range, quiet-volume, strong-trigger). The anatomy study's conclusion survives its own implementation: for every winner that ignites, dozens of identical igniters fizzle, and the difference is external news that isn't in the chart. **The earliest tradeable moment of a rise on DSE remains the reversal fire** (buying the capitulation turn — e.g. ALARABANK's fire day was the literal first day of its +31% run).

### 7.2 In-list honesty layer (shipped)

The pattern scanner rows now carry: (a) **risk tags** computed from live quant state — OVERBOUGHT / ALREADY RAN / STRETCHED / CLIMAX VOLUME / THIN — i.e. the decliner-anatomy markers, shown in red on the row so a "rising, big target" stock like ZEALBANGLA self-labels as late; and (b) **DSE reality** per bullish pattern (measured +20d net return and win rate from §4.2's validation, e.g. pipe bottom: −4.4% net, 21% win) displayed directly under the US-book target so the two are never confused.

## 8. Methodology & honesty notes

- All backtests filter `close>0` (DSE non-trading stub rows), require 20d avg volume ≥ 50k and price ≥ 5, and compute features from prior bars only. Entries 2019-01 → 2026-04.
- **Not modeled:** slippage/spread (thin DSE books make small +edges worse, strengthening the breakout conclusion), circuit-breaker/floor-price regimes (2022–23 floor period suppresses both strategies' samples), overlapping forward windows (a stock can fire repeatedly within 10 days — win rates are per-fire, not per-independent-trade).
- **Sample-size warnings:** pattern BUY SETUP n=40 (grade A n=7) — the direction is clear but the magnitude is noisy; reversal fires cluster in 2024 (n=300 of 525) — its worst year (2025, n=35) was −2.9% net, so it is not immune to regime.
- Reproduce with: `python breakout_cost_audit.py`, `python breakout_grade_audit.py`, `python validate_patterns_pit.py` (writes `pattern_pit_rows.csv`).

## 9. Chart-pattern DENSE re-validation (2026-07-07) — bullish layer is baseline-minus-costs

`validate_patterns_regime.py` (STEP=10, 2022-01 → 2026-07-06, 24,781 PIT samples, breadth-bucketed) — ~100× the bullish sample of §4:

- **Bullish confirmed (n=4,115): −0.21% gross — IDENTICAL to the universe baseline (−0.21%)** → NET −1.01%, 37% win. The bullish pattern layer adds zero information; net of costs it is a commission machine. WATCH verdicts (n=3,512): NET −1.12%.
- **Regime does NOT rescue patterns** (unlike the quant reversal): weak tape −1.84% NET, strong tape −0.42% NET — both ≈ baseline − costs.
- **§4's small-n survivors collapsed**: triple_bottom +1.68% → **+0.42% NET** (n=487, 38% win — noise-tier); double_bottom_ea +2.24% → **−0.87% NET** (n=368). Confirms the multiple-comparison caution in §8.
- **Bearish side no longer validates**: EXIT/AVOID −0.30% gross vs −0.21% baseline (≈0 edge, n=3,528); DANGER/DCB actually *outperformed* (+1.55% NET, n=213). §4's "mild bearish validity" was small-sample.
- **Why it feels like it works right now**: 2026 YTD bullish confirmed = **+2.17% NET, 52% win** (n=632) — the only positive year of five. It's the breadth-68% tape lifting everything, not the patterns: the same layer did **−4.50% NET in 2024**. Following chart patterns feels smart in a bull tape and bleeds worst right after it turns.

**Disposition:** Chart Analyst = visualization/education/context layer only. Not a buy list, not a sell list, no confluence weight. Raw rows: `pattern_pit_rows_regime.csv`.
