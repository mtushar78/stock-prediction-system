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
MIN_BASE_AGE_BARS = 30       # ...OR a fast crash that has since based this long
MIN_PRICE = 5.0              # avoid untradeable penny names
MIN_AVG_VOL20 = 5000         # sanity floor on shares/day (real filter is turnover)
MIN_AVG_TURNOVER_BDT = 500_000  # traded VALUE floor — shares alone is meaningless
MAX_STALE_TRADING_DAYS = 5   # must have traded within N of the market's last session
ADJ_DROP_PCT = 12.0          # 1-day drop beyond this = corporate action, not selling
                             # (DSE circuit breaker caps genuine moves near +/-10%)
# "EARLY" (aggressive) turns — still AT the base but just ticked up over the last
# 1-2 sessions, before the averages have turned. Looser than the established
# curl so the watchlist also catches turns the moment they start. Lower
# conviction by design → tagged stage='EARLY' and sorted below the mature ones.
EARLY_OFF_LOW_MAX = 30.0     # still in the lower half of the recovery (near the base)
EARLY_MIN_2D_POP = 2.0       # a >=2% two-day pop counts as a fresh turn
EARLY_MIN_5D_POP = 3.0       # ...or a >=3% five-day bounce off the base

# "FRESH" (most aggressive) turns — the short-term dip-and-turn the user asked
# for: a name that pulled back over the last few sessions, printed a low in the
# LAST 1-5 days, and is NOW putting in green candles right off that low. It does
# NOT need the deep 25%-from-a-yearly-high "fallen angel" structure — it is a
# recent, tactical bounce. Deliberately the loosest bucket, tagged stage='FRESH'
# so it's never confused with a mature turn, and it's the one that surfaces
# stocks the moment they turn (before they've "already gone high").
FRESH_WIN = 30               # window (bars) to locate the recent swing high the dip fell from
FRESH_MIN_DIP_PCT = 6.0      # recent high -> recent low must be a real dip (not noise)
FRESH_MAX_DAYS_SINCE_LOW = 5 # the low must be within the last 5 sessions (fresh)
FRESH_MIN_OFF_LOW = 1.5      # must have actually ticked up off the low...
FRESH_MAX_OFF_LOW = 12.0     # ...but still be near it (not already run away)


def _back_adjust(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                 drop_pct: float = ADJ_DROP_PCT):
    """Back-adjust prices for corporate actions (bonus/rights ex-dates).

    On DSE the circuit breaker caps a genuine one-day move near +/-10%, so a
    single-day close-to-close drop far beyond that is almost always an ex-date
    price adjustment, not real selling. Left alone, that jump inflates the
    peak->trough drawdown and pollutes the momentum reads. We scale every bar
    BEFORE each such gap by the gap ratio (standard price back-adjustment), which
    chains cleanly across multiple actions and leaves the latest bar untouched.

    Returns (closes_adj, highs_adj, lows_adj, gap_indices).
    """
    n = len(closes)
    factor = np.ones(n)
    gaps: list[int] = []
    thresh = 1.0 - drop_pct / 100.0
    for i in range(1, n):
        prev = closes[i - 1]
        if prev > 0 and closes[i] / prev < thresh:
            factor[:i] *= (closes[i] / prev)
            gaps.append(i)
    return closes * factor, highs * factor, lows * factor, gaps


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    """Wilder's RSI (EWM smoothing) — matches the RSI shown in the full analysis
    modal (src/analyzer.py), so the row and the drill-down agree."""
    if len(closes) < period + 1:
        return None
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = pd.Series(gain).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    al = pd.Series(loss).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
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


def _first_target(highs: np.ndarray, price: float, story_low: float,
                  story_high: float) -> float:
    """A concrete first upside target for the rebound.

    A recovering price climbs back into the resistance it fell from. The most
    honest "target" is therefore the nearest overhead swing high (a prior ceiling
    the price must reclaim), and failing that a Fibonacci retracement of the
    decline. Always capped at the old high (the ultimate recovery room) and kept
    at least a little above the current price so it is a real objective.
    """
    price = float(price); story_low = float(story_low); story_high = float(story_high)
    # Swing highs = local maxima (a bar topping its two neighbours each side).
    swings = []
    for i in range(2, len(highs) - 2):
        h = highs[i]
        if h >= highs[i - 1] and h >= highs[i - 2] and h >= highs[i + 1] and h >= highs[i + 2]:
            swings.append(float(h))
    res_above = sorted(r for r in swings if r > price * 1.02)
    fib382 = story_low + 0.382 * (story_high - story_low)
    fib50 = story_low + 0.5 * (story_high - story_low)
    target = res_above[0] if res_above else None
    # Prefer a genuine overhead level, but never one below the first retracement;
    # if there's nothing sensible above, use the retracement itself.
    if target is None or target < fib382:
        target = fib382 if fib382 > price * 1.015 else fib50
    target = min(target, story_high)
    if target <= price * 1.01:
        target = min(story_high, price * 1.05)
    return target


