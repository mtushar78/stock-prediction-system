# 🏛️ Long-Term Investing Strategy — the "Dividend Fortress" List

**Purpose:** a buy-and-hold shortlist of DSE companies worth owning for **years**, ranked by the one fundamental signal that is hardest to fake in a manipulated market: **a long, unbroken record of real cash dividends.**

**Where:** the `/long-term` page in the app · API: `/api/long-term` · data table: `dividend_history` · refreshed automatically every **Saturday 8 AM** with the weekly fundamentals scrape.

**Status:** shipped 2026-07-08. Backtest results in §6.

---

## 1. The thesis (why dividends, why DSE)

The trading side of this system rests on "price can be faked, volume cannot." The investing side rests on the fundamental analog:

> **Earnings can be window-dressed. Prices can be painted. A cash dividend cannot — it costs the sponsors real taka, every year, paid to every shareholder.**

A company that has paid a cash dividend for 10+ consecutive years has proven, 10+ separate times, that:
1. it actually generates cash (not just paper EPS),
2. its sponsors are willing to share it with minority shareholders,
3. its board treats the dividend as a commitment, not a one-off gesture.

On DSE this matters double, because the alternative "growth story" narrative is exactly the raw material of pump-and-dump syndicates. The dividend record is the anti-narrative: boring, verifiable, cumulative.

**The benchmark that matters:** a bank FDR pays ~8–9% risk-free. A fortress stock at a 6–8% cash yield that also *grows* its dividend competes with the FDR while keeping upside. That comparison — not "will it go up this month" — is the long-term lens.

---

## 2. Data (what we collect and from where)

| Data | Source | Depth | Refresh |
|---|---|---|---|
| **Cash dividend % per year** | DSE company page ("Cash Dividend" row) | ~11 years (2015→) | Weekly (Sat 8 AM cron) |
| **Stock/bonus dividend % per year** | same page ("Bonus Issue" row) | back to the 1990s for old listings | Weekly |
| EPS, NAV, P/E (audited) | same page, annual table | 5 years | Weekly |
| Sponsor holding %, loans, reserves → D/E, ROE | same page | current | Weekly |
| Sector, category, market cap, face value | same page | current | Weekly |
| Price, 20-day volume | `stock_data` (scraper) | 14 years | Daily |

Stored in `dividend_history (ticker, year, cash_pct, stock_pct)`. **Dividend percentages are % of face value** (usually 10 tk): a "120%" cash dividend = 12 tk/share. Yield = 12 ÷ price.

---

## 3. Hard gates (a stock must pass ALL of these to appear)

These remove the un-investable before any scoring:

1. **Not category Z** (defaulters/AGM failures).
2. **Paid a cash dividend for the latest or previous year** — currently paying, not "used to pay."
3. **Paid in ≥3 of the last 5 years** — minimum reliability.
4. **EPS > 0** — loss-makers don't sustain dividends.
5. **Liquidity:** 20-day avg volume ≥ 10,000 shares — you must be able to exit.
6. **Price & face value known** — yield must be computable.

Typically ~60–100 of 434 listed names survive the gates.

---

## 4. The score (0–100) — what "fortress" means, quantified

| Component | Max | Rule |
|---|---|---|
| **Reliability** | 25 | paid cash in 5/5 of last 5 years = 25 · 4/5 = 15 · 3/5 = 5 |
| **Streak** | 15 | consecutive paying years: ≥10y = 15 · ≥7y = 10 · ≥5y = 5 |
| **Yield** | 20 | ≥8% = 20 · ≥6% = 16 · ≥4% = 10 · ≥2.5% = 5 |
| **Dividend growth** | 10 | latest cash % vs 5 years ago: ≥+25% = 10 · ≥0% = 6 |
| **Earnings quality** | 20 | EPS>0 (5) + payout ≤80% of EPS (8, ≤100% = 4) + ROE ≥12% (7, ≥8% = 4) |
| **Balance sheet & governance** | 10 | D/E <50% (4) + sponsor ≥30% (3) + category A (3) |

**Grades:** A ≥ 75 · B ≥ 60 · C ≥ 45 · D < 45.

Design choices, stated honestly:
- **Reliability + streak (40 pts) dominate** because consistency *is* the thesis; yield without reliability is a trap (a 12% yield on a company that pays once is worth less than 6% paid 15 years running).
- **Payout ratio ≤80%** rewards dividends the earnings actually cover — a payout >100% is eating reserves and will be cut.
- **Sponsor ≥30%**: skin in the game; sponsors who own the company want the dividend themselves.
- **Growth is worth only 10** — on DSE, stability beats growth promises.

