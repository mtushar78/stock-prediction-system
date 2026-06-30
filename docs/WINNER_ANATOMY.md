# Winner & Decliner Anatomy — what really triggers big DSE moves

**Study date:** 2026-06-30 · **Data:** live production DB (Neon PG, full history through today)
**Method:** reverse-engineering. Scanned all 433 tickers for *clean drastic winners* — a stock that
rose **≥20% within ~30 trading days with a pre-peak dip no worse than −8%**, launching from a *quiet/flat*
state (not already mid-run), entry window Mar–Jun 2026. Found **212 such launches**; profiled the **top 28**
(including the user's examples: BSRMLTD, BSRMSTEEL, ZEALBANGLA, SHYAMPSUG, FEKDIL, FEDERALINS, ASIATICLAB‑class).

> ⚠️ This documents what winners *looked like at launch*. It is **descriptive, not predictive** — see
> "The hard truth" at the bottom. We use it to build a **watchlist + fast-reaction alert**, not a buy button.

---

## The 28 winners (sorted by peak gain)

| Ticker | Launch | Entry→Now | Peak | RSI | pos 1y | % below ATH | vs SMA20 | rvol (day) | rvol (+1–3d) | broke 20d-hi | base tight | price |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SONARGAON | 05-10 | 33.9→96.7 | +183% | 35 | 0.73 | 136% | −8.9% | 0.6 | 0.9 | no | 17.7 | 34 |
| MEGHNAPET | 04-09 | 27.6→80.6 | +173% | 54 | 0.87 | 88% | +1.5% | 0.5 | 2.4 | **yes** | 21.7 | 28 |
| HFL | 03-01 | 7.2→15.7 | +133% | 58 | 0.32 | 813% | +6.0% | 0.8 | 2.9 | no | 29.4 | 7 |
| APEXSPINN | 03-29 | 193→399 | +126% | 47 | 0.83 | 21% | −1.6% | 0.7 | 2.9 | no | 17.3 | 193 |
| BDAUTOCA | 03-08 | 126→216 | +100% | 40 | 0.82 | 247% | −7.2% | 0.6 | 0.4 | no | 20.2 | 126 |
| SICL | 04-19 | 21.5→38.9 | +94% | 59 | 0.81 | 151% | +4.1% | **3.5** | 3.9 | no | 7.8 | 22 |
| DAFODILCOM | 03-08 | 58→158 | +93% | 68 | 0.81 | 80% | +7.6% | 0.8 | 0.6 | no | 35.2 | 58 |
| SAIFPOWER | 05-19 | 5.9→10.9 | +90% | 36 | 0.38 | 731% | −6.6% | 0.6 | 1.5 | no | 15.8 | 6 |
| NAHEEACP | 04-19 | 22→36 | +87% | 55 | 0.79 | 363% | +2.1% | 1.1 | 3.5 | **yes** | 13.9 | 22 |
| PROVATIINS | 05-12 | 35→65 | +86% | 59 | 0.94 | 482% | +2.4% | 0.4 | 1.4 | no | 12.2 | 35 |
| DOMINAGE | 03-10 | 36→80 | +84% | 62 | 0.95 | 23% | +2.5% | 0.9 | 0.9 | no | 9.9 | 36 |
| APEXTANRY | 03-29 | 68→105 | +82% | 54 | 0.80 | 222% | +1.6% | 1.1 | 4.4 | no | 13.6 | 68 |
| BDTHAI | 05-13 | 12→20.5 | +82% | 46 | 0.80 | 237% | −3.6% | 0.5 | 1.0 | no | 10.4 | 12 |
| IPDC | 05-13 | 18→33 | +80% | 40 | 0.76 | 322% | −2.5% | 1.0 | 1.3 | no | **4.8** | 18 |
| EMERALDOIL | 05-03 | 14→22 | +78% | 34 | 0.27 | 1258% | −7.1% | 0.4 | 0.7 | no | 13.4 | 14 |
| ANLIMAYARN | 04-29 | 19.6→33 | +75% | 50 | 0.79 | 170% | +0.3% | 0.5 | 0.8 | no | 8.7 | 20 |
| SONARBAINS | 04-05 | 27→44 | +74% | 45 | 0.79 | 345% | −1.1% | 0.9 | 1.1 | no | 11.5 | 27 |
| SKTRIMS | 04-28 | 8.8→14 | +72% | 43 | 0.37 | 768% | −4.9% | 0.9 | 0.9 | no | 10.8 | 9 |
| BNICL | 03-08 | 49→121 | +71% | 33 | 0.80 | 251% | −9.6% | 0.6 | 0.7 | no | 17.3 | 49 |
| ACMEPL | 03-01 | 16→23 | +71% | 46 | 0.85 | 186% | −2.3% | 0.7 | 1.6 | no | 13.4 | 16 |
| MERCINS | 05-07 | 26→45 | +70% | 54 | 0.86 | 146% | +1.6% | 0.7 | 1.2 | no | 12.7 | 26 |
| BDTHAIFOOD | 04-27 | 18→25 | +70% | 51 | 0.86 | 210% | −1.9% | 0.5 | 1.5 | no | 19.9 | 18 |
| SHYAMPSUG | 06-21 | 163→251 | +54% | 44 | 0.68 | 77% | −8.5% | 0.5 | 0.4 | no | 56.3 | 163 |
| FEKDIL | 05-18 | 14→19.6 | +39% | 45 | 0.66 | 167% | −3.2% | 0.4 | 0.4 | no | 11.0 | 14 |
| FEDERALINS | 04-20 | 20.5→26 | +38% | 55 | 0.84 | 139% | +2.2% | 0.8 | 2.6 | no | **5.5** | 21 |
| ZEALBANGLA | 05-13 | 120→149 | +26% | 37 | 0.62 | 87% | −6.1% | 0.8 | 0.5 | no | 14.4 | 120 |
| BSRMLTD | 05-14 | 85→106 | +24% | 55 | 0.88 | 102% | +1.0% | 0.6 | 0.6 | no | **4.0** | 85 |
| BSRMSTEEL | 05-18 | 70→87 | +24% | 46 | 0.90 | 63% | −1.1% | 1.0 | 0.4 | no | **5.7** | 70 |

---

## The common DNA (what most winners shared at launch)

| Trait | % of winners | Read |
|---|---|---|
| **Launched on BELOW-normal volume** (rvol < 1.0×) | **82%** | They start **quiet** — no volume spike (median rvol 0.7×) |
| **Did NOT break a 20-day high** | **93%** | They rise from *inside* their range — this is why our breakout signal misses all of them |
| **Did NOT gap up** | **96%** | The move starts calmly, no overnight jump |
| **Sat within 10% of their 20-day average** | **100%** | **Coiled at the mean** — balanced, not extended |
| **Neutral RSI (40–60)** | **75%** | Not oversold (only 7% were <35), not overbought |
| **Upper part of 1-year range** (pos > 0.65) | **82%** | Near 1-yr *highs* — NOT "buy the bottom" (median pos 0.80) |
| **Above their 200-day average** | **79%** | In a longer-term uptrend already |
| **Huge lifetime room** (≥50% below all-time high) | **93%** | Median **178% below** ATH — fell years ago, lots of headroom |
| **Cheap** (< 40 tk) | **68%** | Median price ~25 tk; cheap stocks make bigger % moves |
| **Tight base** (20d range ≤ 12%) | 39% | Not the majority — but the user's picks (BSRMLTD 4.0, BSRMSTEEL 5.7, FEDERALINS 5.5, IPDC 4.8) were the **tightest** |

### One-line profile
> **A cheap stock, far below its all-time high but near its 1-year high, coiled right on its moving
> averages at a neutral RSI, sitting quiet on low volume — that then starts rising from inside its range.**

This is the opposite of a breakout (no volume, no new high) and the opposite of an oversold bounce
(neutral RSI, near 1-yr highs). It's a **quiet coiled spring**.

---

## The trigger — the honest part

**There is no consistent price/volume trigger visible at the launch.** On the launch day: low volume (median
0.7×), no new high (93%), no gap (96%). The spark is **not in the chart.**

- For only **36%**, volume confirmed within the next 1–3 days (rvol ≥ 1.5×) — these are the catchable ones
  (you see volume arrive *after* day 0 and can jump on it).
- For the other **64%** — including SHYAMPSUG (+54%), BSRMSTEEL, ZEALBANGLA, FEKDIL — the stock kept
  rising on **quiet volume**, with no volume tell at all.

**Conclusion on the trigger:** the catalyst is almost always **external** — company news, dividend/earnings,
sector rotation, or operator/syndicate accumulation in thin names — and it is **invisible in price/volume at
the moment of launch.** The chart shows the *setup* (the coiled spring), never the *match* that lights it.

---

## Outliers / unique cases (worth remembering)

- **SICL** — the *only* one with a launch-day volume spike (3.5×) from a tight base (7.8). The textbook
  "volume breakout from a coil" — but it was 1 of 28. Rare.
- **SHYAMPSUG** (+54%) — launched right after a **−25% crash** (very volatile, base 56%) on *low* volume.
  A violent V-snapback in a thin, wild stock. Different animal from the quiet coils.
- **EMERALDOIL / HFL / SAIFPOWER / SKTRIMS** — the only ones near their **1-year low** (pos 0.27–0.38) with
  *enormous* lifetime room (731–1258%). Cheap penny-class rockets — high reward, high risk.
- **DOMINAGE** — already **+74% above its 200-SMA** at launch (extended) yet still ran. Momentum continuation.
- **ZEALBANGLA (13.7k), APEXTANRY (16k), SHYAMPSUG (49k)** — illiquid (avg vol < 50k). Thin names where a
  single operator can move the price — un-tradeable safely and excluded by our liquidity floor.

---

## The hard truth (and how we should use this)

The "quiet coiled spring" profile is **real but common** — at any given time *hundreds* of cheap stocks sit
quiet on their moving averages with room above. Only a handful ignite, and **which one is decided by news
the chart can't see.** So this profile **cannot predict winners**; it can only **narrow the field**.

**Therefore the realistic play is a two-step system, not a buy signal:**

1. **WATCHLIST (the coil screen):** continuously list stocks that match the DNA — cheap, ≥50% below ATH,
   upper-half of 1-yr range, within ~10% of a rising 20/50-SMA, neutral RSI, tight base, currently quiet.
   This is a *small daily shortlist of candidates*, not buys.
2. **FAST-REACTION ALERT (the ignition):** when a watchlist name **starts moving** — first day its volume
   jumps above normal and price ticks up off the coil — fire an alert so we can act in the first 1–2 days
   (the 36% where volume confirms). Accept that the pure-quiet runners (SHYAMPSUG type) will be missed.

**What to drop:** chasing "buy the exact bottom" (unpredictable) and demanding a volume spike (misses 82% of
these). **What to keep:** the coil watchlist + an ignition alert + strict risk control (these are volatile,
often thin — size small, use stops).

---

# PART 2 — Decliner Anatomy (the vice-versa)

Same method, flipped: scanned for **clean drastic falls** — dropped **≥20% within 30 days** with a pre-trough
bounce no worse than +8%, topping near a local high. Found **69**; profiled the **top 22** (steepest falls).

## The 22 decliners (profiled at the TOP, before the fall)

| Ticker | Top date | Top→Now | Fell | RSI | pos 1y | ret 20d *before* | vs SMA20 | rvol (at top) | new 20d-hi | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| PRIMEFIN | 03-15 | 5.9→3.0 | −44% | **78** | 1.00 | **+146%** | +42% | 1.5 | yes | — |
| APEXSPINN | 05-13 | 436→399 | −33% | **81** | 0.99 | +78% | +28% | 1.0 | — | — |
| GSPFINANCE | 03-03 | 6.2→3.4 | −32% | **87** | 0.91 | **+210%** | +57% | 2.9 | yes | +9% |
| ISLAMIBANK | 02-03 | 54→32 | −31% | **87** | 0.96 | +47% | +36% | **4.1** | — | +3% |
| PRAGATILIF | 02-18 | 259→188 | −31% | **73** | 0.91 | +57% | +19% | 1.9 | — | — |
| BIFC | 03-03 | 7.2→4.2 | −31% | **94** | 0.81 | **+324%** | +89% | **4.4** | yes | +9% |
| UNIONCAP | 03-03 | 6.8→4.6 | −29% | **80** | 0.94 | +84% | +43% | 3.2 | — | +5% |
| MEGCONMILK | 06-03 | 49→41 | −29% | **74** | 0.99 | +45% | +26% | 1.3 | — | — |
| NBL | 03-02 | 6.0→3.9 | −28% | **76** | 1.00 | +82% | +33% | 1.5 | yes | +9% |
| MEGHNAPET | 06-03 | 91→81 | −28% | **89** | 1.00 | +116% | +57% | 0.7 | yes | — |
| BAYLEASING | 03-02 | 6.2→4.6 | −27% | **75** | 0.93 | +72% | +30% | 2.2 | yes | +4% |
| BATBC | 02-15 | 289→220 | −27% | **78** | 0.81 | +15% | +8% | 2.6 | — | — |
| FIRSTFIN | 03-03 | 6.1→4.1 | −26% | **77** | 1.00 | +110% | +37% | 2.1 | yes | +9% |
| SAIHAMTEX | 02-15 | 24→19 | −27% | **79** | 0.95 | +18% | +12% | 3.1 | — | +8% |
| *(+8 more financials/textiles, same shape)* | | | −26 to −33% | 60–87 | 0.6–1.0 | +10 to +200% | +6 to +57% | 1.5–8.2 | mixed | mixed |

## The Decliner DNA — a near-perfect mirror of the winners

| Trait at the TOP | % of decliners | Winners (for contrast) |
|---|---|---|
| **Overbought RSI > 70** | **~70%** (median **76**) | winners ~48 (neutral) |
| **Just ran up hard** (≥+45% in 20 days) | **59%** (median **+52%/20d**) | winners ~0% (flat) |
| **Stretched above 20-SMA** (>10%) | **77%** (median **+27%**) | winners within ±10% |
| **At/near 1-year high** (pos ≥ 0.90) | **68%** (median 0.94) | winners ~0.80 |
| **ELEVATED / climax volume at the top** (rvol ≥ 1.5×) | **82%** (median **2.1×**) | winners **0.7×** (quiet) |
| **Final blow-off** (new 20-day high) | 36% | winners 7% |
| **Exhaustion gap-up** (≥3%) | 41% | winners 4% |
| **Cheap speculative penny** (< 10 tk) | 50% | — |

### One-line profile
> **A stock that has just run up parabolically (+50–300% in weeks), is overbought (RSI 70–94), stretched far
> above its averages, pinned at its 1-year high, on loud climax volume** — often the cheap speculative
> financials. That's a stock about to fall.

Note: **APEXSPINN and MEGHNAPET appear in BOTH lists** — they launched quiet (Part 1), ran parabolic, then
collapsed (Part 2). The full life-cycle is in the data: *quiet coil → ignition → parabola → exhaustion → crash.*

---

# PART 3 — So is it news? The honest answer

**The rise and the fall are NOT symmetric, and that's the most important finding in this whole study:**

- **Going UP needs a reason.** A quiet coiled stock will sit forever unless an *external catalyst* (news,
  dividend, earnings, sector flow, operator buying) lights it. That catalyst is **invisible in the chart** —
  which is why winners give no advance tell and **cannot be reliably predicted.** Here, *yes, it's news* (or
  an operator) — and you usually can't see it coming.

