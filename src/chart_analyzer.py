"""
Chart-pattern analyzer — a SECOND, independent engine.

This module is intentionally separate from `src/analyzer.py`. It does NOT
share scoring math, BUY thresholds, or storage with the quant scorer.
Its job is to apply classical Japanese candlestick analysis to the SAME
OHLCV history and produce a parallel set of signals that can be used as
cross-confirmation.

What it detects (8 patterns):
    Reversal:
      1. Bullish Engulfing
      2. Hammer (with location guard)
      3. Inverted Hammer
      4. Morning Star (3-candle)
      5. Piercing Line
      6. Bullish Harami
    Continuation:
      7. Three White Soldiers
      8. Bullish Marubozu

Why these 8: each has documented edge in classical TA literature, each
detects a different market psychology, and together they cover both
reversal (buy-the-dip) and continuation (ride-the-trend) setups.

Scoring philosophy:
    Each pattern has a base strength (0-100).
    Context multipliers adjust the strength:
      - Trend alignment        — reversal in downtrend is strong; in uptrend it's a dip
      - Support/resistance     — patterns at support are gold; near resistance they fail
      - Volume confirmation    — pattern + above-avg volume is what pros wait for
      - SMA200 position        — long-term uptrend boost; downtrend penalty

    The overall ticker score sums final per-pattern strengths (clipped to
    100), then maps to confidence tiers:
      >= 80 with >=2 patterns → HIGH
      >= 50                   → MEDIUM
      >= 25                   → LOW
      else                    → NONE

This engine does NOT produce BUY/SELL directly. It produces a
bullish/bearish bias with a confidence level. The human (or a future
agreement-tab) decides whether to act.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz

from src.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

BANGLADESH_TZ = pytz.timezone('Asia/Dhaka')

# How many days of history are required before any pattern can be detected.
# 30 is enough for support/resistance + 20-day RVOL + recent trend.
MIN_HISTORY_DAYS = 30

# Candle-shape micro-thresholds.
MIN_BODY_PCT = 0.001   # 0.1% of price — anything below is a flat candle, skip
EPS = 1e-9


# ---------------------------------------------------------------------- #
# Candle-geometry helpers
# ---------------------------------------------------------------------- #

def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 0.0)


def _upper_wick(o: float, h: float, c: float) -> float:
    return h - max(o, c)


def _lower_wick(o: float, l: float, c: float) -> float:
    return min(o, c) - l


def _is_green(o: float, c: float) -> bool:
    return c > o


def _is_red(o: float, c: float) -> bool:
    return c < o


def _cpr(o: float, h: float, l: float, c: float) -> float:
    """Close Position in Range — where in the day's range did it close.
    1.0 = closed at high, 0.0 = closed at low. Returns 0.5 for a flat day."""
    rng = h - l
    if rng <= EPS:
        return 0.5
    return (c - l) / rng


# ---------------------------------------------------------------------- #
# Pattern detectors — each returns dict or None.
# Each receives plain floats (not pandas Series) for speed and clarity.
# ---------------------------------------------------------------------- #

def detect_bullish_engulfing(today: dict, prev: dict) -> Optional[dict]:
    """Classic 2-candle reversal: a red candle is completely engulfed by a
    larger green candle that follows. Signals buyers decisively taking
    control after sellers were in charge."""
    o, c = today['open'], today['close']
    po, pc = prev['open'], prev['close']

    # Today green, yesterday red
    if not _is_green(o, c):
        return None
    if not _is_red(po, pc):
        return None

    # Engulfment: today's body fully wraps yesterday's body
    # (open at-or-below prev close, close at-or-above prev open)
    if o > pc:
        return None
    if c < po:
        return None

    body_today = c - o
    body_prev = po - pc
    price = c

    # Skip micro-candles
    if body_prev < MIN_BODY_PCT * price:
        return None
    # Today's body must materially exceed yesterday's (>= 1.2x)
    if body_today < body_prev * 1.2:
        return None

    return {
        'name': 'Bullish Engulfing',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 60,
        'plain': (
            "Yesterday's red candle was completely wrapped by today's larger "
            "green one. Buyers took over decisively — classic 2-candle reversal."
        ),
        'geometry': {
            'today_body': round(body_today, 4),
            'prev_body': round(body_prev, 4),
            'body_ratio': round(body_today / body_prev, 2),
        },
    }


def detect_hammer(today: dict, df_tail: pd.DataFrame) -> Optional[dict]:
    """Single-candle reversal: long lower wick (≥ 2× body), tiny upper wick,
    body in upper third. Signals that sellers pushed price down hard intraday
    but buyers reclaimed everything by close. Only counts if it's near support
    or after a recent decline — otherwise it's just a bullish candle."""
    o, h, l, c = today['open'], today['high'], today['low'], today['close']
    rng = _range(h, l)
    if rng <= EPS:
        return None

    body = _body(o, c)
    upper = _upper_wick(o, h, c)
    lower = _lower_wick(o, l, c)
    price = c

    if body < MIN_BODY_PCT * price:
        return None

    # Lower wick must be ≥ 2× body
    if lower < 2 * body:
        return None

    # Upper wick should be small — small relative to body OR absolutely small
    if upper > body * 0.5 and upper > rng * 0.1:
        return None

    # Body must sit in upper third of the range
    body_top = max(o, c)
    if (body_top - l) / rng < 0.66:
        return None

    # Location guard: only count if recent move was DOWN, or if we're sitting
    # at a recent low (within 4% of last 20-day low). Otherwise this is just
    # a bullish candle in an uptrend and the hammer signal is weak.
    if len(df_tail) >= 5:
        prev5_close = float(df_tail.iloc[-5]['close'])
        ret_5d = (c - prev5_close) / prev5_close * 100 if prev5_close > 0 else 0
        recent_20_low = float(df_tail['low'].tail(20).min()) if len(df_tail) >= 5 else l
        near_recent_low = recent_20_low > 0 and (c - recent_20_low) / c < 0.04
        if ret_5d >= 0 and not near_recent_low:
            return None  # not a reversal — just a long-tailed candle

    return {
        'name': 'Hammer',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 50,
        'plain': (
            "Long lower wick — sellers drove the price down intraday but "
            "buyers reclaimed all of it by the close. Classic capitulation "
            "candle. Strongest when it appears at a support level."
        ),
        'geometry': {
            'body': round(body, 4),
            'lower_wick': round(lower, 4),
            'upper_wick': round(upper, 4),
            'wick_to_body': round(lower / body, 2) if body > 0 else None,
        },
    }


