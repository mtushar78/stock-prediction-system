"""Coil scanner — the "quiet coiled spring" watchlist (docs/WINNER_ANATOMY.md).

Finds stocks that match the launch-day DNA of the big DSE winners profiled in
the winner-anatomy study: the user's "potential to go high but not high yet"
list. The descriptive DNA was then FORWARD-TESTED point-in-time (backtest_
coil.py, monthly checkpoints 2023-01..2026-07) and the gates below keep only
the sub-profile that actually enriched forward outcomes:

  PIT result for the final profile (tight coil above the 200-day SMA), vs the
  liquid universe baseline:
    * P(+20% within 30 sessions):  18.5%  vs 15.6%   (more winners caught)
    * P(-15% within 30 sessions):   7.9%  vs 18.0%   (less than HALF the risk)
    * 3-month mean return lift:    +6.8 percentage points
  ...robust across 2023 / 2025 / 2026 and across RSI / position / price cuts.

Gates and how they were chosen:
  * within 10% of the 20-day SMA     — 100% of the study's winners; hard gate
  * 20-day base range <= 12%         — THE load-bearing gate: it alone cuts the
                                       -15% risk from 27% to 8%. (The user's own
                                       examples were the tightest coils.)
  * above the 200-day SMA            — hard gate; below it the same shape LOSES
                                       (6% win / 34% loss forward-tested)
  * 1-yr range position 0.55..0.95   — launches come from the upper range, but
                                       the sweet spot is 0.55-0.75; pinned AT
                                       the high (>0.75) tested worse, so the
                                       score peaks mid-upper, not at the top
  * headroom >= 20% below the old high — room to run, but NOT scored: huge
                                       (>100%) headroom forward-tested as a
                                       TRAP (50% loss rate), not a bonus
  * neutral RSI, not already running — winners were flat at launch; the
                                       decliner DNA (Part 2) is hard-rejected

And the study's Part-2 decliner DNA (overbought + parabolic + climax volume) is
explicitly EXCLUDED, so the list can never surface a top.

Stages implement the study's two-step play:
  COILED   - matches the DNA, still quiet. The watchlist. Not a buy.
  CREEPING - a coil whose price has started rising QUIETLY (2+ green closes off
             the coil, no volume tell) — the SHYAMPSUG-type move the study says
             runs with no volume confirmation at all. Aggressive.
  IGNITING - a coil where volume JUST arrived (rvol >= 1.5x) on an up day and
             price is still within reach of the coil — the catchable 36% where
             the study says you can act in the first 1-2 days.

HONESTY (from the study itself): even the enriched profile narrows the field,
it cannot pick THE winner — the catalyst that lights a coil is almost always
external (news/operators) and invisible in the chart. ~1 in 5 of these runs
+20% within 30 sessions; the real, proven benefit is the collapsed downside
(a tight coil above the 200-day rarely falls hard). A WATCHLIST + fast-reaction
screen, never a buy signal. Re-run backtest_coil.py after any threshold change.

All thresholds are module constants so they are easy to tune.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

# Reuse the corporate-action back-adjustment + Wilder RSI proven in the rebound
# scanner so ex-date drops aren't read as crashes and RSI matches the modal.
from src.rebound_scanner import _back_adjust, _rsi, _clean

logger = logging.getLogger(__name__)

# ---- Universe / liquidity gates (mirror the other scanners) ------------- #
CALENDAR_LOOKBACK_DAYS = 800    # ~2y of bars: 1y range + SMA200 + ATH proxy depth
MIN_BARS = 120                  # need a real 1-year-ish context to trust the coil
MIN_PRICE = 5.0                 # avoid untradeable penny names
MIN_AVG_VOL20 = 5000            # sanity floor on shares/day
MIN_AVG_TURNOVER_BDT = 500_000  # traded VALUE floor — the real liquidity filter
MAX_STALE_TRADING_DAYS = 5      # must have traded within N of the last session

# ---- The coil DNA gates (winner traits, kept only where the PIT test ---- #
# ---- confirmed them — see the module docstring) ------------------------- #
COIL_MAX_DIST_SMA20 = 10.0      # 100% of winners sat within 10% of the 20-day SMA
TIGHT_BASE_RANGE20 = 12.0       # tier TIGHT: the load-bearing gate (risk 27%->8%)
MAX_BASE_RANGE20 = 15.0         # tier WIDE: 12-15% band — best win-rate lift
                                # (+1.9pp) at market-average risk; labeled looser
MIN_POS_1Y = 0.55               # launches come from the upper 1-yr range
MIN_ATH_ROOM_PCT = 20.0         # needs room to run (info + gate; NOT scored)
MAX_RSI = 68.0                  # winners were neutral (med 48); >68 = late/hot
MAX_RET20_PCT = 22.0            # winners were FLAT into launch — already ran = out
MAX_QUIET_RVOL = 3.0            # a loud bar is only ok if it's a green ignition

# ---- Decliner-DNA rejection (Part 2 of the study — never list a top) ---- #
DECLINE_RSI = 70.0              # overbought
DECLINE_EXT_SMA20 = 12.0        # stretched above the mean
DECLINE_RET20 = 45.0            # parabolic run into today

# ---- Stage detection ---------------------------------------------------- #
IGNITE_MIN_RVOL = 1.5           # the study's ignition: volume arrives (>=1.5x)...
IGNITE_MIN_DAY_PCT = 1.0        # ...on a real up day...
IGNITE_MAX_EXT_SMA20 = 12.0     # ...while price is still within reach of the coil
CREEP_MIN_RET2 = 2.0            # quiet rise: >=2% over 2 days...
CREEP_MAX_EXT_SMA20 = 8.0       # ...still hugging the mean (no chase)
QUIET_RVOL = 1.3                # a COILED name today is at/below normal volume


def _sma(a: np.ndarray, n: int) -> float | None:
    if len(a) < n:
        return None
    return float(a[-n:].mean())


def _sma_ago(a: np.ndarray, n: int, ago: int) -> float | None:
    if len(a) < n + ago:
        return None
    return float(a[-(n + ago):len(a) - ago].mean())


def _analyze_one(ticker: str, df: pd.DataFrame, sector: str | None,
                 stale_cutoff: str | None = None) -> dict | None:
    """Return a coil row for `ticker`, or None if it doesn't match the DNA."""
    df = df[df['close'] > 0].sort_values('date')
    if len(df) < MIN_BARS:
        return None
    df = df.tail(400).reset_index(drop=True)   # bound the compute; >=1y kept

    closes_raw = df['close'].to_numpy(dtype=float)
    opens_raw = df['open'].to_numpy(dtype=float)
    highs_raw = df['high'].to_numpy(dtype=float)
    lows_raw = df['low'].to_numpy(dtype=float)
    vols = df['volume'].to_numpy(dtype=float)
    dates = df['date'].astype(str).str[:10].tolist()

    if stale_cutoff is not None and dates[-1] < stale_cutoff:
        return None

    # DSE data hygiene: some bars store close>0 but low/high/open<=0.
    lows_raw = np.where(lows_raw <= 0, closes_raw, lows_raw)
    highs_raw = np.where(highs_raw <= 0, closes_raw, highs_raw)
    opens_raw = np.where((opens_raw <= 0) | np.isnan(opens_raw), closes_raw, opens_raw)

    price = float(closes_raw[-1])
    if price < MIN_PRICE:
        return None

    turnover = closes_raw * vols
    avg_turnover20 = float(turnover[-20:].mean())
    avg_vol20 = float(vols[-20:].mean())
    if avg_turnover20 < MIN_AVG_TURNOVER_BDT or avg_vol20 < MIN_AVG_VOL20:
        return None

    # Back-adjust for corporate actions (latest bar's factor is always 1.0).
    closes, highs, lows, gap_idx = _back_adjust(closes_raw, highs_raw, lows_raw)
    action_dates = [dates[i] for i in gap_idx]
    n = len(closes)

    # ---- Core coil measurements ----
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    sma20_10ago = _sma_ago(closes, 20, 10)
    sma50_10ago = _sma_ago(closes, 50, 10)
    sma200_20ago = _sma_ago(closes, 200, 20)
    if sma20 is None or sma20 <= 0:
        return None

    dist_sma20 = (price / sma20 - 1) * 100.0

    # 1-year range position (0 = at the low, 1 = at the high).
    yr = closes[-252:] if n >= 252 else closes
    lo1y, hi1y = float(yr.min()), float(yr.max())
    pos_1y = (price - lo1y) / (hi1y - lo1y) if hi1y > lo1y else 0.5

    # Lifetime-high headroom (ATH proxy = highest adjusted high in our window;
    # the study's winners had median 178% of room back to theirs).
    ath = float(highs.max())
    ath_room_pct = (ath - price) / price * 100.0 if price > 0 else 0.0

    rsi = _rsi(closes)
    ret_5d = (price / float(closes[-6]) - 1) * 100.0 if n >= 6 else None
    ret_20d = (price / float(closes[-21]) - 1) * 100.0 if n >= 21 else None
    rvol = float(vols[-1]) / avg_vol20 if avg_vol20 > 0 else 1.0
    rvol5 = float(vols[-5:].mean()) / avg_vol20 if avg_vol20 > 0 else 1.0

    # 20-day base tightness (high-low range as % of price) + contraction vs the
    # prior 60d — the "spring being wound" measure.
    hi20 = float(highs[-20:].max()); lo20 = float(lows[-20:].min())
    base_range20 = (hi20 - lo20) / price * 100.0 if price > 0 else 99.0
    hi60 = float(highs[-60:].max()); lo60 = float(lows[-60:].min())
    range60 = (hi60 - lo60) / price * 100.0 if price > 0 else base_range20
    contraction = base_range20 / range60 if range60 > 0 else 1.0

    last_green = bool(closes_raw[-1] > opens_raw[-1])
    day_pct = (closes[-1] / closes[-2] - 1) * 100.0 if n >= 2 else 0.0
    up1 = n >= 2 and closes[-1] > closes[-2]
    up2 = n >= 3 and closes[-2] > closes[-3]
    ret_2d = (price / float(closes[-3]) - 1) * 100.0 if n >= 3 else 0.0

    # =====================================================================
    # GATES — the winner DNA (reject anything that doesn't match), then the
    # decliner DNA (reject anything that looks like a top).
    # =====================================================================
    if abs(dist_sma20) > COIL_MAX_DIST_SMA20:
        return None                       # 100% of winners were coiled at the mean
    if base_range20 > MAX_BASE_RANGE20:
        return None                       # not a coil at all
    tier = 'TIGHT' if base_range20 <= TIGHT_BASE_RANGE20 else 'WIDE'
    if sma200 is None or price <= sma200:
        return None                       # below the 200-day the same shape LOSES
    if pos_1y < MIN_POS_1Y:
        return None                       # launches come from the UPPER range
    if ath_room_pct < MIN_ATH_ROOM_PCT:
        return None                       # no headroom = no room to run
    if rsi is not None and rsi > MAX_RSI:
        return None                       # hot RSI = late, not early
    if ret_20d is not None and ret_20d > MAX_RET20_PCT:
        return None                       # already ran — the user is late again
    # Decliner DNA (Part 2): overbought + stretched + parabolic + climax volume.
    if ((rsi is not None and rsi > DECLINE_RSI)
            or dist_sma20 > DECLINE_EXT_SMA20
            or (ret_20d is not None and ret_20d > DECLINE_RET20)):
        return None
    # A loud RED bar is distribution, not a coil; a loud bar in general only
    # passes if it's the green ignition handled below.
    if rvol > MAX_QUIET_RVOL or (rvol >= 2.0 and not (up1 or last_green)):
        return None

    # =====================================================================
    # STAGE — the study's two-step play.
    # =====================================================================
    igniting = (rvol >= IGNITE_MIN_RVOL and day_pct >= IGNITE_MIN_DAY_PCT
                and (last_green or up1) and dist_sma20 <= IGNITE_MAX_EXT_SMA20)
    creeping = (not igniting and up1 and up2 and ret_2d >= CREEP_MIN_RET2
                and dist_sma20 <= CREEP_MAX_EXT_SMA20 and rvol < IGNITE_MIN_RVOL)
    if igniting:
        stage = 'IGNITING'
    elif creeping:
        stage = 'CREEPING'
    else:
        if rvol > QUIET_RVOL:
            return None                   # loud but not igniting = not a coil today
        stage = 'COILED'

    above_200 = True                      # gated above — always true past here
    sma200_up = sma200_20ago is not None and sma200 > sma200_20ago
    sma20_up = sma20_10ago is not None and sma20 > sma20_10ago
    sma50_up = sma50 is not None and sma50_10ago is not None and sma50 > sma50_10ago

    # =====================================================================
    # SCORE (0-100) — pure setup quality, weighted by what the PIT backtest
    # actually confirmed (tightness dominates; cheapness and huge headroom
    # tested as neutral/negative so they earn NOTHING). Stage is a badge,
    # not part of the score.
    # =====================================================================
    # THE trait — base tightness (0-30): <=8% range = full marks, 0 past the
    # TIGHT boundary (so tier-WIDE rows earn nothing here and rank below).
    base_pts = max(0.0, min(30.0, 30.0 * (TIGHT_BASE_RANGE20 - base_range20) / 4.0))
    # Coiled at the mean (0-15): tightest to the 20-day SMA scores highest.
    coil_pts = max(0.0, 15.0 * (1.0 - abs(dist_sma20) / COIL_MAX_DIST_SMA20))
    # Volatility contraction (0-10): 20d range half the 60d range = fully wound.
    contr_pts = max(0.0, min(10.0, 10.0 * (1.0 - contraction) / 0.55))
    # Position sweet spot (0-15): PIT says 0.55-0.75 wins, pinned AT the high
    # (>0.75) underperforms — full marks mid-upper, fading toward the extremes.
    if pos_1y <= 0.78:
        pos_pts = max(0.0, min(15.0, (pos_1y - MIN_POS_1Y) / 0.05 * 15.0))
    else:
        pos_pts = max(0.0, 15.0 - (pos_1y - 0.78) / 0.17 * 10.0)
    # Neutral RSI (0-10): full marks at 50, zero by +/-25.
    rsi_pts = max(0.0, 10.0 - abs((rsi if rsi is not None else 50.0) - 50.0) * 0.4)
    # Quiet (0-10): recent volume at/below normal (winners launched quiet).
    quiet_pts = max(0.0, min(10.0, 10.0 * (1.3 - rvol5) / 0.5))
    # Rising context (0-10): 20/50/200-day averages sloping up (drifting coil).
    slope_pts = (3.0 if sma20_up else 0.0) + (3.0 if sma50_up else 0.0) \
        + (4.0 if sma200_up else 0.0)

    score = (base_pts + coil_pts + contr_pts + pos_pts + rsi_pts
             + quiet_pts + slope_pts)
    score = int(round(max(0.0, min(100.0, score))))
    grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D'

    # ---- Plain-English reasons ----
    reasons = []
    if stage == 'IGNITING':
        reasons.append(f"IGNITION: volume just arrived ({rvol:.1f}x normal) on a "
                       f"{day_pct:+.1f}% day — the coil is starting to move")
    elif stage == 'CREEPING':
        reasons.append(f"Creeping up quietly: {ret_2d:+.1f}% over 2 days on normal volume "
                       "— the no-volume-tell launch type (aggressive)")
    if tier == 'TIGHT':
        reasons.append(f"Tight coil — 20-day range only {base_range20:.1f}% "
                       f"(the trait that halves downside risk in the backtest)"
                       + (f", wound to {contraction:.0%} of its 60-day range"
                          if contraction <= 0.6 else ""))
    else:
        reasons.append(f"Wider coil — 20-day range {base_range20:.1f}% (12-15% band: "
                       "same winner odds, but market-average downside — aggressive tier)")
    reasons.append(f"Sitting {dist_sma20:+.1f}% from the 20-day average — balanced, "
                   "not extended")
    reasons.append(f"Upper 1-yr range (pos {pos_1y:.2f}) with {ath_room_pct:.0f}% "
                   "headroom back to the old high")
    if rsi is not None:
        reasons.append(f"RSI {rsi:.0f} — " + ("neutral, not extended" if 40 <= rsi <= 60
                                              else "acceptable"))
    reasons.append("Above the 200-day average" + (" (rising)" if sma200_up else ""))
    if stage == 'COILED' and rvol5 <= 1.0:
        reasons.append(f"Quiet — recent volume {rvol5:.1f}x normal (winners launched quiet)")
    if ath_room_pct > 100:
        reasons.append("⚠ Very large headroom (>100%) — that class forward-tested "
                       "risky; treat as speculative")
    if action_dates:
        reasons.append("History back-adjusted for a corporate action on "
                       + ", ".join(action_dates))

    # Sparkline: the last ~6 months of closes, downsampled to <=60 points.
    seg = closes[-126:] if n >= 126 else closes
    if len(seg) > 60:
        idxs = np.unique(np.linspace(0, len(seg) - 1, 60).astype(int))
        seg = seg[idxs]
    spark = [round(float(x), 2) for x in seg]

    return {
        'ticker': ticker,
        'sector': sector,
        'price': _clean(price),
        'stage': stage,
        'tier': tier,
        'score': score,
        'grade': grade,
        'dist_sma20_pct': _clean(dist_sma20),
        'base_range20_pct': _clean(base_range20),
        'contraction': _clean(contraction),
        'pos_1y': _clean(pos_1y),
        'ath': _clean(ath),
        'ath_room_pct': _clean(ath_room_pct),
        'rsi': _clean(rsi),
        'rvol': _clean(rvol),
        'rvol5': _clean(rvol5),
        'day_pct': _clean(day_pct),
        'ret_5d': _clean(ret_5d),
        'ret_20d': _clean(ret_20d),
        'above_sma200': bool(above_200),
        'sma200_rising': bool(sma200_up),
        'sma20_rising': bool(sma20_up),
        'sma50_rising': bool(sma50_up),
        'avg_vol20': int(avg_vol20),
        'avg_turnover20': int(avg_turnover20),
        'adjusted_for_action': bool(action_dates),
        'action_dates': action_dates,
        'reasons': reasons,
        'spark': spark,
    }


