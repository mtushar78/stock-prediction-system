"""
Chart-pattern analyzer — the THIRD independent engine.

Where `src/chart_analyzer.py` detects single/2/3-bar *candlestick* patterns,
this module detects classical multi-week *chart* patterns from Thomas
Bulkowski's "Encyclopedia of Chart Patterns" (2nd ed.). These are the
formations that play out over weeks to months on the daily chart:

    Reversal (bottoms — bullish):
        Double Bottom (Adam/Eve variants), Triple Bottom,
        Head-and-Shoulders Bottom, Three Rising Valleys,
        Rounding Bottom, Cup with Handle, Pipe Bottom
    Reversal (tops — bearish):
        Double Top, Triple Top, Head-and-Shoulders Top,
        Three Falling Peaks, Pipe Top
    Bilateral / continuation:
        Ascending / Descending / Symmetrical Triangle,
        Rectangle (top & bottom), Rising / Falling Wedge,
        Flag, High-and-Tight Flag, Pennant
    Event:
        Dead-Cat Bounce (the ≥15% one-day plunge warning)

Design goals that make this different from a naive "draw two lines" toy:

  1. Every pattern carries Bulkowski's *real* bull-market statistics —
     average move, break-even (5%) failure rate, throwback/pullback rate,
     and how often price meets the measure-rule target. These are the
     numbers a trader actually needs to size conviction.
  2. Every pattern computes a measure-rule PRICE TARGET and a stop, so the
     UI can draw them on the chart.
  3. Confirmation matters. Bulkowski shows ~65% of *unconfirmed* twin
     patterns never reach their breakout. We mark each pattern
     'confirmed' (a close has already broken out) or 'forming' (geometry
     complete, price coiled at the breakout line) and rank confirmed
     higher.
  4. Throwbacks/pullbacks hurt performance in every pattern. We flag
     nearby overhead resistance (bottoms) / underlying support (tops) as
     a quality penalty.

The engine emits geometry (key points + trend lines in date/price space)
so the front end can render necklines, trendlines and target lines
directly on the candlestick chart.

This engine does NOT emit BUY/SELL. It emits a bias + confidence + target
and lets the human (or a confluence tab) decide.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Need a decent runway to see multi-week patterns and the trend leading in.
MIN_HISTORY_DAYS = 60
# Only surface patterns whose breakout / most-recent pivot is within this many
# bars of the latest bar — otherwise it's ancient history, not actionable.
RECENCY_BARS = 45
EPS = 1e-9


# --------------------------------------------------------------------------- #
# Bulkowski statistics table (2nd edition, BULL market).
#   avg_move   : average rise (bottoms) or decline (tops), % — always positive.
#   fail       : break-even failure rate — % that fail to move 5% past breakout.
#   throwback  : throwback (bottoms) / pullback (tops) rate, %.
#   meet       : % of patterns that reach the measure-rule price target.
#   rank       : Bulkowski's overall performance rank within its breakout
#                direction (1 = best); None where he assigns none.
# These are the headline numbers from each chapter's Results Snapshot.
# --------------------------------------------------------------------------- #
STATS: Dict[str, Dict[str, Optional[float]]] = {
    # ---- Bullish reversals (up breakout) ----
    'double_bottom_aa': {'avg_move': 35, 'fail': 5, 'throwback': 64, 'meet': 66, 'rank': None},
    'double_bottom_ae': {'avg_move': 37, 'fail': 5, 'throwback': 59, 'meet': 66, 'rank': None},
    'double_bottom_ea': {'avg_move': 35, 'fail': 4, 'throwback': 57, 'meet': 66, 'rank': None},
    'double_bottom_ee': {'avg_move': 40, 'fail': 4, 'throwback': 55, 'meet': 67, 'rank': None},
    'triple_bottom':    {'avg_move': 37, 'fail': 4, 'throwback': 64, 'meet': 64, 'rank': None},
    'hs_bottom':        {'avg_move': 38, 'fail': 3, 'throwback': 45, 'meet': 74, 'rank': None},
    'three_rising_valleys': {'avg_move': 41, 'fail': 5, 'throwback': 60, 'meet': 58, 'rank': 4},
    'rounding_bottom':  {'avg_move': 43, 'fail': 5, 'throwback': 40, 'meet': 57, 'rank': None},
    'cup_with_handle':  {'avg_move': 34, 'fail': 5, 'throwback': 58, 'meet': 50, 'rank': None},
    'pipe_bottom':      {'avg_move': 45, 'fail': 5, 'throwback': 44, 'meet': 83, 'rank': 2},
    # ---- Bearish reversals (down breakout) ----
    'double_top_aa': {'avg_move': 19, 'fail': 8,  'throwback': 61, 'meet': 72, 'rank': None},
    'double_top_ae': {'avg_move': 18, 'fail': 14, 'throwback': 59, 'meet': 69, 'rank': None},
    'double_top_ea': {'avg_move': 15, 'fail': 13, 'throwback': 64, 'meet': 72, 'rank': None},
    'double_top_ee': {'avg_move': 18, 'fail': 11, 'throwback': 62, 'meet': 73, 'rank': None},
    'triple_top':    {'avg_move': 19, 'fail': 10, 'throwback': 61, 'meet': 40, 'rank': None},
    'hs_top':        {'avg_move': 22, 'fail': 4,  'throwback': 50, 'meet': 55, 'rank': 1},
    'three_falling_peaks': {'avg_move': 17, 'fail': 12, 'throwback': 59, 'meet': 33, 'rank': None},
    'pipe_top':      {'avg_move': 20, 'fail': 11, 'throwback': 41, 'meet': 70, 'rank': 4},
    # ---- Bilateral / continuation ----
    'ascending_triangle':   {'avg_move': 35, 'fail': 13, 'throwback': 57, 'meet': 75, 'rank': None},
    'descending_triangle':  {'avg_move': 16, 'fail': 16, 'throwback': 54, 'meet': 54, 'rank': None},
    'symmetrical_triangle': {'avg_move': 31, 'fail': 9,  'throwback': 54, 'meet': 66, 'rank': None},
    'rectangle_bottom': {'avg_move': 46, 'fail': 10, 'throwback': 53, 'meet': 85, 'rank': None},
    'rectangle_top':    {'avg_move': 39, 'fail': 9,  'throwback': 64, 'meet': 80, 'rank': None},
    'falling_wedge':    {'avg_move': 32, 'fail': 11, 'throwback': 56, 'meet': 70, 'rank': None},
    'rising_wedge':     {'avg_move': 14, 'fail': 24, 'throwback': 63, 'meet': 46, 'rank': None},
    'flag':             {'avg_move': 23, 'fail': 4,  'throwback': 43, 'meet': 64, 'rank': None},
    'high_tight_flag':  {'avg_move': 69, 'fail': 0,  'throwback': 54, 'meet': 90, 'rank': 1},
    'pennant':          {'avg_move': 25, 'fail': 2,  'throwback': 47, 'meet': 60, 'rank': None},
    # ---- Event ----
    'dead_cat_bounce':  {'avg_move': 18, 'fail': None, 'throwback': None, 'meet': None, 'rank': None},
}


# --------------------------------------------------------------------------- #
# OHLC sanity + zigzag pivot extraction
# --------------------------------------------------------------------------- #

def _valid_ohlc(o, h, l, c) -> bool:
    try:
        o, h, l, c = float(o), float(h), float(l), float(c)
    except (TypeError, ValueError):
        return False
    if not all(np.isfinite(v) and v > 0 for v in (o, h, l, c)):
        return False
    if h < l or o < l - EPS or o > h + EPS or c < l - EPS or c > h + EPS:
        return False
    return True


def clean_history(df: pd.DataFrame) -> pd.DataFrame:
    """Sort, drop broken/non-trading stub rows, reset index. Keeps only the
    columns we need and guarantees a clean, gap-free bar sequence."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    if 'date' not in df.columns:
        return pd.DataFrame()
    df = df.sort_values('date').reset_index(drop=True)
    mask = df.apply(lambda r: _valid_ohlc(r.get('open'), r.get('high'),
                                          r.get('low'), r.get('close')), axis=1)
    df = df[mask].reset_index(drop=True)
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    else:
        df['volume'] = 0
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def _date_str(v) -> str:
    if isinstance(v, pd.Timestamp):
        return v.strftime('%Y-%m-%d')
    return str(v)[:10]