def detect_inverted_hammer(today: dict, df_tail: pd.DataFrame) -> Optional[dict]:
    """Like hammer but upper wick is the long one. Body sits in lower third.
    Only meaningful after a downtrend — it suggests buyers tried to push up,
    got rejected, but the next day often confirms the reversal."""
    o, h, l, c = today['open'], today['high'], today['low'], today['close']
    rng = _range(h, l)
    if rng <= EPS:
        return None

    body = _body(o, c)
    upper = _upper_wick(o, h, c)
    lower = _lower_wick(o, l, c)
    price = c

    if body < MIN_BODY_PCT * price:
        return None
    if upper < 2 * body:
        return None
    if lower > body * 0.5 and lower > rng * 0.1:
        return None
    # Body must be in lower third
    body_top = max(o, c)
    if (body_top - l) / rng > 0.4:
        return None

    # Must be in a downtrend (recent 5-day return <= 0)
    if len(df_tail) >= 5:
        prev5_close = float(df_tail.iloc[-5]['close'])
        if prev5_close <= 0:
            return None
        ret_5d = (c - prev5_close) / prev5_close * 100
        if ret_5d > -1:
            return None  # only counts after meaningful decline
    else:
        return None

    return {
        'name': 'Inverted Hammer',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 45,
        'plain': (
            "Long upper wick — buyers attempted to push the price up but "
            "got rejected. Appears at the bottom of a decline; often signals "
            "buyers testing the waters before a real reversal the next day."
        ),
        'geometry': {
            'body': round(body, 4),
            'upper_wick': round(upper, 4),
            'lower_wick': round(lower, 4),
            'wick_to_body': round(upper / body, 2) if body > 0 else None,
        },
    }


