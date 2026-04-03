# DSE Sniper — Limitations & Improvement Opportunities

## CRITICAL LIMITATIONS (High Impact on Syndicate Detection)

### 1. No Paid-Up Capital Data Feed
- **Problem**: The `low_float` scoring component (20 pts) almost never fires because no paid-up capital data is automatically ingested. Low-float stocks are the primary syndicate targets — missing this data blinds you to the most manipulated stocks.
- **Impact**: Syndicate plays on low-cap stocks (< 50 Cr) get the same score as large-cap stocks.
- **Fix**: Scrape paid-up capital from DSE website (`/displayCompany.php?name=TICKER`) or integrate a data provider that has this field. Store in a `ticker_fundamentals` table and auto-feed into the analyzer.

### 2. No Intraday Volume Profile (Tick-Level Data)
- **Problem**: You only get EOD (or snapshot) OHLCV data. Syndicates accumulate during specific intraday windows (e.g., quiet midday hours). Without tick-level or at least 5-minute bars, you can't detect:
  - Block trades clustered in time
  - Volume spikes in the last 10 minutes (dump signal)
  - Opening auction manipulation
- **Impact**: You're detecting accumulation at the daily level when the real signal is at the intraday level.
- **Fix**: DSE provides a "Trade" page with last trade data. Scrape it every minute during market hours and store as intraday bars. Even 30-minute bars would be a massive improvement.

### 3. No Public vs Institutional Volume Breakdown
- **Problem**: The `institutional_flow` component checks `public_volume` vs `volume`, but `public_volume` is always NULL in the database. The DSE website does show "Public Vol" vs "Total Vol" but it's not being scraped.
- **Impact**: 15 pts of scoring capacity (institutional flow) is permanently disabled.
- **Fix**: Update `dse_scraper.py` to extract the "Pub. Vol" column from DSE's latest share price page and store it in the `public_volume` column of `stock_data`.

### 4. Linear Volume Projection (Now Fixed in v6)
- **Problem (v5)**: Projected volume used linear extrapolation, which overestimated during opening rush and underestimated during midday quiet.
- **Status**: Fixed in v6 with U-shaped cumulative model. But the model uses fixed coefficients (25/50/25 split) — real DSE distribution may differ.
- **Future**: Calibrate the U-shape coefficients from actual intraday data once tick-level scraping is implemented.

### 5. No Sector/Industry Correlation
- **Problem**: Syndicates often rotate across sectors. If banking stocks are suddenly getting volume, other banking stocks are likely to follow. Currently each stock is analyzed in isolation.
- **Impact**: You miss sector-wide accumulation patterns and can't detect "the next stock in the sector play."
- **Fix**: Add sector tags to each ticker (from DSE sector classification). Compute sector-level RVOL aggregates. Flag sectors where 3+ stocks show simultaneous elevated volume.

---

## SIGNIFICANT LIMITATIONS (Medium Impact)

### 6. No Sell-Side Volume Analysis
- **Problem**: The system detects BUY signals well but has limited ability to detect when syndicates are DISTRIBUTING (selling). The Climax detector (RVOL > 5.0 + red candle) only catches extreme dumps.
- **Fix**: Add distribution detection:
  - High volume + price at resistance = distribution
  - Multiple doji candles at highs with elevated volume = indecision → distribution
  - OBV turning down while price stays flat = stealth selling

### 7. Support/Resistance Uses Only Simple Swing Points
- **Problem**: `find_support_resistance()` uses a 3-bar swing high/low which misses:
  - Volume-weighted levels (where most trading occurred)
  - Round-number psychology levels (100, 50, 200, etc.)
  - Gap levels (significant unfilled gaps)
- **Fix**: Add volume profile (price bins weighted by volume) for more reliable S/R levels. Also add round-number level detection.

### 8. No Historical Win Rate Tracking
- **Problem**: When a signal fires, there's no tracking of whether it was profitable. You can't measure:
  - Win rate by signal type
  - Average holding period for profitable trades
  - Which components contributed to winning trades
- **Fix**: When a trade is removed from portfolio, record the exit in a `trade_history` table with entry/exit prices, holding period, P&L, and the original signal reasons. Use this to weight scoring components.

### 9. Database Connection Management
- **Problem**: `DatabaseManager` uses `sqlite3.connect()` directly. Every API call creates a new connection, and some endpoints (like portfolio) create multiple connections in a single request. SQLite can't handle concurrent writes well.
- **Fix**: Use connection pooling (or switch to WAL mode for better concurrency). For the backend, a single WAL-mode connection with proper locking would reduce connection overhead.

### 10. No Market Breadth Context
- **Problem**: The analyzer doesn't consider overall market conditions. During a broad market rally, most stocks show elevated volume — this dilutes signal quality. During a crash, even syndicate targets get sold.
- **Fix**: Calculate DSEX-wide metrics:
  - % of stocks above their 200 SMA (market health indicator)
  - Total market RVOL (is the market itself in elevated volume?)
  - Advance/Decline ratio
  - Use these to adjust signal thresholds dynamically (tighter in euphoria, looser in early recovery).

---

## MODERATE LIMITATIONS (Nice-to-Have Improvements)

### 11. Scraper Resilience
- **Problem**: `dse_scraper.py` depends on a specific HTML structure of DSE's website. If DSE changes their layout, scraping breaks silently.
- **Fix**: Add HTML structure validation after scraping. If expected columns don't match, alert via notification instead of silently failing.