def find_pivots(df: pd.DataFrame, pct: float = 0.05) -> List[dict]:
    """Percentage zigzag. Returns an alternating list of swing pivots:
        {'idx', 'date', 'price', 'kind': 'H'|'L'}
    A new pivot is confirmed once price reverses `pct` (fraction, e.g. 0.05
    = 5%) from the running extreme. Peaks use the bar HIGH, troughs the LOW —
    the levels chart patterns are actually built from.

    `pct` auto-adapts: low-priced DSE stocks are noisier, so we widen the
    threshold a touch for sub-20 Tk names.
    """
    n = len(df)
    if n < 5:
        return []

    highs = df['high'].to_numpy(dtype=float)
    lows = df['low'].to_numpy(dtype=float)

    pivots: List[dict] = []
    # Seed direction by comparing the first few bars.
    direction = 0  # +1 = looking for a high, -1 = looking for a low
    ext_idx = 0
    ext_price = highs[0]

    # Bootstrap: decide initial trend from first swing.
    first_high, first_low = highs[0], lows[0]
    up_ext_idx, up_ext = 0, first_high
    dn_ext_idx, dn_ext = 0, first_low

    for i in range(1, n):
        if direction >= 0:
            # In an up-leg: track the highest high.
            if highs[i] > up_ext:
                up_ext, up_ext_idx = highs[i], i
            # Reversal down from the high?
            if lows[i] <= up_ext * (1 - pct):
                pivots.append({'idx': up_ext_idx, 'date': _date_str(df.iloc[up_ext_idx]['date']),
                               'price': float(up_ext), 'kind': 'H'})
                direction = -1
                dn_ext, dn_ext_idx = lows[i], i
        if direction <= 0:
            if lows[i] < dn_ext:
                dn_ext, dn_ext_idx = lows[i], i
            if highs[i] >= dn_ext * (1 + pct):
                pivots.append({'idx': dn_ext_idx, 'date': _date_str(df.iloc[dn_ext_idx]['date']),
                               'price': float(dn_ext), 'kind': 'L'})
                direction = 1
                up_ext, up_ext_idx = highs[i], i

    # Collapse any accidental same-kind repeats (keep the more extreme).
    cleaned: List[dict] = []
    for p in pivots:
        if cleaned and cleaned[-1]['kind'] == p['kind']:
            if p['kind'] == 'H' and p['price'] >= cleaned[-1]['price']:
                cleaned[-1] = p
            elif p['kind'] == 'L' and p['price'] <= cleaned[-1]['price']:
                cleaned[-1] = p
        else:
            cleaned.append(p)
    return cleaned


# --------------------------------------------------------------------------- #
# Small geometry helpers
# --------------------------------------------------------------------------- #

def _pct_diff(a: float, b: float) -> float:
    """|a-b| as a fraction of their mean."""
    m = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / m if m > EPS else 999.0


def _slope_intercept(x1, y1, x2, y2) -> Tuple[float, float]:
    if x2 == x1:
        return 0.0, y1
    m = (y2 - y1) / (x2 - x1)
    return m, y1 - m * x1


def _line_at(m: float, b: float, x: float) -> float:
    return m * x + b


def _trend_before(df: pd.DataFrame, start_idx: int, lookback: int = 20) -> float:
    """% price change over the `lookback` bars leading INTO start_idx.
    Negative = downtrend into the pattern (what bottoms want)."""
    a = max(0, start_idx - lookback)
    p0 = float(df.iloc[a]['close'])
    p1 = float(df.iloc[start_idx]['close'])
    return (p1 - p0) / p0 * 100 if p0 > 0 else 0.0


def _rvol_at(df: pd.DataFrame, idx: int, window: int = 20) -> float:
    a = max(0, idx - window)
    avg = float(df['volume'].iloc[a:idx].mean()) if idx > a else 0.0
    v = float(df['volume'].iloc[idx])
    return v / avg if avg > 0 else 1.0


def _confirm_close_above(df: pd.DataFrame, level: float, start_idx: int) -> Optional[int]:
    """Index of the first bar after start_idx that CLOSES above `level`."""
    for i in range(start_idx + 1, len(df)):
        if float(df.iloc[i]['close']) > level:
            return i
    return None


def _confirm_close_below(df: pd.DataFrame, level: float, start_idx: int) -> Optional[int]:
    for i in range(start_idx + 1, len(df)):
        if float(df.iloc[i]['close']) < level:
            return i
    return None


def _pt(df: pd.DataFrame, idx: int, price: float, label: str = '') -> dict:
    return {'date': _date_str(df.iloc[idx]['date']), 'price': round(float(price), 3), 'label': label}


def _pivot_width_bars(df: pd.DataFrame, idx: int, price: float, is_low: bool,
                      tol: float = 0.03) -> int:
    """Rough Adam/Eve width: how many consecutive bars around `idx` stay
    within `tol` of the pivot price. Narrow (≈1-3, spiky) → Adam; wide → Eve."""
    n = len(df)
    lo = hi = idx
    while lo - 1 >= 0 and _pct_diff(float(df.iloc[lo - 1]['low' if is_low else 'high']), price) < tol:
        lo -= 1
    while hi + 1 < n and _pct_diff(float(df.iloc[hi + 1]['low' if is_low else 'high']), price) < tol:
        hi += 1
    return hi - lo + 1


# --------------------------------------------------------------------------- #
# Pattern builder — shared result envelope
# --------------------------------------------------------------------------- #

def _make(df: pd.DataFrame, code: str, name: str, category: str, bias: str,
          status: str, key_points: List[dict], lines: List[dict],
          start_idx: int, end_idx: int, breakout_idx: Optional[int],
          breakout_price: Optional[float], target: Optional[float],
          stop: Optional[float], height_pct: float, plain: str,
          quality_notes: List[str], quality_score: float) -> dict:
    def _num(v, ndigits=3):
        """JSON-safe number: None/NaN/inf -> None, else rounded float."""
        if v is None:
            return None
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return None
        if not np.isfinite(fv):
            return None
        return round(fv, ndigits)

    st = STATS.get(code, {})
    price_now = float(df.iloc[-1]['close'])
    target_pct = None
    if target is not None and price_now > 0:
        target_pct = _num((target - price_now) / price_now * 100, 1)
    # Confidence: geometry quality × Bulkowski reliability × confirmation.
    fail = st.get('fail')
    reliability = 1.0 - (fail / 100.0) if fail is not None else 0.7
    conf_raw = quality_score * reliability
    if status == 'confirmed':
        conf_raw *= 1.15
    if conf_raw >= 0.72 and status == 'confirmed':
        confidence = 'HIGH'
    elif conf_raw >= 0.5:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'
    return {
        'code': code,
        'name': name,
        'category': category,        # reversal | continuation | event
        'bias': bias,                # bullish | bearish
        'status': status,            # confirmed | forming
        'start_date': _date_str(df.iloc[start_idx]['date']),
        'end_date': _date_str(df.iloc[end_idx]['date']),
        'breakout_date': _date_str(df.iloc[breakout_idx]['date']) if breakout_idx is not None else None,
        'breakout_price': _num(breakout_price),
        'target': _num(target),
        'target_pct': target_pct,
        'stop': _num(stop),
        'height_pct': _num(height_pct, 1),
        'confidence': confidence,
        'key_points': key_points,
        'lines': lines,
        'stats': {
            'avg_move_pct': st.get('avg_move'),
            'failure_rate_pct': st.get('fail'),
            'throwback_pct': st.get('throwback'),
            'meet_target_pct': st.get('meet'),
            'rank': st.get('rank'),
        },
        'plain': plain,
        'quality_notes': quality_notes,
        '_start_idx': start_idx,      # internal, stripped before serialization
        '_end_idx': end_idx,
        '_breakout_idx': breakout_idx,
        '_quality': round(conf_raw, 3),
    }


# --------------------------------------------------------------------------- #
# DETECTORS — double / triple / H&S / three-valley family (pivot based)
# --------------------------------------------------------------------------- #

def _classify_ae(width: int) -> str:
    """Adam (narrow/spiky) vs Eve (wide/rounded) from bar width."""
    return 'a' if width <= 3 else 'e'


