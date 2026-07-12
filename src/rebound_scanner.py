"""Rebound scanner — "fallen angels that are curving back up".

Finds stocks that (1) fell a long way from a prior high, (2) carved out a
bottom / base over time, and (3) are NOW turning back up. The canonical shape
the user described: a name that was ~120, ground down to a 50-60 base over
several months, and whose most recent bars are ticking higher (61, 62, ...).

This is a WATCHLIST screen, not a buy signal. A stock curling off a base can
resume its downtrend at any time — the point is to surface turns early so they
can be tracked (and then judged on the full manual analysis, which the UI opens
in a modal). Nothing here asserts a validated edge; it is a structural filter.

Design goals:
  * Pure structural detection from daily OHLCV — no dependency on the quant
    signals_today pipeline, so it works for every ticker with enough history.
  * One bulk read of recent history, grouped in pandas (fast for ~400 tickers).
  * Every row carries plain-English reasons + a 0-100 score + A-D grade so the
    list is a decision aid, not a data dump.

All thresholds are module constants so they are easy to tune.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---- Tunable thresholds ------------------------------------------------- #
LOOKBACK_BARS = 252          # ~1 trading year of context for the peak
CALENDAR_LOOKBACK_DAYS = 400 # bulk-read window (calendar) to cover LOOKBACK_BARS
MIN_BARS = 80                # need enough history to trust a peak->trough->turn
MIN_DRAWDOWN_PCT = 25.0      # peak -> trough fall must be at least this deep
MIN_STILL_DOWN_PCT = 15.0    # price must still be at least this far below the peak
OFF_LOW_MIN_PCT = 3.0        # must have bounced at least this much off the low
OFF_LOW_MAX_PCT = 45.0       # ...but not already fully recovered (stay early)
MIN_DAYS_SINCE_TROUGH = 4    # the low must be behind us (a turn, not a fresh low)
MIN_FALL_SPAN_BARS = 18      # the decline took time (excludes 1-day crash bounces)
MIN_PRICE = 5.0              # avoid untradeable penny names
MIN_AVG_VOL20 = 20000        # basic liquidity floor (shares/day)


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = gain[-period:].mean()
    al = loss[-period:].mean()
    if al == 0:
        return 100.0
    rs = ag / al
    return float(100 - (100 / (1 + rs)))


def _sma(a: np.ndarray, n: int) -> float | None:
    if len(a) < n:
        return None
    return float(a[-n:].mean())


def _sma_ago(a: np.ndarray, n: int, ago: int) -> float | None:
    """SMA(n) computed `ago` bars in the past."""
    if len(a) < n + ago:
        return None
    seg = a[-(n + ago):len(a) - ago]
    return float(seg.mean())


def _clean(f):
    if f is None:
        return None
    try:
        f = float(f)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else round(f, 3)


def _analyze_one(ticker: str, df: pd.DataFrame, sector: str | None) -> dict | None:
    """Return a rebound row for `ticker`, or None if it doesn't qualify."""
    df = df[df['close'] > 0].sort_values('date')
    if len(df) < MIN_BARS:
        return None
    # Keep at most the lookback window (most recent).
    df = df.tail(LOOKBACK_BARS).reset_index(drop=True)

    closes = df['close'].to_numpy(dtype=float)
    highs = df['high'].to_numpy(dtype=float)
    lows = df['low'].to_numpy(dtype=float)
    vols = df['volume'].to_numpy(dtype=float)
    dates = df['date'].astype(str).str[:10].tolist()

    price = float(closes[-1])
    if price < MIN_PRICE:
        return None

    avg_vol20 = float(vols[-20:].mean()) if len(vols) >= 20 else float(vols.mean())
    if avg_vol20 < MIN_AVG_VOL20:
        return None

    # ---- Peak -> trough -> now geometry ----
    peak_i = int(np.argmax(highs))
    peak = float(highs[peak_i])
    # Trough is the lowest low AFTER the peak (the base we're recovering from).
    if peak_i >= len(lows) - 1:
        return None  # peak is the last bar → nothing has fallen yet
    post = lows[peak_i + 1:]
    trough_rel = int(np.argmin(post))
    trough_i = peak_i + 1 + trough_rel
    trough = float(lows[trough_i])
    if trough <= 0 or peak <= 0:
        return None

    drawdown_pct = (peak - trough) / peak * 100.0
    if drawdown_pct < MIN_DRAWDOWN_PCT:
        return None

    fall_span = trough_i - peak_i
    if fall_span < MIN_FALL_SPAN_BARS:
        return None  # a fast crash + bounce is a different animal (dead-cat)

    days_since_trough = (len(closes) - 1) - trough_i
    if days_since_trough < MIN_DAYS_SINCE_TROUGH:
        return None  # still making fresh lows — no turn yet

    off_low_pct = (price - trough) / trough * 100.0
    if off_low_pct < OFF_LOW_MIN_PCT or off_low_pct > OFF_LOW_MAX_PCT:
        return None

    from_peak_pct = (price - peak) / peak * 100.0  # negative
    if from_peak_pct > -MIN_STILL_DOWN_PCT:
        return None  # already recovered most of the fall → not what we want

    # ---- "Curving up" confirmation ----
    sma10 = _sma(closes, 10)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma10_5ago = _sma_ago(closes, 10, 5)
    sma20_10ago = _sma_ago(closes, 20, 10)

    close_5ago = float(closes[-6]) if len(closes) >= 6 else None
    close_10ago = float(closes[-11]) if len(closes) >= 11 else None
    ret_5d = (price / close_5ago - 1) * 100 if close_5ago else None
    ret_10d = (price / close_10ago - 1) * 100 if close_10ago else None

    # 20-day range position (0 = at 20d low, 1 = at 20d high).
    win = closes[-20:] if len(closes) >= 20 else closes
    lo20, hi20 = float(win.min()), float(win.max())
    range_pos = (price - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5

    c_above_sma20 = sma20 is not None and price > sma20
    c_sma10_up = sma10 is not None and sma10_5ago is not None and sma10 > sma10_5ago
    c_sma20_up = sma20 is not None and sma20_10ago is not None and sma20 > sma20_10ago
    c_mom10 = ret_10d is not None and ret_10d > 0
    c_progress = (close_5ago is not None and price > close_5ago) and \
                 (close_10ago is not None and price > close_10ago)
    c_reclaim = range_pos >= 0.55

    ma_turning = c_above_sma20 or c_sma10_up
    curl_score = sum([c_above_sma20, c_sma10_up, c_sma20_up, c_mom10, c_progress, c_reclaim])
    if not ma_turning or curl_score < 3:
        return None

    # ---- Volume pick-up (accumulation returning on the turn) ----
    vol_recent5 = float(vols[-5:].mean()) if len(vols) >= 5 else avg_vol20
    base_vol = float(vols[-25:-5].mean()) if len(vols) >= 25 else avg_vol20
    vol_pickup = vol_recent5 / base_vol if base_vol > 0 else 1.0
    rvol = float(vols[-1]) / avg_vol20 if avg_vol20 > 0 else 1.0

    rsi = _rsi(closes)

    # ---- Score 0-100 ----
    # MA reclaim + slope (0-30)
    ma_pts = (10 if c_above_sma20 else 0) + (10 if c_sma10_up else 0) + (10 if c_sma20_up else 0)
    # Momentum (0-20)
    mom_pts = 0.0
    if ret_10d is not None:
        mom_pts += max(0.0, min(12.0, ret_10d * 1.2))
    if ret_5d is not None:
        mom_pts += max(0.0, min(8.0, ret_5d * 1.2))
    # Off-low positioning (0-20): reward catching it early (sweet spot ~6-22%).
    if off_low_pct <= 22:
        offlow_pts = 20.0 * min(1.0, off_low_pct / 10.0) if off_low_pct < 10 else 20.0
    else:
        offlow_pts = max(0.0, 20.0 - (off_low_pct - 22) * 0.8)
    # Volume pick-up (0-15)
    vol_pts = max(0.0, min(15.0, (vol_pickup - 1.0) * 20.0))
    # Base quality (0-15): a longer base + a decent (not catastrophic) fall.
    base_pts = min(10.0, days_since_trough / 4.0) + (5.0 if 25 <= drawdown_pct <= 70 else 2.0)

    score = ma_pts + mom_pts + offlow_pts + vol_pts + base_pts
    score = int(round(max(0.0, min(100.0, score))))
    grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D'

    # ---- Plain-English reasons ----
    reasons = []
    reasons.append(
        f"Fell {drawdown_pct:.0f}% from {peak:.1f} ({dates[peak_i]}) to {trough:.1f} "
        f"({dates[trough_i]})")
    reasons.append(f"Now {off_low_pct:.0f}% off the low, still {abs(from_peak_pct):.0f}% below the old high")
    if c_above_sma20:
        reasons.append("Reclaimed the 20-day average")
    if c_sma10_up:
        reasons.append("10-day average turning up")
    if c_sma20_up:
        reasons.append("20-day average slope turned positive")
    if ret_10d is not None and ret_10d > 0:
        reasons.append(f"+{ret_10d:.0f}% over the last 10 sessions")
    if vol_pickup >= 1.3:
        reasons.append(f"Volume picking up ({vol_pickup:.1f}x its base)")
    if rsi is not None:
        reasons.append(f"RSI {rsi:.0f}")

    # Recent price path for a row sparkline (last ~40 closes).
    spark = [round(float(x), 2) for x in closes[-40:]]

    return {
        'ticker': ticker,
        'sector': sector,
        'price': _clean(price),
        'peak': _clean(peak),
        'peak_date': dates[peak_i],
        'trough': _clean(trough),
        'trough_date': dates[trough_i],
        'drawdown_pct': _clean(drawdown_pct),
        'off_low_pct': _clean(off_low_pct),
        'from_peak_pct': _clean(from_peak_pct),
        'recovery_room_pct': _clean((peak - price) / price * 100.0),  # upside back to old high
        'days_since_trough': int(days_since_trough),
        'fall_span_bars': int(fall_span),
        'ret_5d': _clean(ret_5d),
        'ret_10d': _clean(ret_10d),
        'sma20': _clean(sma20),
        'sma50': _clean(sma50),
        'above_sma20': bool(c_above_sma20),
        'sma20_rising': bool(c_sma20_up),
        'range_pos': _clean(range_pos),
        'rsi': _clean(rsi),
        'avg_vol20': int(avg_vol20),
        'rvol': _clean(rvol),
        'vol_pickup': _clean(vol_pickup),
        'curl_score': int(curl_score),
        'score': score,
        'grade': grade,
        'reasons': reasons,
        'spark': spark,
    }


def scan(engine, sector_map: dict | None = None) -> dict:
    """Scan the whole universe. Returns {as_of, universe, count, stocks:[...]}.

    `sector_map` optionally maps ticker -> sector (from fundamentals); if None
    it is loaded here.
    """
    # Latest trading date, then a bulk read of the recent window.
    try:
        last = pd.read_sql_query(text("SELECT MAX(date) AS d FROM stock_data"), engine)
        as_of = str(last['d'].iloc[0])[:10] if not last.empty and last['d'].iloc[0] else None
    except Exception as e:
        logger.error(f"rebound scan: latest-date lookup failed: {e}")
        return {'as_of': None, 'universe': 0, 'count': 0, 'stocks': []}
    if not as_of:
        return {'as_of': None, 'universe': 0, 'count': 0, 'stocks': []}

    try:
        cutoff = (datetime.strptime(as_of, '%Y-%m-%d') - timedelta(days=CALENDAR_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    except Exception:
        cutoff = None

    q = ("SELECT ticker, date, open, high, low, close, volume FROM stock_data "
         + ("WHERE date >= :cutoff " if cutoff else "")
         + "ORDER BY ticker, date")
    params = {'cutoff': cutoff} if cutoff else {}
    try:
        allrows = pd.read_sql_query(text(q), engine, params=params)
    except Exception as e:
        logger.error(f"rebound scan: bulk read failed: {e}")
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'stocks': []}
    if allrows.empty:
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'stocks': []}

    for col in ('open', 'high', 'low', 'close', 'volume'):
        allrows[col] = pd.to_numeric(allrows[col], errors='coerce')
    allrows = allrows.dropna(subset=['close', 'high', 'low'])

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
            row = _analyze_one(ticker, g, sector_map.get(ticker))
            if row:
                stocks.append(row)
        except Exception as e:
            logger.debug(f"rebound scan: {ticker} failed: {e}")
            continue

    stocks.sort(key=lambda x: (x['score'], -abs(x['from_peak_pct'] or 0)), reverse=True)
    return {'as_of': as_of, 'universe': universe, 'count': len(stocks), 'stocks': stocks}