### 12. No Price Alert / Notification System
- **Problem**: Signals are only visible on the dashboard. If a BUY signal fires at 11 AM, you won't know until you check the dashboard.
- **Fix**: Add Telegram/Discord notification when:
  - A new BUY signal appears
  - A portfolio holding triggers STOP_LOSS or TAKE_PROFIT
  - An existing WAIT signal upgrades to BUY

### 13. Excessive Scraping Frequency
- **Problem**: Backend schedules 11 scrapes per day (every 30 min from 10:30 to 3:15). This is wasteful — DSE's snapshot data doesn't change frequently enough to justify this.
- **Fix**: Reduce to 4 scrapes: 10:30 AM (early), 12:00 PM (midday), 2:00 PM (pre-close), 3:15 PM (final EOD). The 10-11 AM period is too early for reliable signals anyway.

### 14. Frontend Doesn't Show v6 Components
- **Problem**: The `SignalDetailModal` and `SignalsTable` only display v5 fields. The new v6 components (Price Squeeze, Buying Streak, Smart Money, VWAP Proximity) are computed in the backend but not shown in the UI.
- **Fix**: Update `frontend/app/types.ts` and the signal detail modal to render v6 breakdown components.

### 15. No Backtesting Framework
- **Problem**: When you change scoring weights or add new components, there's no way to measure whether the change improved or hurt signal quality against historical data.
- **Fix**: Build a simple backtester:
  - Take historical data
  - Run the scoring engine on each date
  - Simulate trades (enter on BUY, exit on sell signals)
  - Track simulated P&L, win rate, max drawdown
  - Compare old vs new scoring

### 16. 200 SMA Hard Filter at -10%
- **Problem**: Stocks more than 10% below their 200 SMA are completely filtered out. Some syndicate plays involve beaten-down stocks that they accumulate heavily below SMA before a massive pump.
- **Fix**: Instead of hard-filtering at -10%, keep them but with heavy penalty. Or add a separate "Deep Value Accumulation" detector for stocks 10-20% below SMA with extreme volume (RVOL > 4.0).

### 17. No Correlation with Index/Sector Movement
- **Problem**: A stock can show elevated volume simply because DSEX moved big that day. Currently there's no way to distinguish "stock-specific volume" from "market-driven volume."
- **Fix**: Calculate Beta-adjusted RVOL: if the market itself is 2x normal volume, a stock at 3x is really only 1.5x on a relative basis.

### 18. Commission Model is Simplified
- **Problem**: The 0.40% flat commission rate doesn't account for:
  - DP charges
  - CDBL fees
  - Different brokerage rates
  - Tax implications
- **Fix**: Make commission configurable in config.yaml with multiple fee tiers.

---

## ARCHITECTURE IMPROVEMENTS

### 19. Move to Async Database Operations
- **Problem**: All database operations in the analyzer and portfolio manager are synchronous, blocking the FastAPI event loop.
- **Fix**: Use `aiosqlite` or `databases` library for async DB access. The backend already uses `asyncio` for scheduling — the database operations should match.

### 20. Configuration Not Used in Analyzer
- **Problem**: `config.yaml` defines thresholds (rvol_threshold, sma_period, scoring weights) but the `StockAnalyzer` class hardcodes all values internally.
- **Fix**: Load config.yaml in StockAnalyzer.__init__ and use those values. This would allow tuning without code changes.

### 21. No Data Validation Layer
- **Problem**: If a scrape returns garbage data (zero prices, negative volumes, dates in the future), it goes straight into the database and pollutes analysis.
- **Fix**: Add a validation layer between scraping and database insertion. Reject rows where:
  - close == 0 or close < 0
  - volume < 0
  - date is in the future
  - high < low
  - close > high or close < low

### 22. No Rate Limiting on API Endpoints
- **Problem**: `/api/trigger-update` can be spammed, causing multiple concurrent scrapes. `/api/analyze-ticker` recalculates from scratch on every call.
- **Fix**: Add rate limiting middleware. Cache analysis results for 5 minutes using a simple TTL cache.

---

## QUICK WINS (Easy to Implement, Immediate Value)

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| A | Scrape public_volume from DSE and enable institutional flow scoring | Low | High |
| B | Add Telegram notification for BUY signals and sell alerts | Low | High |
| C | Reduce scrape frequency from 11 to 4 per day | Trivial | Medium |
| D | Update frontend to display v6 scoring components | Low | Medium |
| E | Add sector tags and sector-level RVOL | Medium | High |
| F | Scrape paid-up capital from DSE company pages | Medium | High |
| G | Add data validation before database insertion | Low | Medium |
| H | Load scoring thresholds from config.yaml instead of hardcoding | Low | Medium |

---

## SYNDICATE DETECTION WISH LIST (Future Research)

1. **Order book depth analysis** — If DSE provides Level 2 data, detect fake bid walls (common syndicate tactic to create support illusion).
2. **Cross-stock volume timing** — When syndicate exits one stock and enters another, there's a volume signature across stocks in the same timeframe.
3. **Social media sentiment** — DSE syndicates often coordinate via Telegram groups and Facebook. Scraping public groups for ticker mentions could provide early signals.
4. **Circuit breaker proximity** — Stocks approaching upper circuit with sustained volume are likely syndicate-driven. Add a "circuit proximity" indicator.
5. **Net foreign buy/sell data** — DSE publishes daily foreign investor activity. Correlate with volume anomalies.
6. **Multi-timeframe analysis** — Same stock analyzed on weekly + daily timeframes. Weekly accumulation + daily breakout = strongest signal.