def detect_morning_star(today: dict, prev1: dict, prev2: dict) -> Optional[dict]:
    """Three-candle reversal at the bottom of a decline.
        Day 1 (prev2): long red — sellers in control.
        Day 2 (prev1): small body (any color) — indecision.
        Day 3 (today): long green, closes ≥ 50% into day 1's body — bulls win.
    One of the highest-confidence reversal patterns in classical TA."""
    # Day 1 — long red
    if not _is_red(prev2['open'], prev2['close']):
        return None
    body_d1 = prev2['open'] - prev2['close']
    range_d1 = _range(prev2['high'], prev2['low'])
    if range_d1 <= EPS or body_d1 / range_d1 < 0.6:
        return None
    if body_d1 < MIN_BODY_PCT * prev2['close']:
        return None

    # Day 2 — small body (any color)
    body_d2 = _body(prev1['open'], prev1['close'])
    range_d2 = _range(prev1['high'], prev1['low'])
    if range_d2 <= EPS:
        return None
    if body_d2 > body_d1 * 0.5:
        return None  # day 2 body too big — not a star
    if body_d2 / range_d2 > 0.5:
        return None

    # Day 2's body should not be above day 1's close by much (allow small overlap)
    d2_body_top = max(prev1['open'], prev1['close'])
    if d2_body_top > prev2['open']:  # would mean day 2 already engulfs day 1
        return None

    # Day 3 — long green, closes well into day 1's body
    if not _is_green(today['open'], today['close']):
        return None
    body_d3 = today['close'] - today['open']
    if body_d3 < body_d1 * 0.5:
        return None
    midpoint_d1 = (prev2['open'] + prev2['close']) / 2.0
    if today['close'] < midpoint_d1:
        return None

    return {
        'name': 'Morning Star',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 80,
        'plain': (
            "Three-candle reversal: a long red day of selling, an indecisive "
            "small-bodied day (the 'star'), then a strong green day that "
            "closes well into the first day's body. One of the highest-"
            "confidence reversal signals in classical chart analysis."
        ),
        'geometry': {
            'd1_body': round(body_d1, 4),
            'd2_body': round(body_d2, 4),
            'd3_body': round(body_d3, 4),
            'penetration_into_d1': round(
                (today['close'] - prev2['close']) / max(body_d1, EPS) * 100, 1
            ),
        },
    }


def detect_three_white_soldiers(today: dict, prev1: dict,
                                prev2: dict) -> Optional[dict]:
    """Three consecutive strong green candles, each opening within the
    previous body and closing at a new high. Bodies similar size, upper wicks
    small. Signals sustained, controlled buying."""
    # All three green
    for r in (prev2, prev1, today):
        if not _is_green(r['open'], r['close']):
            return None

    # Each closes higher than the previous
    if not (prev1['close'] > prev2['close']):
        return None
    if not (today['close'] > prev1['close']):
        return None

    # Each opens within the previous body (not gapping up — controlled buying)
    if not (prev2['open'] <= prev1['open'] <= prev2['close']):
        return None
    if not (prev1['open'] <= today['open'] <= prev1['close']):
        return None

    # Bodies substantial (≥ 50% of range)
    for r in (prev2, prev1, today):
        body = r['close'] - r['open']
        rng = _range(r['high'], r['low'])
        if rng <= EPS or body / rng < 0.5:
            return None
        if body < MIN_BODY_PCT * r['close']:
            return None

    # Upper wicks small (no exhaustion at top — sellers haven't returned)
    for r in (prev2, prev1, today):
        upper = r['high'] - r['close']
        body = r['close'] - r['open']
        if upper > body * 0.6:
            return None

    return {
        'name': 'Three White Soldiers',
        'type': 'continuation',
        'bias': 'bullish',
        'base_strength': 70,
        'plain': (
            "Three strong green candles in a row, each opening inside the "
            "previous body and closing at a new high. Sellers were unable "
            "to push price down at any point. Signals sustained, controlled "
            "buying — a hallmark of accumulation."
        ),
        'geometry': {
            'd1_body': round(prev2['close'] - prev2['open'], 4),
            'd2_body': round(prev1['close'] - prev1['open'], 4),
            'd3_body': round(today['close'] - today['open'], 4),
            'gain_3d_pct': round(
                (today['close'] - prev2['open']) / prev2['open'] * 100, 2
            ) if prev2['open'] > 0 else None,
        },
    }