def detect_double_bottom(df, pivots) -> List[dict]:
    """Two troughs at ~the same level separated by a peak ≥10% above them,
    after a downtrend; confirms on a close above that interior peak."""
    out = []
    lows = [p for p in pivots if p['kind'] == 'L']
    highs = [p for p in pivots if p['kind'] == 'H']
    for i in range(len(pivots) - 2):
        a, b, c = pivots[i], pivots[i + 1], pivots[i + 2]
        if not (a['kind'] == 'L' and b['kind'] == 'H' and c['kind'] == 'L'):
            continue
        low1, peak, low2 = a, b, c
        if _pct_diff(low1['price'], low2['price']) > 0.05:      # bottoms within 5%
            continue
        rise = (peak['price'] - min(low1['price'], low2['price'])) / min(low1['price'], low2['price'])
        if rise < 0.10:                                          # ≥10% valley→peak
            continue
        sep = low2['idx'] - low1['idx']
        if not (10 <= sep <= 70):                                # ~2-14 weeks
            continue
        if _trend_before(df, low1['idx'], 20) > 3:               # want a downtrend in
            continue
        # Price must not have broken below the pattern before confirming.
        interior_min = float(df['low'].iloc[low1['idx']:low2['idx'] + 1].min())
        conf = _confirm_close_above(df, peak['price'], low2['idx'])
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming':
            # only surface if price is coiled within 4% under the breakout line
            if float(df.iloc[-1]['close']) < peak['price'] * 0.96:
                continue
            end_idx = len(df) - 1
        else:
            end_idx = conf
        low_price = min(low1['price'], low2['price'])
        height = peak['price'] - low_price
        target = peak['price'] + height                          # full height (bottoms)
        w1 = _classify_ae(_pivot_width_bars(df, low1['idx'], low1['price'], True))
        w2 = _classify_ae(_pivot_width_bars(df, low2['idx'], low2['price'], True))
        code = f'double_bottom_{w1}{w2}'
        if code not in STATS:
            code = 'double_bottom_ee'
        variant = {'aa': 'Adam & Adam', 'ae': 'Adam & Eve',
                   'ea': 'Eve & Adam', 'ee': 'Eve & Eve'}[w1 + w2]
        breakout_price = peak['price']
        # throwback risk: overhead resistance from the last 6 months above breakout
        notes = _resistance_notes(df, breakout_price, low2['idx'], bullish=True)
        quality = _quality_from(sep_ok=(21 <= sep <= 49), sym=_pct_diff(low1['price'], low2['price']),
                                confirmed=(status == 'confirmed'), extra=(rise >= 0.15))
        out.append(_make(
            df, code, f'Double Bottom ({variant})', 'reversal', 'bullish', status,
            key_points=[_pt(df, low1['idx'], low1['price'], 'bottom 1'),
                        _pt(df, peak['idx'], peak['price'], 'confirm'),
                        _pt(df, low2['idx'], low2['price'], 'bottom 2')],
            lines=[_hline(df, peak['price'], low1['idx'], end_idx, 'neckline'),
                   _hline(df, target, (conf or end_idx), len(df) - 1, 'target')],
            start_idx=low1['idx'], end_idx=end_idx, breakout_idx=conf,
            breakout_price=breakout_price, target=target,
            stop=low_price * 0.99, height_pct=height / low_price * 100,
            plain=(f"Two troughs near {low_price:.2f} bracketing a rally to "
                   f"{peak['price']:.2f}. A close above {peak['price']:.2f} confirms the "
                   f"reversal. {variant}: the left/right bottoms are "
                   f"{'sharp V-spikes' if variant=='Adam & Adam' else 'rounded' if variant=='Eve & Eve' else 'mixed shapes'}."),
            quality_notes=notes, quality_score=quality,
        ))
    return _dedupe_recent(df, out)


def detect_double_top(df, pivots) -> List[dict]:
    out = []
    for i in range(len(pivots) - 2):
        a, b, c = pivots[i], pivots[i + 1], pivots[i + 2]
        if not (a['kind'] == 'H' and b['kind'] == 'L' and c['kind'] == 'H'):
            continue
        top1, valley, top2 = a, b, c
        if _pct_diff(top1['price'], top2['price']) > 0.05:
            continue
        drop = (max(top1['price'], top2['price']) - valley['price']) / max(top1['price'], top2['price'])
        if drop < 0.10:
            continue
        sep = top2['idx'] - top1['idx']
        if not (10 <= sep <= 70):
            continue
        if _trend_before(df, top1['idx'], 20) < -3:              # want an uptrend in
            continue
        conf = _confirm_close_below(df, valley['price'], top2['idx'])
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming':
            if float(df.iloc[-1]['close']) > valley['price'] * 1.04:
                continue
            end_idx = len(df) - 1
        else:
            end_idx = conf
        top_price = max(top1['price'], top2['price'])
        height = top_price - valley['price']
        target = valley['price'] - height / 2.0                  # HALF height (tops)
        if target <= 0:
            target = valley['price'] * 0.9
        w1 = _classify_ae(_pivot_width_bars(df, top1['idx'], top1['price'], False))
        w2 = _classify_ae(_pivot_width_bars(df, top2['idx'], top2['price'], False))
        code = f'double_top_{w1}{w2}'
        if code not in STATS:
            code = 'double_top_ee'
        variant = {'aa': 'Adam & Adam', 'ae': 'Adam & Eve',
                   'ea': 'Eve & Adam', 'ee': 'Eve & Eve'}[w1 + w2]
        notes = _support_notes(df, valley['price'], top2['idx'])
        quality = _quality_from(sep_ok=(14 <= sep <= 49), sym=_pct_diff(top1['price'], top2['price']),
                                confirmed=(status == 'confirmed'), extra=(drop >= 0.15))
        out.append(_make(
            df, code, f'Double Top ({variant})', 'reversal', 'bearish', status,
            key_points=[_pt(df, top1['idx'], top1['price'], 'top 1'),
                        _pt(df, valley['idx'], valley['price'], 'confirm'),
                        _pt(df, top2['idx'], top2['price'], 'top 2')],
            lines=[_hline(df, valley['price'], top1['idx'], end_idx, 'neckline'),
                   _hline(df, target, (conf or end_idx), len(df) - 1, 'target')],
            start_idx=top1['idx'], end_idx=end_idx, breakout_idx=conf,
            breakout_price=valley['price'], target=target,
            stop=top_price * 1.01, height_pct=height / top_price * 100,
            plain=(f"Two peaks near {top_price:.2f} around a dip to {valley['price']:.2f}. "
                   f"A close below {valley['price']:.2f} confirms the top. Target uses HALF "
                   f"the height — Bulkowski shows the full projection rarely fills on tops."),
            quality_notes=notes, quality_score=quality,
        ))
    return _dedupe_recent(df, out)


def detect_triple(df, pivots, bottom=True) -> List[dict]:
    """Triple Bottom / Triple Top — three ~equal extremes, center NOT the
    most extreme (else it's H&S)."""
    out = []
    kind = 'L' if bottom else 'H'
    opp = 'H' if bottom else 'L'
    for i in range(len(pivots) - 4):
        seq = pivots[i:i + 5]
        kinds = ''.join(p['kind'] for p in seq)
        want = (kind + opp) * 2 + kind
        if kinds != want:
            continue
        e1, m1, e2, m2, e3 = seq
        prices = [e1['price'], e2['price'], e3['price']]
        # three extremes must be genuinely level (within ~3%)
        if max(_pct_diff(prices[0], prices[1]), _pct_diff(prices[1], prices[2]),
               _pct_diff(prices[0], prices[2])) > 0.035:
            continue
        # center must not be the extreme one (that's H&S)
        if bottom and e2['price'] < min(e1['price'], e3['price']) * 0.98:
            continue
        if not bottom and e2['price'] > max(e1['price'], e3['price']) * 1.02:
            continue
        # meaningful width and depth — a real base, not three ticks of noise
        if e3['idx'] - e1['idx'] < 20:
            continue
        band = max(m1['price'], m2['price']) - min(prices) if bottom else max(prices) - min(m1['price'], m2['price'])
        if band / max(min(prices), EPS) < 0.06:
            continue
        interior = [m1, m2]
        if bottom:
            conf_level = max(m1['price'], m2['price'])
            conf = _confirm_close_above(df, conf_level, e3['idx'])
        else:
            conf_level = min(m1['price'], m2['price'])
            conf = _confirm_close_below(df, conf_level, e3['idx'])
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming':
            last = float(df.iloc[-1]['close'])
            if bottom and last < conf_level * 0.96:
                continue
            if not bottom and last > conf_level * 1.04:
                continue
            end_idx = len(df) - 1
        else:
            end_idx = conf
        ext = min(prices) if bottom else max(prices)
        height = abs(conf_level - ext)
        if bottom:
            target = conf_level + height
            bias, cat, code, nm = 'bullish', 'reversal', 'triple_bottom', 'Triple Bottom'
            notes = _resistance_notes(df, conf_level, e3['idx'], bullish=True)
            stop = ext * 0.99
        else:
            target = conf_level - height / 2.0
            bias, cat, code, nm = 'bearish', 'reversal', 'triple_top', 'Triple Top'
            notes = _support_notes(df, conf_level, e3['idx'])
            stop = ext * 1.01
        quality = _quality_from(sep_ok=True, sym=_pct_diff(prices[0], prices[2]),
                                confirmed=(status == 'confirmed'), extra=True)
        out.append(_make(
            df, code, nm, cat, bias, status,
            key_points=[_pt(df, e1['idx'], e1['price'], '1'),
                        _pt(df, e2['idx'], e2['price'], '2'),
                        _pt(df, e3['idx'], e3['price'], '3')],
            lines=[_hline(df, conf_level, e1['idx'], end_idx, 'neckline'),
                   _hline(df, target, (conf or end_idx), len(df) - 1, 'target')],
            start_idx=e1['idx'], end_idx=end_idx, breakout_idx=conf,
            breakout_price=conf_level, target=target, stop=stop,
            height_pct=height / ext * 100,
            plain=(f"Three {'troughs' if bottom else 'peaks'} near {ext:.2f}. "
                   f"A close {'above' if bottom else 'below'} {conf_level:.2f} confirms."),
            quality_notes=notes, quality_score=quality,
        ))
    return _dedupe_recent(df, out)