- **Going DOWN needs no reason — it's gravity.** Once a stock is parabolic and overbought, it falls under its
  **own weight**: buyers are exhausted, early buyers take profit, the climax volume *is* the smart money
  selling. News can pick the *day*, but the fall was **inevitable and clearly visible in advance** (RSI 90,
  +200% in a month, gapping up on huge volume is a flashing red light).

**The asymmetry you can act on:** the chart **can't tell you what will go up, but it CAN tell you what is
dangerously extended and likely to fall.** Avoiding/exiting the falls is far more doable than catching the
rises. *Risk management is the real, reliable edge here — not stock-picking.*

**Practical rules this gives us:**
1. **Never chase a stock that's already run +50%+ in a few weeks at RSI > 75 on a volume climax** — that's the
   decliner DNA; you'd be the exit liquidity. (This is also exactly what our breakout signal's "not extended"
   and overbought guards are *trying* to enforce.)
2. **If you hold something that goes parabolic, that's a SELL signal, not a hold** — overbought + extended +
   climax volume = take profit. The data says it round-trips.
3. **The cheap speculative financials** (sub-10 tk: PRIMEFIN, BIFC, GSPFINANCE, NBL, UNIONCAP…) are the
   pump-and-dump zone — biggest rips *and* biggest crashes. Trade tiny or avoid.

---

### Next steps (when we build on this)
- **Up-side:** build the **coil watchlist** + **ignition alert** (Part 1) — narrow the field, react fast.
- **Down-side (easier & more reliable):** build an **"Overheated / take-profit" warning** — flag any stock
  that's overbought + stretched far above its MAs + parabolic + on climax volume. This is the high-confidence
  half. Use it to avoid buying tops and to exit winners before they round-trip.
- Track both live (like the reversal tracker) and verify forward before trusting either.