def detect_piercing_line(today: dict, prev: dict) -> Optional[dict]:
    """Bullish 2-candle reversal: day 1 is a meaningful red candle, day 2
    opens BELOW day 1's low (gap down) but closes above day 1's midpoint —
    though below day 1's open (otherwise it'd be an engulfing).
    Signals that overnight sellers took control, but intraday buyers
    overpowered them."""
    if not _is_red(prev['open'], prev['close']):
        return None
    body_d1 = prev['open'] - prev['close']
    if body_d1 < 0.005 * prev['close']:  # need a meaningful red day
        return None

    if not _is_green(today['open'], today['close']):
        return None

    # Today must open below yesterday's low (gap down)
    if today['open'] >= prev['low']:
        return None

    midpoint_d1 = (prev['open'] + prev['close']) / 2.0
    # Today must close ≥ day-1 midpoint but < day-1 open (else: engulfing)
    if today['close'] < midpoint_d1:
        return None
    if today['close'] >= prev['open']:
        return None

    penetration = (today['close'] - prev['close']) / max(body_d1, EPS) * 100
    return {
        'name': 'Piercing Line',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 60,
        'plain': (
            "Overnight sellers gapped the price below yesterday's low, but "
            "intraday buyers stepped in and pushed it back more than halfway "
            "into yesterday's red body. Signals a reversal in progress — "
            "not as decisive as engulfing, but on the same family."
        ),
        'geometry': {
            'd1_body': round(body_d1, 4),
            'gap_down': round(prev['low'] - today['open'], 4),
            'penetration_pct': round(penetration, 1),
        },
    }


def detect_bullish_marubozu(today: dict) -> Optional[dict]:
    """Pure momentum candle: solid green body with no/minimal wicks.
    Sellers had no influence at any point. Body must be ≥ 95% of range."""
    o, h, l, c = today['open'], today['high'], today['low'], today['close']
    if not _is_green(o, c):
        return None
    body = c - o
    rng = _range(h, l)
    if rng <= EPS:
        return None
    if body / rng < 0.95:
        return None
    if body < 0.01 * c:  # 1% body min
        return None
    return {
        'name': 'Bullish Marubozu',
        'type': 'continuation',
        'bias': 'bullish',
        'base_strength': 55,
        'plain': (
            "A nearly wickless solid green candle — the stock opened at the "
            "day's low and closed at the day's high. Sellers had no influence "
            "all day. Pure momentum signal."
        ),
        'geometry': {
            'body_pct_of_range': round(body / rng * 100, 1),
            'body': round(body, 4),
            'upper_wick': round(_upper_wick(o, h, c), 4),
            'lower_wick': round(_lower_wick(o, l, c), 4),
        },
    }