def detect_head_shoulders(df, pivots, bottom=True) -> List[dict]:
    """H&S bottom (inverse) / top. Five pivots; the head (center) is the
    most extreme; neckline joins the two interior opposite pivots."""
    out = []
    kind = 'L' if bottom else 'H'
    opp = 'H' if bottom else 'L'
    for i in range(len(pivots) - 4):
        seq = pivots[i:i + 5]
        kinds = ''.join(p['kind'] for p in seq)
        if kinds != (kind + opp) * 2 + kind:
            continue
        ls, n1, head, n2, rs = seq
        # head is the extreme
        if bottom and not (head['price'] < ls['price'] and head['price'] < rs['price']):
            continue
        if not bottom and not (head['price'] > ls['price'] and head['price'] > rs['price']):
            continue
        # shoulders roughly level (within 5%) and roughly symmetric in time
        if _pct_diff(ls['price'], rs['price']) > 0.05:
            continue
        d1, d2 = head['idx'] - ls['idx'], rs['idx'] - head['idx']
        if min(d1, d2) == 0 or max(d1, d2) / min(d1, d2) > 2.2:
            continue
        # head must be CLEARLY beyond the shoulders (≥5%) — else it's a triple.
        if _pct_diff(head['price'], (ls['price'] + rs['price']) / 2) < 0.05:
            continue
        # neckline (the two interior highs/lows) should be roughly level — a
        # real neckline, not a wild diagonal.
        if _pct_diff(n1['price'], n2['price']) > 0.10:
            continue
        # forms over weeks, not days
        if rs['idx'] - ls['idx'] < 25:
            continue
        m, b = _slope_intercept(n1['idx'], n1['price'], n2['idx'], n2['price'])
        # breakout = close beyond neckline projected forward
        conf = None
        for j in range(rs['idx'] + 1, len(df)):
            nl = _line_at(m, b, j)
            c = float(df.iloc[j]['close'])
            if (bottom and c > nl) or (not bottom and c < nl):
                conf = j
                break
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming':
            nl_now = _line_at(m, b, len(df) - 1)
            last = float(df.iloc[-1]['close'])
            if bottom and last < nl_now * 0.96:
                continue
            if not bottom and last > nl_now * 1.04:
                continue
            end_idx = len(df) - 1
            bo_price = nl_now
        else:
            end_idx = conf
            bo_price = _line_at(m, b, conf)
        neck_at_head = _line_at(m, b, head['idx'])
        height = abs(neck_at_head - head['price'])
        if bottom:
            target = bo_price + height
            bias, code, nm = 'bullish', 'hs_bottom', 'Head-and-Shoulders Bottom'
            notes = _resistance_notes(df, bo_price, rs['idx'], bullish=True)
            stop = min(ls['price'], rs['price']) * 0.99
        else:
            target = bo_price - height
            bias, code, nm = 'bearish', 'hs_top', 'Head-and-Shoulders Top'
            notes = _support_notes(df, bo_price, rs['idx'])
            stop = max(ls['price'], rs['price']) * 1.01
        quality = _quality_from(sep_ok=True, sym=_pct_diff(ls['price'], rs['price']),
                                confirmed=(status == 'confirmed'), extra=True)
        out.append(_make(
            df, code, nm, 'reversal', bias, status,
            key_points=[_pt(df, ls['idx'], ls['price'], 'L.shoulder'),
                        _pt(df, head['idx'], head['price'], 'head'),
                        _pt(df, rs['idx'], rs['price'], 'R.shoulder')],
            lines=[{'kind': 'neckline',
                    'points': [_pt(df, n1['idx'], n1['price']),
                               _pt(df, end_idx, _line_at(m, b, end_idx))]},
                   _hline(df, target, (conf or end_idx), len(df) - 1, 'target')],
            start_idx=ls['idx'], end_idx=end_idx, breakout_idx=conf,
            breakout_price=bo_price, target=target, stop=stop,
            height_pct=height / head['price'] * 100,
            plain=(f"{'Inverse ' if bottom else ''}Head-and-Shoulders: a "
                   f"{'low' if bottom else 'high'} ({head['price']:.2f}) flanked by two "
                   f"shallower shoulders near {ls['price']:.2f}. A close "
                   f"{'above' if bottom else 'below'} the neckline confirms; measure the "
                   f"head-to-neckline height off the breakout."),
            quality_notes=notes, quality_score=quality,
        ))
    return _dedupe_recent(df, out)


def detect_three_march(df, pivots, rising=True) -> List[dict]:
    """Three Rising Valleys (bullish) / Three Falling Peaks (bearish) —
    three monotonic same-kind pivots."""
    out = []
    kind = 'L' if rising else 'H'
    for i in range(len(pivots) - 4):
        seq = pivots[i:i + 5]
        same = [p for p in seq if p['kind'] == kind]
        if len(same) < 3:
            continue
        v1, v2, v3 = same[0], same[1], same[2]
        if rising and not (v1['price'] < v2['price'] < v3['price']):
            continue
        if not rising and not (v1['price'] > v2['price'] > v3['price']):
            continue
        # each step must be a real move (≥3%) and the run must span ≥25 bars —
        # otherwise every gently drifting zigzag qualifies.
        if _pct_diff(v1['price'], v2['price']) < 0.03 or _pct_diff(v2['price'], v3['price']) < 0.03:
            continue
        if v3['idx'] - v1['idx'] < 25:
            continue
        # total staircase must be a meaningful trend (≥8% end to end)
        if _pct_diff(v1['price'], v3['price']) < 0.08:
            continue
        opp = [p for p in seq if p['kind'] != kind and v1['idx'] < p['idx'] < v3['idx']]
        if not opp:
            continue
        if rising:
            conf_level = max(p['price'] for p in opp)
            conf = _confirm_close_above(df, conf_level, v3['idx'])
        else:
            conf_level = min(p['price'] for p in opp)
            conf = _confirm_close_below(df, conf_level, v3['idx'])
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming':
            last = float(df.iloc[-1]['close'])
            if rising and last < conf_level * 0.97:
                continue
            if not rising and last > conf_level * 1.03:
                continue
            end_idx = len(df) - 1
        else:
            end_idx = conf
        hi = max(p['price'] for p in seq)
        lo = min(p['price'] for p in seq)
        height = hi - lo
        if rising:
            target = conf_level + height
            code, nm, bias = 'three_rising_valleys', 'Three Rising Valleys', 'bullish'
            notes = _resistance_notes(df, conf_level, v3['idx'], bullish=True)
            stop = v3['price'] * 0.98
        else:
            target = conf_level - height
            code, nm, bias = 'three_falling_peaks', 'Three Falling Peaks', 'bearish'
            notes = _support_notes(df, conf_level, v3['idx'])
            stop = v3['price'] * 1.02
        quality = _quality_from(sep_ok=True, sym=0.02,
                                confirmed=(status == 'confirmed'), extra=True)
        out.append(_make(
            df, code, nm, 'reversal', bias, status,
            key_points=[_pt(df, v1['idx'], v1['price'], '1'),
                        _pt(df, v2['idx'], v2['price'], '2'),
                        _pt(df, v3['idx'], v3['price'], '3')],
            lines=[{'kind': 'trend',
                    'points': [_pt(df, v1['idx'], v1['price']), _pt(df, v3['idx'], v3['price'])]},
                   _hline(df, target, (conf or end_idx), len(df) - 1, 'target')],
            start_idx=v1['idx'], end_idx=end_idx, breakout_idx=conf,
            breakout_price=conf_level, target=target, stop=stop,
            height_pct=height / lo * 100,
            plain=(f"Three successively {'higher lows' if rising else 'lower highs'} — "
                   f"a {'staircase up' if rising else 'staircase down'}. Confirms on a close "
                   f"{'above' if rising else 'below'} {conf_level:.2f}."),
            quality_notes=notes, quality_score=quality,
        ))
    return _dedupe_recent(df, out)