---

## 5. How to actually use the list (the operating rules)

1. **This is the *investing* bucket — separate money from the *trading* bucket.** Decide the split first (e.g., 60% long-term / 30% swing / 10% cash) and never let one raid the other.
2. **Build a basket of 8–12 names across ≥4 sectors.** One company can cut its dividend; eight diversified fortresses rarely all cut together.
3. **Buy boring, buy gradually.** Spread entries over weeks/months (cost averaging). Long-term entries don't need timing — but buying during Reversal Season (breadth < 45%) gets you fortress names at panic prices with fatter yields.
4. **Hold while the thesis holds.** Review **twice a year** (post-AGM seasons). Sell only when: the dividend is cut/skipped, payout goes >100% with falling EPS, sponsors start dumping, or category drops. **Do not sell because the price wiggled.**
5. **Reinvest the dividends** — into the same list. Compounding is the whole point: 8% yield reinvested doubles the position in ~9 years before any price gain.
6. **Check the newest quarterly report before committing serious money** — the app's fundamentals are weekly and post-AGM; they can lag a fresh deterioration.

**What this list will never do:** beat the swing signals in a good month, tell you the bottom, or move fast. It's the slow half of the portfolio — deliberately.

---

## 6. Validation — point-in-time backtest (`lt_strategy_study.py`)

**Method:** each July 1 (2020–2025), pick using ONLY then-knowable data (dividends declared for prior years + price/liquidity at pick date); hold 12 months; total return = price return + cash dividends received + bonus-share dilution correction ((1+B) exit adjustment). Benchmark = every liquid stock (vol ≥ 10k, price ≥ 10), same return math.

### 6.1 Results (run 2026-07-08, data through 2026-07-06)

12-month total returns (price + cash dividends + bonus adjustment), July→July cohorts:

| Portfolio | Avg/yr | Compounded (6y) | Positive years | 2023 (bear) | 2024 (bear) |
|---|---|---|---|---|---|
| **FORT-HY** — top 10 by *yield* among reliable payers | +17.7% | ×2.49 | **6 / 6** | **+5.9%** | **+14.4%** |
| **FORT10** — top 10 by streak-then-yield | +23.7% | ×2.98 | 4 / 6 | −1.7% | −21.3% |
| **ALLQ** — every qualifier, equal weight | +23.9% | ×2.76 | 4 / 6 | −11.8% | −13.3% |
| Universe (all liquid stocks) | +21.5% | ×2.53 | 4 / 6 | −10.7% | −14.7% |

**The honest reading:**
1. **The screen's raw return edge over the market is modest** (~+2pp/yr average). Do not expect dividend stocks to massively outrun a bull market — 2020's +93% universe year lifts every average.
2. **The real prize is the risk profile of the *high-yield* fortress subset (FORT-HY): positive in ALL six years, including +5.9% and +14.4% in the two bear years where the market lost 10–15%.** The dividends themselves carried it through. That bond-like smoothness with equity upside is exactly what long-term money is for — you can *hold* it through a crash without panic, which is the behavior that actually compounds.
3. Practical implication: when picking from the list, **weight current yield heavily among the reliable payers** (the YIELD column) rather than chasing the longest streak alone. Reliability qualifies a stock; yield is what defends the bear years.

**Honesty caveats (read these):**
- **Survivorship bias:** the DSE page only exists for currently-listed companies; delisted losers are missing from both cohort and benchmark. Treat absolute numbers as optimistic; the *spread vs universe* is the more trustworthy figure.
- Cash-dividend pages list ~11 years → cohorts start 2020 (6 pick-years, one of them partial).
- AGM timing approximated (dividend "for year Y" assumed received in the July Y→Y+1 window).
- Rights issues not modeled; bonus issues corrected.
- 6 yearly cohorts is a small sample. This validates the *direction* of the edge, not a precise expectancy.

---

## 7. Maintenance

- **Weekly** (automatic): Saturday 8 AM scrape refreshes fundamentals + dividend history.
- **Yearly** (manual, ~10 min): re-run `python lt_strategy_study.py` after the AGM season to extend the backtest by one cohort; skim for any score-component drift.
- The scoring lives in `backend/main.py :: _compute_long_term_list()` — change thresholds there; the UI reads whatever the API sends.

---

*Companion docs: `TRADING_PLAYBOOK.md` (the fast half of the portfolio) · `PROFITABILITY_AUDIT.md` (why the trading side is reversal-only).*