def detect_bullish_harami(today: dict, prev: dict) -> Optional[dict]:
    """Day 1: long red. Day 2: small green completely inside day 1's body.
    A weaker reversal hint — momentum is fading, but no decisive bull push
    yet. Often precedes a stronger confirmation pattern."""
    if not _is_red(prev['open'], prev['close']):
        return None
    body_d1 = prev['open'] - prev['close']
    range_d1 = _range(prev['high'], prev['low'])
    if range_d1 <= EPS or body_d1 / range_d1 < 0.5:
        return None
    if body_d1 < MIN_BODY_PCT * prev['close']:
        return None

    if not _is_green(today['open'], today['close']):
        return None

    # Day 2's body fully inside day 1's body
    if today['open'] < prev['close'] or today['close'] > prev['open']:
        return None

    body_d2 = today['close'] - today['open']
    if body_d2 > body_d1 * 0.5:
        return None
    if body_d2 < MIN_BODY_PCT * today['close']:
        return None

    return {
        'name': 'Bullish Harami',
        'type': 'reversal',
        'bias': 'bullish',
        'base_strength': 45,
        'plain': (
            "Yesterday's long red candle was followed by a small green candle "
            "that sits entirely inside yesterday's body. The selling has "
            "paused — buyers are testing. Often a precursor to a stronger "
            "reversal pattern over the next 1-2 days. Wait for confirmation."
        ),
        'geometry': {
            'd1_body': round(body_d1, 4),
            'd2_body': round(body_d2, 4),
        },
    }


# ---------------------------------------------------------------------- #
# Context — trend, support/resistance, volume, SMA200
# ---------------------------------------------------------------------- #

def _safe_float(v) -> float:
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def compute_context(df: pd.DataFrame) -> dict:
    """Compute trend, support, resistance, volume, SMA200 from history."""
    if len(df) < 20:
        return {}

    close = _safe_float(df.iloc[-1]['close'])
    if close <= 0:
        return {}

    # --- Trend over last 10d vs prior 10d ---
    trend = 'unknown'
    trend_slope_pct = 0.0
    if len(df) >= 20:
        sma10_recent = float(df['close'].tail(10).mean())
        sma10_prior = float(df['close'].iloc[-20:-10].mean())
        if sma10_prior > 0:
            trend_slope_pct = (sma10_recent - sma10_prior) / sma10_prior * 100
            if trend_slope_pct < -2.0:
                trend = 'downtrend'
            elif trend_slope_pct > 2.0:
                trend = 'uptrend'
            else:
                trend = 'sideways'

    # --- SMA200 ---
    if len(df) >= 200:
        sma200 = float(df['close'].tail(200).mean())
    else:
        sma200 = float(df['close'].mean())
    sma200_distance_pct = (close - sma200) / sma200 * 100 if sma200 > 0 else 0

    # --- Support / Resistance from last 30 days (avg of 3 lowest lows, 3 highest highs) ---
    recent_30 = df.tail(30)
    support = float(recent_30['low'].nsmallest(3).mean())
    resistance = float(recent_30['high'].nlargest(3).mean())
    near_support = abs(close - support) / close < 0.03
    near_resistance = abs(close - resistance) / close < 0.03

    # --- Volume context ---
    rvol = 1.0
    avg_vol_20 = 0
    if 'volume' in df.columns and len(df) >= 20:
        avg_vol_20 = float(df['volume'].tail(20).mean())
        today_vol = float(df.iloc[-1]['volume']) if pd.notna(df.iloc[-1]['volume']) else 0
        if avg_vol_20 > 0:
            rvol = today_vol / avg_vol_20

    # --- 5-day return (for "extended" check) ---
    ret_5d_pct = 0.0
    if len(df) >= 6:
        prev5_close = float(df.iloc[-6]['close'])
        if prev5_close > 0:
            ret_5d_pct = (close - prev5_close) / prev5_close * 100

    return {
        'trend': trend,
        'trend_slope_pct': round(trend_slope_pct, 2),
        'sma200': round(sma200, 2),
        'sma200_distance_pct': round(sma200_distance_pct, 2),
        'support': round(support, 2),
        'resistance': round(resistance, 2),
        'near_support': bool(near_support),
        'near_resistance': bool(near_resistance),
        'rvol': round(rvol, 2),
        'avg_vol_20d': int(avg_vol_20),
        'ret_5d_pct': round(ret_5d_pct, 2),
    }