# --------------------------------------------------------------------------- #
# DETECTORS — trendline family: triangles, rectangle, wedge
# --------------------------------------------------------------------------- #

def _fit_line(idxs, prices):
    """Least-squares slope/intercept for a set of pivot points."""
    if len(idxs) < 2:
        return None
    x = np.array(idxs, dtype=float)
    y = np.array(prices, dtype=float)
    m, b = np.polyfit(x, y, 1)
    return float(m), float(b)


def detect_trendline_patterns(df, pivots) -> List[dict]:
    """Triangles (asc/desc/sym), Rectangle (top/bottom), Wedges (rising/
    falling). Uses the last cluster of ≥2 highs and ≥2 lows, fits a top and
    a bottom trendline, and classifies by their slopes."""
    out = []
    n = len(df)
    # Work on the most recent pivots that form a converging/parallel band.
    recent = [p for p in pivots if p['idx'] >= n - 90]
    highs = [p for p in recent if p['kind'] == 'H']
    lows = [p for p in recent if p['kind'] == 'L']
    if len(highs) < 2 or len(lows) < 2:
        return out
    highs = highs[-3:]
    lows = lows[-3:]
    top = _fit_line([p['idx'] for p in highs], [p['price'] for p in highs])
    bot = _fit_line([p['idx'] for p in lows], [p['price'] for p in lows])
    if not top or not bot:
        return out
    tm, tb = top
    bm, bb = bot
    start_idx = min(highs[0]['idx'], lows[0]['idx'])
    end_pivot_idx = max(highs[-1]['idx'], lows[-1]['idx'])
    span = end_pivot_idx - start_idx
    if span < 12:                                    # need ≥~2.5 weeks
        return out
    # Normalize slopes to % of price per bar so thresholds are scale-free.
    price0 = float(df.iloc[start_idx]['close'])
    tsl = tm / price0 * 100
    bsl = bm / price0 * 100
    top_h = float(np.mean([p['price'] for p in highs]))
    bot_l = float(np.mean([p['price'] for p in lows]))
    height = top_h - bot_l
    if height <= 0:
        return out
    FLAT = 0.10          # |slope| < 0.10%/bar ≈ horizontal
    band_top = _line_at(tm, tb, n - 1)
    band_bot = _line_at(bm, bb, n - 1)

    code = name = bias = None
    up_break = down_break = True
    if abs(tsl) < FLAT and bsl > FLAT:
        code, name, bias = 'ascending_triangle', 'Ascending Triangle', 'bullish'
    elif abs(bsl) < FLAT and tsl < -FLAT:
        code, name, bias = 'descending_triangle', 'Descending Triangle', 'bearish'
    elif tsl < -FLAT and bsl > FLAT:
        code, name, bias = 'symmetrical_triangle', 'Symmetrical Triangle', 'neutral'
    elif abs(tsl) < FLAT and abs(bsl) < FLAT:
        trend_in = _trend_before(df, start_idx, 20)
        if trend_in >= 0:
            code, name, bias = 'rectangle_top', 'Rectangle Top', 'neutral'
        else:
            code, name, bias = 'rectangle_bottom', 'Rectangle Bottom', 'neutral'
    elif tsl > FLAT and bsl > FLAT and bsl > tsl:
        code, name, bias = 'rising_wedge', 'Rising Wedge', 'bearish'
    elif tsl < -FLAT and bsl < -FLAT and tsl < bsl:
        code, name, bias = 'falling_wedge', 'Falling Wedge', 'bullish'
    if code is None:
        return out

    # Breakout: a close beyond whichever line broke first after the last pivot.
    conf = None
    direction = None
    for j in range(end_pivot_idx + 1, n):
        c = float(df.iloc[j]['close'])
        if c > _line_at(tm, tb, j) * 1.005:
            conf, direction = j, 'up'
            break
        if c < _line_at(bm, bb, j) * 0.995:
            conf, direction = j, 'down'
            break
    status = 'confirmed' if conf is not None else 'forming'
    end_idx = conf if conf is not None else n - 1

    # Determine bias/target from the (expected or actual) breakout direction.
    expected_up = code in ('ascending_triangle', 'falling_wedge')
    expected_down = code in ('descending_triangle', 'rising_wedge')
    if direction == 'up' or (direction is None and expected_up):
        bo_price = band_top
        target = band_top + height
        bias = 'bullish'
        stop = band_bot * 0.99
        notes = _resistance_notes(df, bo_price, end_pivot_idx, bullish=True)
    elif direction == 'down' or (direction is None and expected_down):
        bo_price = band_bot
        target = band_bot - height
        bias = 'bearish'
        stop = band_top * 1.01
        notes = _support_notes(df, bo_price, end_pivot_idx)
    else:
        # symmetrical / rectangle still forming — present both rails, no target
        bo_price = None
        target = None
        bias = bias if bias != 'neutral' else 'neutral'
        stop = None
        notes = ["Bilateral pattern — wait for the close beyond a rail to set direction."]

    quality = _quality_from(sep_ok=(span >= 20),
                            sym=abs(tsl - bsl) / max(abs(tsl) + abs(bsl), 1) if code == 'symmetrical_triangle' else 0.02,
                            confirmed=(status == 'confirmed'), extra=(span >= 25))
    lines = [
        {'kind': 'resistance', 'points': [_pt(df, highs[0]['idx'], _line_at(tm, tb, highs[0]['idx'])),
                                          _pt(df, end_idx, _line_at(tm, tb, end_idx))]},
        {'kind': 'support', 'points': [_pt(df, lows[0]['idx'], _line_at(bm, bb, lows[0]['idx'])),
                                       _pt(df, end_idx, _line_at(bm, bb, end_idx))]},
    ]
    if target is not None:
        lines.append(_hline(df, target, (conf or end_idx), n - 1, 'target'))
    kps = ([_pt(df, p['idx'], p['price'], 'H') for p in highs]
           + [_pt(df, p['idx'], p['price'], 'L') for p in lows])
    plain_map = {
        'ascending_triangle': "Flat resistance with rising lows — buyers keep paying up. Breaks up ~70% of the time.",
        'descending_triangle': "Flat support with falling highs — sellers pressing down. Usually breaks down.",
        'symmetrical_triangle': "Converging highs and lows (a coil). Direction is decided by the breakout — trade the close beyond a rail.",
        'rectangle_top': "A trading range after an up-move; horizontal support & resistance. Trade the rail that breaks.",
        'rectangle_bottom': "A trading range after a down-move; horizontal support & resistance. An up-break is the reversal.",
        'rising_wedge': "Two up-sloping lines converging — a tiring rally. Usually resolves DOWN.",
        'falling_wedge': "Two down-sloping lines converging — selling exhausts. Usually resolves UP.",
    }
    out.append(_make(
        df, code, name, 'continuation' if 'rectangle' in code or 'triangle' in code else 'reversal',
        bias, status, key_points=kps, lines=lines,
        start_idx=start_idx, end_idx=end_idx, breakout_idx=conf,
        breakout_price=bo_price, target=target, stop=stop,
        height_pct=height / bot_l * 100, plain=plain_map[code],
        quality_notes=notes, quality_score=quality,
    ))
    return out


# --------------------------------------------------------------------------- #
# DETECTORS — flag / pennant / high-tight-flag (flagpole based)
# --------------------------------------------------------------------------- #