def _analyze_one(ticker: str, df: pd.DataFrame, sector: str | None,
                 stale_cutoff: str | None = None,
                 reversal_set: set | None = None) -> dict | None:
    """Return a rebound row for `ticker`, or None if it doesn't qualify."""
    df = df[df['close'] > 0].sort_values('date')
    if len(df) < MIN_BARS:
        return None
    # Keep at most the lookback window (most recent).
    df = df.tail(LOOKBACK_BARS).reset_index(drop=True)

    closes_raw = df['close'].to_numpy(dtype=float)
    opens_raw = df['open'].to_numpy(dtype=float)
    highs_raw = df['high'].to_numpy(dtype=float)
    lows_raw = df['low'].to_numpy(dtype=float)
    vols = df['volume'].to_numpy(dtype=float)
    dates = df['date'].astype(str).str[:10].tolist()

    # ---- Freshness: don't surface a stale ticker as a live "turn" ----
    # It must have traded within the last few market sessions, else its "turn"
    # is months old (e.g. a suspended/illiquid name last printed in December).
    if stale_cutoff is not None and dates[-1] < stale_cutoff:
        return None

    # ---- Data hygiene: DSE stores some bars with close>0 but low/high<=0 ----
    # A single zero low creates a false trough of 0 and silently discards the
    # whole ticker (this alone was hiding the majority of valid candidates).
    lows_raw = np.where(lows_raw <= 0, closes_raw, lows_raw)
    highs_raw = np.where(highs_raw <= 0, closes_raw, highs_raw)
    opens_raw = np.where((opens_raw <= 0) | np.isnan(opens_raw), closes_raw, opens_raw)

    price = float(closes_raw[-1])
    if price < MIN_PRICE:
        return None

    # ---- Liquidity by traded VALUE (20k shares of a 6tk stock is untradeable) ----
    turnover = closes_raw * vols
    avg_turnover20 = float(turnover[-20:].mean()) if len(turnover) >= 20 else float(turnover.mean())
    avg_vol20 = float(vols[-20:].mean()) if len(vols) >= 20 else float(vols.mean())
    if avg_turnover20 < MIN_AVG_TURNOVER_BDT or avg_vol20 < MIN_AVG_VOL20:
        return None

    # ---- Back-adjust for corporate actions before measuring the fall ----
    closes, highs, lows, gap_idx = _back_adjust(closes_raw, highs_raw, lows_raw)
    # `price` stays the raw last close (its adjustment factor is always 1.0).
    action_dates = [dates[i] for i in gap_idx]
    n = len(closes)

    # ---- Candles / short-term turn primitives (used by every stage) ----
    up1 = closes[-1] > closes[-2] if n >= 2 else False
    up2 = closes[-2] > closes[-3] if n >= 3 else False
    # The latest bar's adjustment factor is always 1.0, so raw open/close is safe.
    last_green = bool(closes_raw[-1] > opens_raw[-1])
    ret_2d = (price / float(closes[-3]) - 1) * 100.0 if n >= 3 else None

    # =====================================================================
    # DEEP "fallen angel" geometry — peak -> trough -> now (on adjusted prices).
    # This is the classic rebound: a big fall from a yearly high, a base, a curl.
    # We compute it but DON'T early-return on its gates any more, because a stock
    # can still qualify for the looser, short-term FRESH bucket below.
    # =====================================================================
    deep_ok = False
    d_peak_i = int(np.argmax(highs))
    d_peak = float(highs[d_peak_i])
    d_trough_i = d_trough = d_drawdown = d_fall_span = d_days_since = None
    d_off_low = d_from_peak = None
    if d_peak_i < n - 1 and d_peak > 0:
        post = lows[d_peak_i + 1:]
        d_trough_i = d_peak_i + 1 + int(np.argmin(post))
        d_trough = float(lows[d_trough_i])
        if d_trough > 0:
            d_drawdown = (d_peak - d_trough) / d_peak * 100.0
            d_fall_span = d_trough_i - d_peak_i
            d_days_since = (n - 1) - d_trough_i
            d_off_low = (price - d_trough) / d_trough * 100.0
            d_from_peak = (price - d_peak) / d_peak * 100.0
            deep_ok = (
                d_drawdown >= MIN_DRAWDOWN_PCT
                and not (d_fall_span < MIN_FALL_SPAN_BARS and d_days_since < MIN_BASE_AGE_BARS)
                and d_days_since >= 1
                and d_from_peak <= -MIN_STILL_DOWN_PCT
                and d_off_low <= OFF_LOW_MAX_PCT
            )

    # ---- "Curving up" confirmation (moving averages / momentum) ----
    sma10 = _sma(closes, 10)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma10_5ago = _sma_ago(closes, 10, 5)
    sma20_10ago = _sma_ago(closes, 20, 10)

    close_5ago = float(closes[-6]) if n >= 6 else None
    close_10ago = float(closes[-11]) if n >= 11 else None
    ret_5d = (price / close_5ago - 1) * 100 if close_5ago else None
    ret_10d = (price / close_10ago - 1) * 100 if close_10ago else None

    # 20-day range position (0 = at 20d low, 1 = at 20d high).
    win = closes[-20:] if n >= 20 else closes
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

    early_signals = sum([
        (up1 and up2),
        (ret_2d is not None and ret_2d >= EARLY_MIN_2D_POP),
        (ret_5d is not None and ret_5d >= EARLY_MIN_5D_POP),
        c_sma10_up,
        c_above_sma20,
        (range_pos >= 0.5),
    ])

    # ---- Deep-track staging (only if the fallen-angel structure is present) ----
    established = early = False
    if deep_ok:
        established = (d_days_since >= MIN_DAYS_SINCE_TROUGH
                       and d_off_low >= OFF_LOW_MIN_PCT
                       and ma_turning and curl_score >= 3)
        early = (not established) and d_off_low <= EARLY_OFF_LOW_MAX and early_signals >= 1

    # =====================================================================
    # FRESH short-term dip-and-turn — the aggressive bucket the user wants:
    # pulled back over the last few sessions, printed a low in the LAST 1-5 days,
    # and is putting in green candles right off that low. No deep drawdown needed.
    # =====================================================================
    fresh_ok = False
    fr_high_i = fr_low_i = fr_high = fr_low = fr_dip = fr_off_low = fr_days_since = fr_from_high = None
    w = min(FRESH_WIN, n)
    if w >= 6:
        seg_h = highs[-w:]
        rh_rel = int(np.argmax(seg_h))
        fr_high_i = n - w + rh_rel
        fr_high = float(highs[fr_high_i])
        if fr_high_i < n - 1 and fr_high > 0:
            post_l = lows[fr_high_i + 1:]
            fr_low_i = fr_high_i + 1 + int(np.argmin(post_l))
            fr_low = float(lows[fr_low_i])
            if fr_low > 0:
                fr_dip = (fr_high - fr_low) / fr_high * 100.0
                fr_off_low = (price - fr_low) / fr_low * 100.0
                fr_days_since = (n - 1) - fr_low_i
                fr_from_high = (price - fr_high) / fr_high * 100.0
                fresh_ok = (
                    0 <= fr_days_since <= FRESH_MAX_DAYS_SINCE_LOW
                    and fr_dip >= FRESH_MIN_DIP_PCT
                    and FRESH_MIN_OFF_LOW <= fr_off_low <= FRESH_MAX_OFF_LOW
                    and price < fr_high * 0.995        # hasn't recovered the whole dip yet
                    and (last_green or up1)            # actually turning up now
                )

    # ---- Pick ONE stage (deep turns take precedence; FRESH is the fallback) ----
    if established:
        stage = 'TURNING'
    elif early:
        stage = 'EARLY'
    elif fresh_ok:
        stage = 'FRESH'
    else:
        return None

    # ---- Resolve the "story" (peak -> trough -> now) from the chosen stage ----
    if stage == 'FRESH':
        peak_i, peak = fr_high_i, fr_high
        trough_i, trough = fr_low_i, fr_low
        drawdown_pct, off_low_pct = fr_dip, fr_off_low
        from_peak_pct, days_since_trough = fr_from_high, fr_days_since
        fall_span = trough_i - peak_i
    else:
        peak_i, peak = d_peak_i, d_peak
        trough_i, trough = d_trough_i, d_trough
        drawdown_pct, off_low_pct = d_drawdown, d_off_low
        from_peak_pct, days_since_trough = d_from_peak, d_days_since
        fall_span = d_fall_span

    # ---- First upside target (issue: show a concrete objective) ----
    target = _first_target(highs, price, trough, peak)
    target_pct = (target - price) / price * 100.0 if price > 0 else None

    # ---- Volume pick-up (accumulation returning on the turn) ----
    vol_recent5 = float(vols[-5:].mean()) if n >= 5 else avg_vol20
    base_vol = float(vols[-25:-5].mean()) if n >= 25 else avg_vol20
    vol_pickup = vol_recent5 / base_vol if base_vol > 0 else 1.0
    rvol = float(vols[-1]) / avg_vol20 if avg_vol20 > 0 else 1.0

    rsi = _rsi(closes)

    # ---- Score 0-100 (rebalanced so FRESHNESS + a real green turn win, and
    #      names that have "already gone high" off their low sink) ----
    # MA reclaim + slope (0-25)
    ma_pts = (8 if c_above_sma20 else 0) + (9 if c_sma10_up else 0) + (8 if c_sma20_up else 0)
    # Momentum (0-15)
    mom_pts = 0.0
    if ret_10d is not None:
        mom_pts += max(0.0, min(9.0, ret_10d * 1.0))
    if ret_5d is not None:
        mom_pts += max(0.0, min(6.0, ret_5d * 1.0))
    # Off-low positioning (0-20): peak reward ~6% off the low; steep penalty once
    # it has run away (>25% off the low scores ~0 — that's "already gone high").
    if off_low_pct <= 12:
        offlow_pts = 20.0 - abs(off_low_pct - 6.0) * 0.8
    elif off_low_pct <= 25:
        offlow_pts = 15.0 - (off_low_pct - 12.0) * 1.0
    else:
        offlow_pts = max(0.0, 2.0 - (off_low_pct - 25.0) * 0.2)
    offlow_pts = max(0.0, offlow_pts)
    # The turn itself (0-20): green candle + up days + a two-day pop right now.
    turn_pts = (8.0 if last_green else 0.0) + (4.0 if up1 else 0.0) \
        + (4.0 if (up1 and up2) else 0.0) \
        + (4.0 if (ret_2d is not None and ret_2d >= EARLY_MIN_2D_POP) else 0.0)
    turn_pts = min(20.0, turn_pts)
    # Volume pick-up (0-12)
    vol_pts = max(0.0, min(12.0, (vol_pickup - 1.0) * 20.0))
    # Base quality (0-8): a decent (not catastrophic) fall behind the turn.
    base_pts = min(6.0, days_since_trough / 6.0) + (2.0 if 12 <= drawdown_pct <= 70 else 0.0)

    score = ma_pts + mom_pts + offlow_pts + turn_pts + vol_pts + base_pts
    score = int(round(max(0.0, min(100.0, score))))
    grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D'

    # ---- Plain-English reasons ----
    reasons = []
    if stage == 'FRESH':
        reasons.append(
            f"Short-term dip: −{drawdown_pct:.0f}% from {peak:.1f} ({dates[peak_i]}) "
            f"to {trough:.1f} ({dates[trough_i]})")
        turnbits = []
        if last_green:
            turnbits.append("green candle")
        if up1 and up2:
            turnbits.append("2 up days")
        elif up1:
            turnbits.append("up today")
        if ret_2d is not None and ret_2d >= EARLY_MIN_2D_POP:
            turnbits.append(f"+{ret_2d:.0f}% 2d")
        reasons.append(
            f"Low was {days_since_trough}d ago, now {off_low_pct:.0f}% back up — turning: "
            + ", ".join(turnbits))
    else:
        reasons.append(
            f"Fell {drawdown_pct:.0f}% from {peak:.1f} ({dates[peak_i]}) to {trough:.1f} "
            f"({dates[trough_i]})")
        reasons.append(f"Now {off_low_pct:.0f}% off the low, still {abs(from_peak_pct):.0f}% below the old high")
        if stage == 'EARLY':
            bits = []
            if up1 and up2:
                bits.append("2 up days")
            if ret_2d is not None and ret_2d >= EARLY_MIN_2D_POP:
                bits.append(f"+{ret_2d:.0f}% 2d")
            elif ret_5d is not None and ret_5d >= EARLY_MIN_5D_POP:
                bits.append(f"+{ret_5d:.0f}% 5d")
            if c_sma10_up:
                bits.append("10-day avg curling up")
            if c_above_sma20:
                bits.append("back above the 20-day")
            reasons.append("Early/aggressive — at the base, first signs of turning"
                           + (" (" + ", ".join(bits) + ")" if bits else ""))
    if target_pct is not None:
        reasons.append(f"First target ~{target:.1f} (+{target_pct:.0f}% from here)")
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
    if action_dates:
        reasons.append(
            "Fall adjusted for a corporate action on " + ", ".join(action_dates))

    is_reversal = bool(reversal_set and ticker in reversal_set)
    if is_reversal:
        reasons.insert(0, "Also firing on the validated reversal signal — strongest overlap")

    # Sparkline covers the whole peak->base->turn story (down-sampled to ~60
    # points) so the base low is always in-frame; spark_low_idx marks it.
    seg = closes[peak_i:]
    if len(seg) >= 2:
        if len(seg) > 60:
            idxs = np.unique(np.linspace(peak_i, len(closes) - 1, 60).astype(int))
        else:
            idxs = np.arange(peak_i, len(closes))
        vals = closes[idxs]
        spark = [round(float(x), 2) for x in vals]
        spark_low_idx = int(np.argmin(vals))
    else:
        spark = [round(float(x), 2) for x in closes[-40:]]
        spark_low_idx = int(np.argmin(closes[-40:])) if len(closes) else 0

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
        'target': _clean(target),                # first concrete upside objective
        'target_pct': _clean(target_pct),        # upside from here to that target
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
        'stage': stage,
        'score': score,
        'grade': grade,
        'is_reversal': is_reversal,
        'adjusted_for_action': bool(action_dates),
        'action_dates': action_dates,
        'reasons': reasons,
        'spark': spark,
        'spark_low_idx': spark_low_idx,
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

    # Freshness cutoff: the market date MAX_STALE_TRADING_DAYS sessions back. A
    # ticker whose last bar is older than this hasn't traded recently and its
    # "turn" would be stale — reject it in _analyze_one.
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

    # Cross-reference the validated v10 reversal signal: a rebound that ALSO
    # fires a reversal is a far stronger candidate than the structural shape
    # alone (reversal is the only net-of-cost edge measured on DSE).
    reversal_set: set = set()
    try:
        rcols = pd.read_sql_query(text("SELECT * FROM signals_today LIMIT 1"), engine).columns.tolist()
        if 'reversal_signal' in rcols:
            rdf = pd.read_sql_query(
                text("SELECT ticker FROM signals_today WHERE reversal_signal = 1"), engine)
            reversal_set = set(rdf['ticker'].astype(str).tolist())
    except Exception:
        reversal_set = set()

    stocks = []
    universe = 0
    for ticker, g in allrows.groupby('ticker'):
        universe += 1
        try:
            row = _analyze_one(ticker, g, sector_map.get(ticker),
                               stale_cutoff=stale_cutoff, reversal_set=reversal_set)
            if row:
                stocks.append(row)
        except Exception as e:
            logger.debug(f"rebound scan: {ticker} failed: {e}")
            continue

    # Rank purely by the (rebalanced) quality score, then reversal overlap, then
    # earliest (smallest off-low). The score now rewards a fresh green turn right
    # off the low and penalises names that have "already gone high", so the top
    # of the list is the aggressive, just-turning candidates the user wants — not
    # the mature setups that have already run. Stage is a badge, not a sort gate.
    stocks.sort(key=lambda x: (x['score'], int(x['is_reversal']), x['curl_score'],
                               -(x['off_low_pct'] or 0.0)),
                reverse=True)
    turning = sum(1 for s in stocks if s.get('stage') == 'TURNING')
    fresh = sum(1 for s in stocks if s.get('stage') == 'FRESH')
    early = sum(1 for s in stocks if s.get('stage') == 'EARLY')
    return {'as_of': as_of, 'universe': universe, 'count': len(stocks), 'fresh': fresh,
            'turning': turning, 'early': early, 'stocks': stocks}