# ---------------------------------------------------------------------- #
# Context multipliers
# ---------------------------------------------------------------------- #

def apply_multipliers(pattern: dict, context: dict) -> dict:
    """Adjust base strength by context. Returns a new pattern dict with
    `final_strength`, `multipliers`, `context_notes` populated."""
    base = float(pattern['base_strength'])
    multipliers: Dict[str, float] = {}
    notes: List[str] = []

    bias = pattern['bias']
    ptype = pattern['type']
    trend = context.get('trend', 'unknown')

    # ---- Trend alignment ----
    if bias == 'bullish':
        if ptype == 'reversal':
            if trend == 'downtrend':
                multipliers['downtrend_reversal'] = 1.4
                notes.append("In downtrend — classic reversal setup (+40%)")
            elif trend == 'uptrend':
                multipliers['uptrend_dip'] = 0.7
                notes.append("In uptrend — likely just a pullback, less significant (-30%)")
            else:
                multipliers['sideways_neutral'] = 1.0
        elif ptype == 'continuation':
            if trend == 'uptrend':
                multipliers['trend_aligned'] = 1.3
                notes.append("Aligned with existing uptrend (+30%)")
            elif trend == 'downtrend':
                multipliers['trend_against'] = 0.5
                notes.append("Conflicts with prevailing downtrend (-50%)")

    # ---- Location ----
    near_support = context.get('near_support', False)
    near_resistance = context.get('near_resistance', False)
    if bias == 'bullish':
        if near_support and ptype == 'reversal':
            multipliers['at_support'] = 1.5
            notes.append("At a key support level — high-conviction setup (+50%)")
        elif near_resistance and ptype == 'reversal':
            multipliers['under_resistance'] = 0.6
            notes.append("Just under resistance — likely to be rejected (-40%)")
        elif near_resistance and ptype == 'continuation':
            multipliers['breakout_attempt'] = 1.2
            notes.append("Pressing into resistance — possible breakout (+20%)")

    # ---- Volume confirmation ----
    rvol = context.get('rvol', 1.0)
    if rvol >= 2.0:
        multipliers['high_volume'] = 1.3
        notes.append(f"High-volume confirmation ({rvol:.1f}× avg) (+30%)")
    elif rvol >= 1.5:
        multipliers['elevated_volume'] = 1.15
        notes.append(f"Elevated volume ({rvol:.1f}× avg) (+15%)")
    elif rvol < 0.7:
        multipliers['low_volume'] = 0.7
        notes.append(f"Low volume — unconfirmed ({rvol:.1f}× avg) (-30%)")

    # ---- SMA200 alignment ----
    sma_dist = context.get('sma200_distance_pct', 0)
    if bias == 'bullish':
        if sma_dist > 5:
            multipliers['above_sma200'] = 1.1
            notes.append(f"Above 200-day MA ({sma_dist:+.1f}%) — long-term uptrend (+10%)")
        elif sma_dist < -15:
            multipliers['far_below_sma200'] = 0.7
            notes.append(f"Well below 200-day MA ({sma_dist:+.1f}%) — fighting the trend (-30%)")

    # ---- Apply ----
    final = base
    for m in multipliers.values():
        final *= m
    final = max(0, min(100, int(round(final))))

    return {
        **pattern,
        'final_strength': final,
        'multipliers': {k: round(v, 2) for k, v in multipliers.items()},
        'context_notes': notes,
    }


# ---------------------------------------------------------------------- #
# Aggregation — per-ticker overall score & bias
# ---------------------------------------------------------------------- #