def detect_flag_pennant(df) -> List[dict]:
    """A steep 'flagpole' run, then a short (≤3 week) consolidation. If the
    pole roughly DOUBLED price in ≤2 months → High-and-Tight Flag."""
    out = []
    n = len(df)
    if n < 25:
        return out
    close = df['close'].to_numpy(dtype=float)
    last = close[-1]

    # Consolidation = the last 5-15 bars with a tight range.
    for cons_len in (10, 12, 8, 15):
        if n < cons_len + 15:
            continue
        cons = df.iloc[n - cons_len:]
        cons_hi = float(cons['high'].max())
        cons_lo = float(cons['low'].min())
        if cons_lo <= 0:
            continue
        cons_range = (cons_hi - cons_lo) / cons_lo
        if cons_range > 0.13:                     # not a tight consolidation
            continue
        pole_end = n - cons_len
        # find the pole start: strongest run in the ~28 bars before consolidation
        pole_start = max(0, pole_end - 28)
        base_price = float(df['low'].iloc[pole_start:pole_end].min())
        pole_top = float(df['high'].iloc[pole_start:pole_end].max())
        if base_price <= 0:
            continue
        pole_gain = (pole_top - base_price) / base_price
        pole_bars = pole_end - pole_start
        if pole_gain < 0.20:                      # need a real flagpole
            continue
        # the consolidation must sit AT the top of the pole, not have already
        # run away above it (that's a trend, not a flag).
        if cons_hi > pole_top * 1.03:
            continue
        # breakout above the consolidation high
        conf = _confirm_close_above(df, cons_hi, n - cons_len)
        status = 'confirmed' if conf is not None else 'forming'
        if status == 'forming' and last < cons_hi * 0.97:
            continue
        end_idx = conf if conf is not None else n - 1
        htf = pole_gain >= 0.90 and pole_bars <= 44
        if htf:
            code, name = 'high_tight_flag', 'High-and-Tight Flag'
            target = cons_lo + (pole_top - base_price) / 2.0    # half the doubling move
        else:
            code, name = 'flag', 'Flag'
            target = cons_hi + (pole_top - base_price)          # full pole height
        notes = _resistance_notes(df, cons_hi, n - cons_len, bullish=True)
        if htf:
            notes.insert(0, "Price roughly doubled into this flag — Bulkowski's #1 bullish pattern (0% failure, +69% avg).")
        quality = _quality_from(sep_ok=True, sym=0.02, confirmed=(status == 'confirmed'),
                                extra=htf or pole_gain >= 0.4)
        out.append(_make(
            df, code, name, 'continuation', 'bullish', status,
            key_points=[_pt(df, pole_start, base_price, 'pole base'),
                        _pt(df, pole_end - 1, pole_top, 'pole top')],
            lines=[_hline(df, cons_hi, n - cons_len, end_idx, 'resistance'),
                   _hline(df, cons_lo, n - cons_len, end_idx, 'support'),
                   _hline(df, target, (conf or end_idx), n - 1, 'target')],
            start_idx=pole_start, end_idx=end_idx, breakout_idx=conf,
            breakout_price=cons_hi, target=target, stop=cons_lo * 0.98,
            height_pct=pole_gain * 100,
            plain=(f"A sharp {pole_gain*100:.0f}% run (the flagpole) then a tight pause. "
                   f"A close above {cons_hi:.2f} resumes the advance."
                   + (" Because price doubled, this is a High-and-Tight Flag — the strongest bullish setup in the book."
                      if htf else "")),
            quality_notes=notes, quality_score=quality,
        ))
        break   # one flag is enough
    return out


# --------------------------------------------------------------------------- #
# DETECTORS — rounding bottom / cup-with-handle (curvature based)
# --------------------------------------------------------------------------- #