def scan(engine, sector_map: dict | None = None) -> dict:
    """Scan the whole universe for coiled springs.

    Returns {as_of, universe, count, counts:{coiled,creeping,igniting}, stocks}.
    Sorted stage-first (IGNITING > CREEPING > COILED) then by setup score.
    """
    try:
        last = pd.read_sql_query(text("SELECT MAX(date) AS d FROM stock_data"), engine)
        as_of = str(last['d'].iloc[0])[:10] if not last.empty and last['d'].iloc[0] else None
    except Exception as e:
        logger.error(f"coil scan: latest-date lookup failed: {e}")
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if not as_of:
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

    try:
        cutoff = (datetime.strptime(as_of, '%Y-%m-%d')
                  - timedelta(days=CALENDAR_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    except Exception:
        cutoff = None

    q = ("SELECT ticker, date, open, high, low, close, volume FROM stock_data "
         + ("WHERE date >= :cutoff " if cutoff else "")
         + "ORDER BY ticker, date")
    params = {'cutoff': cutoff} if cutoff else {}
    try:
        allrows = pd.read_sql_query(text(q), engine, params=params)
    except Exception as e:
        logger.error(f"coil scan: bulk read failed: {e}")
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if allrows.empty:
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

    for col in ('open', 'high', 'low', 'close', 'volume'):
        allrows[col] = pd.to_numeric(allrows[col], errors='coerce')
    allrows = allrows.dropna(subset=['close', 'high', 'low'])

    udates = sorted(pd.unique(allrows['date'].astype(str).str[:10]))
    stale_cutoff = (udates[-MAX_STALE_TRADING_DAYS] if len(udates) >= MAX_STALE_TRADING_DAYS
                    else (udates[0] if udates else None))

    if sector_map is None:
        try:
            sdf = pd.read_sql_query(
                text("SELECT ticker, sector FROM fundamentals WHERE sector IS NOT NULL"), engine)
            sector_map = dict(zip(sdf['ticker'], sdf['sector']))
        except Exception:
            sector_map = {}

    stocks = []
    universe = 0
    for ticker, g in allrows.groupby('ticker'):
        universe += 1
        try:
            row = _analyze_one(str(ticker), g, sector_map.get(str(ticker)),
                               stale_cutoff=stale_cutoff)
            if row:
                stocks.append(row)
        except Exception as e:
            logger.debug(f"coil scan: {ticker} failed: {e}")
            continue

    # TIGHT quality first (the PIT-validated tier), then the act-now stage,
    # then setup score.
    stage_rank = {'IGNITING': 2, 'CREEPING': 1, 'COILED': 0}
    stocks.sort(key=lambda x: (x['tier'] == 'TIGHT',
                               stage_rank.get(x['stage'], 0), x['score']), reverse=True)
    counts = {
        'igniting': sum(1 for s in stocks if s['stage'] == 'IGNITING'),
        'creeping': sum(1 for s in stocks if s['stage'] == 'CREEPING'),
        'coiled': sum(1 for s in stocks if s['stage'] == 'COILED'),
        'tight': sum(1 for s in stocks if s['tier'] == 'TIGHT'),
        'wide': sum(1 for s in stocks if s['tier'] == 'WIDE'),
    }
    return {'as_of': as_of, 'universe': universe, 'count': len(stocks),
            'counts': counts, 'stocks': stocks}