def aggregate_patterns(patterns: List[dict], context: dict) -> dict:
    """Combine all detected patterns for a ticker into an overall view."""
    if not patterns:
        return {
            'overall_score': 0,
            'overall_bias': 'neutral',
            'confidence': 'NONE',
            'pattern_count': 0,
        }

    bullish_sum = sum(p['final_strength'] for p in patterns if p['bias'] == 'bullish')
    bearish_sum = sum(p['final_strength'] for p in patterns if p['bias'] == 'bearish')
    net = bullish_sum - bearish_sum

    if net > 0:
        overall_score = min(100, net)
        overall_bias = 'bullish'
    elif net < 0:
        overall_score = min(100, -net)
        overall_bias = 'bearish'
    else:
        overall_score = 0
        overall_bias = 'neutral'

    if overall_score >= 80 and len(patterns) >= 2:
        confidence = 'HIGH'
    elif overall_score >= 50:
        confidence = 'MEDIUM'
    elif overall_score >= 25:
        confidence = 'LOW'
    else:
        confidence = 'NONE'
        overall_bias = 'neutral'

    return {
        'overall_score': int(overall_score),
        'overall_bias': overall_bias,
        'confidence': confidence,
        'pattern_count': len(patterns),
    }


# ---------------------------------------------------------------------- #
# Human-readable explanation
# ---------------------------------------------------------------------- #