def detect_rounding_cup(df, pivots) -> List[dict]:
    """A smooth U-shaped saucer over ~2-8 months. If a short pullback
    ('handle') sits on the right lip, it's a Cup with Handle."""
    out = []
    n = len(df)
    if n < 50:
        return out
    lookback = min(180, n - 1)
    seg = df.iloc[n - lookback:].reset_index(drop=True)
    closes = seg['close'].to_numpy(dtype=float)
    L = len(closes)
    x = np.arange(L)
    # Fit a parabola; a U-shape has positive curvature and a bottom mid-way.
    try:
        a, b, c = np.polyfit(x, closes, 2)
    except Exception:
        return out
    if a <= 0:
        return out
    vertex = -b / (2 * a)
    if not (L * 0.3 <= vertex <= L * 0.7):        # bottom must sit in the middle
        return out
    # goodness of fit
    fit = a * x * x + b * x + c
    ss_res = float(np.sum((closes - fit) ** 2))
    ss_tot = float(np.sum((closes - closes.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    if r2 < 0.5:
        return out
    left_lip = float(seg['high'].iloc[:5].max())
    right_lip = float(seg['high'].iloc[-15:].max())
    cup_low = float(seg['low'].min())
    if cup_low <= 0 or _pct_diff(left_lip, right_lip) > 0.15:
        return out
    depth = right_lip - cup_low
    if depth / cup_low < 0.15:                     # cup too shallow
        return out
    start_idx = n - lookback
    last = float(df.iloc[-1]['close'])
    # handle: a small pullback in the last ~15 bars staying in the upper half
    recent_lo = float(df['low'].iloc[n - 15:].min())
    has_handle = recent_lo > cup_low + depth * 0.5 and last < right_lip
    rim = right_lip
    conf = _confirm_close_above(df, rim, n - 15)
    status = 'confirmed' if conf is not None else 'forming'
    if status == 'forming' and last < rim * 0.96:
        return out
    end_idx = conf if conf is not None else n - 1
    if has_handle:
        code, name = 'cup_with_handle', 'Cup with Handle'
        target = rim + depth / 2.0                 # half-depth (Bulkowski: hits 76%)
    else:
        code, name = 'rounding_bottom', 'Rounding Bottom'
        target = rim + depth
    notes = _resistance_notes(df, rim, n - 15, bullish=True)
    quality = _quality_from(sep_ok=True, sym=1 - r2, confirmed=(status == 'confirmed'),
                            extra=(r2 >= 0.7))
    out.append(_make(
        df, code, name, 'reversal', 'bullish', status,
        key_points=[_pt(df, start_idx, left_lip, 'left lip'),
                    _pt(df, n - lookback + int(vertex), cup_low, 'base'),
                    _pt(df, n - 1, right_lip, 'right lip')],
        lines=[_hline(df, rim, start_idx, end_idx, 'resistance'),
               _hline(df, target, (conf or end_idx), n - 1, 'target')],
        start_idx=start_idx, end_idx=end_idx, breakout_idx=conf,
        breakout_price=rim, target=target, stop=cup_low * 0.99,
        height_pct=depth / cup_low * 100,
        plain=(f"A long, smooth U-shaped base bottoming near {cup_low:.2f} and recovering to "
               f"the {rim:.2f} rim." + (" A shallow handle has formed on the right lip — "
               "a classic Cup with Handle; buy the rim breakout." if has_handle
               else " A close above the rim signals the base is complete.")),
        quality_notes=notes, quality_score=quality,
    ))
    return out


# --------------------------------------------------------------------------- #
# DETECTORS — pipe bottom / top (two adjacent spikes)
# --------------------------------------------------------------------------- #

def detect_pipes(df) -> List[dict]:
    """Two adjacent long parallel spikes. Bulkowski uses a weekly chart; on
    daily bars we approximate with a 2-bar spike that stands out from the
    surrounding range — a fast V-reversal."""
    out = []
    n = len(df)
    if n < 30:
        return out
    look = 6                                        # how far back to search for the spike
    for direction in ('bottom', 'top'):
        for start in range(n - look, n - 1):
            if start < 22:
                continue
            b1, b2 = df.iloc[start], df.iloc[start + 1]
            prior = df.iloc[start - 20:start]
            avg_rng = float((prior['high'] - prior['low']).mean())
            if avg_rng <= 0:
                continue
            if direction == 'bottom':
                spike = min(float(b1['low']), float(b2['low']))
                depth = min(float(prior['low'].min()), spike)
                # both bars poke well below and overlap
                r1 = float(b1['high'] - b1['low'])
                r2 = float(b2['high'] - b2['low'])
                if not (r1 > 1.5 * avg_rng and r2 > 1.5 * avg_rng):
                    continue
                if _pct_diff(float(b1['low']), float(b2['low'])) > 0.05:
                    continue
                top = max(float(b1['high']), float(b2['high']))
                conf = _confirm_close_above(df, top, start + 1)
                status = 'confirmed' if conf is not None else 'forming'
                if status == 'forming' and float(df.iloc[-1]['close']) < top * 0.97:
                    continue
                end_idx = conf if conf is not None else n - 1
                height = top - spike
                target = top + height
                notes = _resistance_notes(df, top, start + 1, bullish=True)
                quality = _quality_from(sep_ok=True, sym=_pct_diff(float(b1['low']), float(b2['low'])),
                                        confirmed=(status == 'confirmed'), extra=True)
                out.append(_make(
                    df, 'pipe_bottom', 'Pipe Bottom', 'reversal', 'bullish', status,
                    key_points=[_pt(df, start, float(b1['low']), 'spike 1'),
                                _pt(df, start + 1, float(b2['low']), 'spike 2')],
                    lines=[_hline(df, top, start, end_idx, 'neckline'),
                           _hline(df, target, (conf or end_idx), n - 1, 'target')],
                    start_idx=start, end_idx=end_idx, breakout_idx=conf,
                    breakout_price=top, target=target, stop=spike * 0.99,
                    height_pct=height / spike * 100,
                    plain=(f"Two adjacent downward spikes to ~{spike:.2f} — a sharp V washout. "
                           f"Bulkowski ranks pipe bottoms 2nd of 23 bullish patterns (+45% avg). "
                           f"A close above {top:.2f} confirms."),
                    quality_notes=notes, quality_score=quality,
                ))
            else:
                r1 = float(b1['high'] - b1['low'])
                r2 = float(b2['high'] - b2['low'])
                if not (r1 > 1.5 * avg_rng and r2 > 1.5 * avg_rng):
                    continue
                if _pct_diff(float(b1['high']), float(b2['high'])) > 0.05:
                    continue
                peak = max(float(b1['high']), float(b2['high']))
                bot = min(float(b1['low']), float(b2['low']))
                conf = _confirm_close_below(df, bot, start + 1)
                status = 'confirmed' if conf is not None else 'forming'
                if status == 'forming' and float(df.iloc[-1]['close']) > bot * 1.03:
                    continue
                end_idx = conf if conf is not None else n - 1
                height = peak - bot
                target = bot - height
                notes = _support_notes(df, bot, start + 1)
                quality = _quality_from(sep_ok=True, sym=_pct_diff(float(b1['high']), float(b2['high'])),
                                        confirmed=(status == 'confirmed'), extra=True)
                out.append(_make(
                    df, 'pipe_top', 'Pipe Top', 'reversal', 'bearish', status,
                    key_points=[_pt(df, start, float(b1['high']), 'spike 1'),
                                _pt(df, start + 1, float(b2['high']), 'spike 2')],
                    lines=[_hline(df, bot, start, end_idx, 'neckline'),
                           _hline(df, target, (conf or end_idx), n - 1, 'target')],
                    start_idx=start, end_idx=end_idx, breakout_idx=conf,
                    breakout_price=bot, target=target, stop=peak * 1.01,
                    height_pct=height / peak * 100,
                    plain=(f"Two adjacent upward spikes to ~{peak:.2f} — a sharp blow-off. "
                           f"A close below {bot:.2f} confirms the top."),
                    quality_notes=notes, quality_score=quality,
                ))
    return _dedupe_recent(df, out)


# --------------------------------------------------------------------------- #
# DETECTOR — dead-cat bounce (event warning)
# --------------------------------------------------------------------------- #

def detect_dead_cat_bounce(df) -> List[dict]:
    """A ≥15% single-session plunge (usually gapped, huge volume). Bulkowski:
    after the inevitable ~28% bounce over ~3 weeks, price breaks BELOW the
    event low 67% of the time and falls a further ~18%. This is a WARNING,
    not a buy — and it blocks bullish setups for 6 months."""
    out = []
    n = len(df)
    if n < 25:
        return out
    for i in range(n - 40, n):
        if i < 21:
            continue
        prev_close = float(df.iloc[i - 1]['close'])
        low = float(df.iloc[i]['low'])
        close = float(df.iloc[i]['close'])
        if prev_close <= 0:
            continue
        drop = (prev_close - low) / prev_close
        close_drop = (prev_close - close) / prev_close
        if drop < 0.15:
            continue
        rvol = _rvol_at(df, i)
        # bounce so far
        post = df.iloc[i:]
        bounce_hi = float(post['high'].max())
        event_low = float(post['low'].min())
        bounce_pct = (bounce_hi - event_low) / event_low * 100 if event_low > 0 else 0
        last = float(df.iloc[-1]['close'])
        below_event = last < event_low * 1.01
        notes = [
            "After the bounce, price closes BELOW the event low ~67% of the time and falls a further ~18%.",
            "Bulkowski's rule: do NOT trade any bullish chart pattern within 6 months of a dead-cat bounce.",
        ]
        if rvol >= 3:
            notes.append(f"Plunge came on {rvol:.1f}× volume — capitulation.")
        plain = (f"Price collapsed {close_drop*100:.0f}% in one session (intraday −{drop*100:.0f}%). "
                 f"That's a dead-cat bounce event. Expect a partial bounce (~28% avg over ~3 weeks) that "
                 f"tends to fail. {'Price has already bounced ~%.0f%% off the low. ' % bounce_pct if bounce_pct>5 else ''}"
                 f"Treat rallies as exits, not entries.")
        out.append(_make(
            df, 'dead_cat_bounce', 'Dead-Cat Bounce', 'event', 'bearish',
            'confirmed', key_points=[_pt(df, i, low, 'plunge')],
            lines=[_hline(df, event_low, i, n - 1, 'support')],
            start_idx=i, end_idx=n - 1, breakout_idx=i, breakout_price=close,
            target=event_low * 0.82, stop=None, height_pct=drop * 100,
            plain=plain, quality_notes=notes, quality_score=0.9,
        ))
        break
    return out


# --------------------------------------------------------------------------- #
# Quality / context helper functions
# --------------------------------------------------------------------------- #

def _quality_from(sep_ok: bool, sym: float, confirmed: bool, extra: bool) -> float:
    """Blend a few geometric quality signals into 0..1. `sym` is a
    dissimilarity fraction (lower = better symmetry)."""
    q = 0.45
    if sep_ok:
        q += 0.12
    q += max(0.0, 0.18 * (1 - min(sym / 0.06, 1.0)))     # tight symmetry rewarded
    if confirmed:
        q += 0.15
    if extra:
        q += 0.10
    return min(1.0, q)


def _hline(df, price, i0, i1, kind) -> dict:
    return {'kind': kind,
            'points': [{'date': _date_str(df.iloc[i0]['date']), 'price': round(float(price), 3)},
                       {'date': _date_str(df.iloc[i1]['date']), 'price': round(float(price), 3)}]}


def _resistance_notes(df, breakout_price, idx, bullish=True) -> List[str]:
    """Warn about overhead resistance that could trigger a throwback."""
    notes: List[str] = []
    look = df.iloc[max(0, idx - 120):idx]
    if look.empty:
        return notes
    highs_above = look[look['high'] > breakout_price * 1.02]['high']
    if len(highs_above) >= 3:
        lvl = float(highs_above.min())
        if lvl < breakout_price * 1.15:
            notes.append(f"Overhead resistance near {lvl:.2f} — throwbacks hurt these patterns; "
                         f"watch for a stall on the first push.")
    return notes


def _support_notes(df, breakout_price, idx) -> List[str]:
    notes: List[str] = []
    look = df.iloc[max(0, idx - 120):idx]
    if look.empty:
        return notes
    lows_below = look[look['low'] < breakout_price * 0.98]['low']
    if len(lows_below) >= 3:
        lvl = float(lows_below.max())
        if lvl > breakout_price * 0.85:
            notes.append(f"Underlying support near {lvl:.2f} — pullbacks hurt tops; the decline "
                         f"may stall there.")
    return notes


def _dedupe_recent(df, patterns: List[dict]) -> List[dict]:
    """Keep only the most recent instance of each pattern code (the actionable
    one), and drop anything whose activity ended long ago."""
    n = len(df)
    by_code: Dict[str, dict] = {}
    for p in patterns:
        if n - 1 - p['_end_idx'] > RECENCY_BARS:
            continue
        prev = by_code.get(p['code'])
        if prev is None or p['_end_idx'] > prev['_end_idx']:
            by_code[p['code']] = p
    return list(by_code.values())


# Higher = more trustworthy / specific; wins ties when two patterns describe the
# same swing region. Broad "staircase" patterns rank lowest so a genuine double
# bottom / H&S in the same region supersedes them.
PRIORITY: Dict[str, int] = {
    'dead_cat_bounce': 100,
    'high_tight_flag': 95, 'hs_top': 90, 'hs_bottom': 90,
    'pipe_bottom': 85, 'pipe_top': 85,
    'double_bottom_ee': 80, 'double_bottom_aa': 80, 'double_bottom_ae': 80, 'double_bottom_ea': 80,
    'double_top_ee': 80, 'double_top_aa': 80, 'double_top_ae': 80, 'double_top_ea': 80,
    'cup_with_handle': 78, 'rounding_bottom': 76,
    'triple_bottom': 72, 'triple_top': 72,
    'ascending_triangle': 68, 'descending_triangle': 68, 'symmetrical_triangle': 66,
    'rectangle_bottom': 64, 'rectangle_top': 64,
    'falling_wedge': 60, 'rising_wedge': 60,
    'flag': 58, 'pennant': 56,
    'three_rising_valleys': 40, 'three_falling_peaks': 40,
}

# How fresh a confirmed breakout must be to still be "actionable now".
CONFIRM_RECENCY_BARS = 25
MAX_PATTERNS = 6


def _actionable(df, p: dict) -> bool:
    """Only surface patterns a trader could act on today: a confirmed breakout
    within the last few weeks, or a pattern still forming at the latest bar.
    This is what culls the pile of old, played-out formations."""
    n = len(df)
    if p['code'] == 'dead_cat_bounce':
        return True
    if p['status'] == 'confirmed':
        bidx = p.get('_breakout_idx')
        return bidx is not None and bidx >= n - 1 - CONFIRM_RECENCY_BARS
    # forming — geometry must reach essentially the current bar
    return p['_end_idx'] >= n - 1 - 2


def _finalize(df, patterns: List[dict]) -> List[dict]:
    """Filter to actionable patterns, then greedily de-overlap: one swing
    region yields ONE pattern (the highest-priority / best-quality), not the
    four loosely-fitting formations that share those pivots."""
    cand = [p for p in patterns if _actionable(df, p)]
    # Bulkowski's rule: don't trade a bullish chart pattern within ~6 months of
    # a dead-cat bounce. If one is in force, suppress the bullish formations.
    if any(p['code'] == 'dead_cat_bounce' for p in cand):
        cand = [p for p in cand if p['bias'] != 'bullish' or p['code'] == 'dead_cat_bounce']
    cand.sort(key=lambda p: (p['status'] == 'confirmed',
                             PRIORITY.get(p['code'], 50), p['_quality']), reverse=True)
    chosen: List[dict] = []
    for p in cand:
        if p['code'] == 'dead_cat_bounce':
            chosen.append(p)
            continue
        s0, e0 = p['_start_idx'], p['_end_idx']
        span0 = max(1, e0 - s0)
        clash = False
        for q in chosen:
            if q['code'] == 'dead_cat_bounce':
                continue
            s1, e1 = q['_start_idx'], q['_end_idx']
            inter = max(0, min(e0, e1) - max(s0, s1))
            if inter / min(span0, max(1, e1 - s1)) > 0.5:
                clash = True
                break
        if not clash:
            chosen.append(p)
        if len(chosen) >= MAX_PATTERNS:
            break
    return chosen


# --------------------------------------------------------------------------- #
# Public analyzer
# --------------------------------------------------------------------------- #

class PatternAnalyzer:
    """Detect classical chart patterns for one ticker's OHLCV history."""

    def analyze(self, df: pd.DataFrame) -> dict:
        df = clean_history(df)
        if len(df) < MIN_HISTORY_DAYS:
            return {'chart_patterns': [], 'chart_pattern_summary': None}

        # Two zigzag resolutions: a tight one for shorter formations, a wide
        # one for the big multi-month reversals.
        price = float(df.iloc[-1]['close'])
        pct = 0.06 if price < 20 else 0.05
        pivots_fine = find_pivots(df, pct=pct)
        pivots_wide = find_pivots(df, pct=pct * 1.8)

        patterns: List[dict] = []
        try:
            patterns += detect_double_bottom(df, pivots_fine)
            patterns += detect_double_top(df, pivots_fine)
            patterns += detect_triple(df, pivots_fine, bottom=True)
            patterns += detect_triple(df, pivots_fine, bottom=False)
            patterns += detect_head_shoulders(df, pivots_fine, bottom=True)
            patterns += detect_head_shoulders(df, pivots_fine, bottom=False)
            patterns += detect_three_march(df, pivots_fine, rising=True)
            patterns += detect_three_march(df, pivots_fine, rising=False)
            patterns += detect_trendline_patterns(df, pivots_fine)
            patterns += detect_flag_pennant(df)
            patterns += detect_rounding_cup(df, pivots_wide)
            patterns += detect_pipes(df)
            patterns += detect_dead_cat_bounce(df)
        except Exception as e:               # never let one detector kill the batch
            logger.warning("pattern detection error: %s", e, exc_info=True)

        # Filter to actionable patterns and de-overlap to one-per-region.
        patterns = _finalize(df, patterns)

        summary = self._summarize(patterns)
        # Strip internal fields before returning.
        for p in patterns:
            for k in ('_start_idx', '_end_idx', '_breakout_idx', '_quality'):
                p.pop(k, None)
        return {'chart_patterns': patterns, 'chart_pattern_summary': summary}

    def analyze_ticker_row(self, ticker: str, df: pd.DataFrame) -> Optional[dict]:
        """Analyze one ticker and return a compact, storable row (or None if
        no active chart pattern). Used by the all-ticker scanner."""
        res = self.analyze(df)
        patterns = res['chart_patterns']
        if not patterns:
            return None
        cdf = clean_history(df)
        if cdf.empty:
            return None
        analysis_date = _date_str(cdf.iloc[-1]['date'])
        price = float(cdf.iloc[-1]['close'])
        summary = res['chart_pattern_summary'] or {}
        top = patterns[0]
        return {
            'ticker': ticker,
            'analysis_date': analysis_date,
            'price': round(price, 3),
            'bias': summary.get('bias', top['bias']),
            'confidence': top['confidence'],
            'top_code': top['code'],
            'top_name': top['name'],
            'status': top['status'],
            'target': top.get('target'),
            'target_pct': top.get('target_pct'),
            'pattern_count': len(patterns),
            'confirmed_count': summary.get('confirmed_count', 0),
            'has_dcb': 1 if summary.get('has_dead_cat_bounce') else 0,
            'patterns': patterns,
            'summary': summary,
        }

    def analyze_all(self, db, freshness_window_days: int = 3) -> List[dict]:
        """Scan every ticker we have *fresh* history for and return storable
        rows for those with ≥1 active chart pattern. Mirrors the freshness gate
        used by the candlestick ChartAnalyzer so we don't flag stale months-old
        formations as today's signals."""
        tickers = db.get_all_tickers()
        try:
            from sqlalchemy import text as _text
            row = pd.read_sql_query(_text("SELECT MAX(date) AS m FROM stock_data"), db.engine)
            global_max = row.iloc[0]['m']
        except Exception:
            global_max = None
        global_max_ts = pd.to_datetime(global_max) if global_max else None
        cutoff = (global_max_ts - pd.Timedelta(days=freshness_window_days)
                  if global_max_ts is not None else None)

        rows: List[dict] = []
        skipped = 0
        for t in tickers:
            try:
                df = db.get_stock_data(t)
                if df is None or df.empty:
                    continue
                if cutoff is not None:
                    last_date = pd.to_datetime(df['date'].iloc[-1])
                    if last_date < cutoff:
                        skipped += 1
                        continue
                r = self.analyze_ticker_row(t, df)
                if r:
                    rows.append(r)
            except Exception as e:
                logger.warning("PatternAnalyzer failed for %s: %s", t, e)
                continue
        logger.info("PatternAnalyzer: %d/%d tickers with chart patterns (%d stale skipped)",
                    len(rows), len(tickers), skipped)
        return rows

    def _summarize(self, patterns: List[dict]) -> Optional[dict]:
        if not patterns:
            return None
        dcb = any(p['code'] == 'dead_cat_bounce' for p in patterns)
        bull = [p for p in patterns if p['bias'] == 'bullish']
        bear = [p for p in patterns if p['bias'] == 'bearish']
        confirmed = [p for p in patterns if p['status'] == 'confirmed']
        if dcb:
            bias = 'bearish'
            headline = "Dead-cat-bounce warning in force — bullish setups suppressed for ~6 months."
        elif len(bull) > len(bear):
            bias = 'bullish'
        elif len(bear) > len(bull):
            bias = 'bearish'
        else:
            bias = 'mixed'
        top = patterns[0]
        return {
            'bias': bias,
            'pattern_count': len(patterns),
            'confirmed_count': len(confirmed),
            'has_dead_cat_bounce': dcb,
            'top_pattern': top['name'],
            'top_confidence': top['confidence'],
            'headline': headline if dcb else (
                f"{top['name']} ({top['status']}) is the dominant formation — "
                f"{top['confidence']} confidence, "
                f"{'target ' + str(top['target']) if top.get('target') else 'no target yet'}."),
        }