def build_explanation(patterns: List[dict], context: dict, agg: dict) -> str:
    """Plain-English summary of why this ticker scored how it did."""
    if not patterns:
        return "No bullish or bearish candlestick patterns detected today."

    lines = []
    trend = context.get('trend', 'unknown')
    rvol = context.get('rvol', 1.0)
    sma_dist = context.get('sma200_distance_pct', 0)

    lines.append(
        f"Detected {len(patterns)} candlestick pattern"
        f"{'s' if len(patterns) > 1 else ''} today. "
        f"Trend is {trend}, today's volume was {rvol:.1f}× the 20-day average, "
        f"and price is {sma_dist:+.1f}% from the 200-day MA."
    )

    for p in patterns:
        line = (
            f"• {p['name']} (strength {p['final_strength']}/100): {p['plain']}"
        )
        if p.get('context_notes'):
            line += " — " + "; ".join(p['context_notes'])
        lines.append(line)

    lines.append(
        f"\nOverall bias: {agg['overall_bias'].upper()} with "
        f"{agg['confidence']} confidence (score {agg['overall_score']}/100)."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# Per-ticker analyzer
# ---------------------------------------------------------------------- #

class ChartAnalyzer:
    """Detect candlestick patterns on every ticker and store results."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def analyze_ticker(self, ticker: str,
                       df: Optional[pd.DataFrame] = None) -> Optional[dict]:
        """Return chart-analysis result for one ticker, or None if not enough
        history. If `df` is provided, use it directly (no DB hit); else load."""
        if df is None:
            df = self.db.get_stock_data(ticker)
        if df is None or df.empty or len(df) < MIN_HISTORY_DAYS:
            return None

        df = df.sort_values('date').reset_index(drop=True)

        # Last 3 rows for pattern detection
        if len(df) < 3:
            return None

        today_row = df.iloc[-1].to_dict()
        prev1_row = df.iloc[-2].to_dict()
        prev2_row = df.iloc[-3].to_dict()

        # Guard against NaN OHLC
        for r in (today_row, prev1_row, prev2_row):
            for k in ('open', 'high', 'low', 'close'):
                v = r.get(k)
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    return None
            # Volume can be NaN, treat as 0
            if pd.isna(r.get('volume')):
                r['volume'] = 0

        context = compute_context(df)
        if not context:
            return None

        # Use the actual trading date (last row of OHLCV) — NOT calendar
        # now(). This way `analysis_date` reflects when the patterns
        # actually fired on tape; weekends, holidays, and stale tickers
        # are handled correctly.
        last_date_raw = df.iloc[-1].get('date')
        if isinstance(last_date_raw, pd.Timestamp):
            analysis_date = last_date_raw.strftime('%Y-%m-%d')
        else:
            analysis_date = str(last_date_raw)[:10]

        # Run each detector
        raw_patterns: List[dict] = []

        # 1-candle
        for detector, kwargs in (
            (detect_bullish_marubozu, {'today': today_row}),
        ):
            r = detector(**kwargs)
            if r:
                raw_patterns.append(r)

        # 1-candle with history (Hammer, Inverted Hammer)
        r = detect_hammer(today_row, df)
        if r:
            raw_patterns.append(r)
        r = detect_inverted_hammer(today_row, df)
        if r:
            raw_patterns.append(r)

        # 2-candle
        r = detect_bullish_engulfing(today_row, prev1_row)
        if r:
            raw_patterns.append(r)
        r = detect_piercing_line(today_row, prev1_row)
        if r:
            raw_patterns.append(r)
        r = detect_bullish_harami(today_row, prev1_row)
        if r:
            raw_patterns.append(r)

        # 3-candle
        r = detect_morning_star(today_row, prev1_row, prev2_row)
        if r:
            raw_patterns.append(r)
        r = detect_three_white_soldiers(today_row, prev1_row, prev2_row)
        if r:
            raw_patterns.append(r)

        # Apply context multipliers
        scored_patterns = [apply_multipliers(p, context) for p in raw_patterns]
        scored_patterns.sort(key=lambda p: p['final_strength'], reverse=True)

        agg = aggregate_patterns(scored_patterns, context)
        explanation = build_explanation(scored_patterns, context, agg)

        return {
            'ticker': ticker,
            'analysis_date': analysis_date,
            'overall_score': agg['overall_score'],
            'overall_bias': agg['overall_bias'],
            'confidence': agg['confidence'],
            'pattern_count': agg['pattern_count'],
            'patterns': scored_patterns,
            'context': context,
            'explanation': explanation,
            'price': round(_safe_float(today_row['close']), 2),
        }

    def analyze_all_tickers(self, freshness_window_days: int = 3) -> List[dict]:
        """Run chart analysis on every ticker we have *fresh* history for.

        Tickers whose latest stock_data row is more than
        `freshness_window_days` behind the global maximum date are skipped —
        otherwise we'd flag stale months-old patterns as today's signals.
        """
        tickers = self.db.get_all_tickers()

        # Find the global latest date (the current trading session)
        try:
            from sqlalchemy import text as _text
            row = pd.read_sql_query(
                _text("SELECT MAX(date) AS m FROM stock_data"),
                self.db.engine,
            )
            global_max = row.iloc[0]['m']
        except Exception:
            global_max = None

        global_max_ts = pd.to_datetime(global_max) if global_max else None
        if global_max_ts is not None:
            cutoff = global_max_ts - pd.Timedelta(days=freshness_window_days)
        else:
            cutoff = None

        results: List[dict] = []
        skipped_stale = 0
        for t in tickers:
            try:
                df = self.db.get_stock_data(t)
                if df is None or df.empty:
                    continue
                # Freshness gate
                if cutoff is not None:
                    last_date = pd.to_datetime(df['date'].iloc[-1])
                    if last_date < cutoff:
                        skipped_stale += 1
                        continue
                r = self.analyze_ticker(t, df=df)
                if r is None:
                    continue
                if r['pattern_count'] > 0:
                    results.append(r)
            except Exception as e:
                logger.warning("ChartAnalyzer failed for %s: %s", t, e)
                continue
        logger.info(
            "ChartAnalyzer: %d/%d tickers produced patterns (%d skipped as stale)",
            len(results), len(tickers), skipped_stale,
        )
        return results

    def save_results(self, results: List[dict]):
        """Persist results into the chart_signals table (UPSERT per
        ticker+date)."""
        if not results:
            return
        self.db.save_chart_signals_bulk(results)
