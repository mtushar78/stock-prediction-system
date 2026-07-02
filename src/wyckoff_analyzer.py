"""Wyckoff Method analyzer — accumulation structures on daily OHLCV.

Implements the operational method from "The Wyckoff Methodology in Depth"
(Rubén Villahermosa, docs/_wyckoff.txt) — the market-structure framework built
for operator-driven markets, which is what DSE is (docs/WINNER_ANATOMY.md found
winners launch as quiet accumulation "coiled springs"; deep-dive mapping in
docs/PROFITABILITY_AUDIT.md).

What is detected (long side only — DSE has no short selling):

  TRADING RANGE  — lateral structure after a meaningful decline (accumulation
                   context: the "cause" of the Law of Cause & Effect).
  SPRING         — Phase C shake: price penetrates range support then closes
                   back inside. Classified by the book's three types via the
                   volume on the undercut (#3 low-vol = exhaustion of supply,
                   enterable directly; #1/#2 high-vol = must wait for a test).
  SPRING TEST    — the book's preferred entry: after a shake, a narrow-range
                   bar holding above the spring low with volume LOWER THAN THE
                   PREVIOUS TWO CANDLES (the explicit "no supply" rule).
  BUEC           — Phase D confirmation: Sign of Strength closes above range
                   resistance (the Creek), then a low-volume back-up holds
                   above it without re-entering the range.

Stops per the book: spring entries below the spring low; BUEC below the creek.
Target from Cause & Effect: range height projected above the creek.

Pure functions on a DataFrame with columns date/open/high/low/close/volume —
no I/O, no state — so the exact same code is backtested (wyckoff_study.py),
falsification-tested (verify_wyckoff.py) and run in production (analyzer.py).
"""
from typing import Dict, Optional

import numpy as np
import pandas as pd

# ---- structure parameters (validated in wyckoff_study.py) ----
RANGE_WINDOW = 45        # bars that must form the lateral structure (the cause)
RANGE_EXCLUDE = 10       # most-recent bars excluded from support/resistance
                         # (they may BE the shake/test/back-up being evaluated;
                         # must cover TEST_MAX_BARS and SOS_MAX_AGE)
RANGE_MAX_HEIGHT = 30.0  # % max height of the trading range
RANGE_MIN_HEIGHT = 5.0   # % min height (else support/resistance meaningless)
DOWNTREND_MIN_PCT = 12.0  # % decline into the range (accumulation, not re-acc)
DOWNTREND_LOOKBACK = 120  # bars before the range in which the decline happened
SPRING_MAX_DEPTH = 12.0  # % max penetration below support (deeper = breakdown)
SPRING_RECENT_BARS = 3   # undercut must have happened within this many bars
SPRING_LOWVOL_RVOL = 1.2  # undercut rvol below this = Spring #3 (supply gone)
TEST_MAX_BARS = 10       # bars after a spring in which a test can complete
SOS_MAX_AGE = 10         # bars since the SOS close above the creek (for BUEC)
BUEC_TOLERANCE = 3.0     # % the back-up may dip below the creek intrabar
MIN_AVG_VOL20 = 50000    # same liquidity floor as breakout/reversal signals
MIN_PRICE = 5.0


def _round(x, nd=2):
    try:
        v = float(x)
        return round(v, nd) if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def find_trading_range(df: pd.DataFrame, end_idx: int) -> Optional[Dict]:
    """Locate an accumulation trading range ending at end_idx (inclusive).

    The range is the RANGE_WINDOW bars before the last RANGE_EXCLUDE bars.
    Requires (a) lateral: height within [RANGE_MIN_HEIGHT, RANGE_MAX_HEIGHT],
    (b) a prior decline of >= DOWNTREND_MIN_PCT into the range (accumulation
    context — the downtrend Phase A must have stopped).
    Returns {'support','resistance','height_pct','start_idx','end_idx'} or None.
    """
    lo_i = end_idx - RANGE_EXCLUDE - RANGE_WINDOW + 1
    hi_i = end_idx - RANGE_EXCLUDE
    if lo_i < DOWNTREND_LOOKBACK:
        return None
    window = df.iloc[lo_i:hi_i + 1]
    support = float(window['low'].min())
    resistance = float(window['high'].max())
    if support <= 0:
        return None
    height_pct = (resistance - support) / support * 100
    if not (RANGE_MIN_HEIGHT <= height_pct <= RANGE_MAX_HEIGHT):
        return None
    # Accumulation context: price fell into this range (PS/SC territory).
    before = df.iloc[max(0, lo_i - DOWNTREND_LOOKBACK):lo_i]
    if before.empty:
        return None
    peak_before = float(before['high'].max())
    if peak_before <= 0:
        return None
    decline_pct = (peak_before - support) / peak_before * 100
    if decline_pct < DOWNTREND_MIN_PCT:
        return None
    return {
        'support': support,
        'resistance': resistance,
        'height_pct': height_pct,
        'decline_pct': decline_pct,
        'start_idx': lo_i,
        'end_idx': hi_i,
    }


def detect_wyckoff_long(df: pd.DataFrame) -> Dict:
    """Evaluate the LAST bar of df for a Wyckoff long entry.

    Returns {'is_wyckoff': bool, 'event': 'SPRING'|'SPRING_TEST'|'BUEC'|None,
             'reasons': [...], 'checks': {...}} — same contract style as
    analyzer.calculate_reversal_signal so it slots into the signal pipeline.
    Uses ONLY bars in df (call with history truncated at the evaluation date).
    """
    out = {'is_wyckoff': False, 'event': None, 'reasons': [], 'checks': {}}
    # DSE stores non-trading days as zero-price stub rows — they would corrupt
    # the range support (low=0). Same clean rule as the pattern engine.
    df = df[(df['close'] > 0) & (df['low'] > 0) & (df['high'] > 0)]
    n = len(df)
    need = DOWNTREND_LOOKBACK + RANGE_WINDOW + RANGE_EXCLUDE + 1
    if n < need:
        out['reasons'].append(f'Insufficient history ({n} < {need} bars)')
        return out

    df = df.reset_index(drop=True)
    i = n - 1
    close = df['close'].to_numpy(float)
    low = df['low'].to_numpy(float)
    high = df['high'].to_numpy(float)
    vol = df['volume'].to_numpy(float)

    # Liquidity floor (identical to the breakout/reversal gates).
    avg_vol20 = float(np.mean(vol[max(0, i - 20):i])) if i >= 1 else 0.0
    rvol = vol[i] / avg_vol20 if avg_vol20 > 0 else 0.0
    out['checks']['avg_vol20'] = int(avg_vol20)
    out['checks']['rvol'] = _round(rvol)
    out['checks']['close'] = _round(close[i])
    if avg_vol20 < MIN_AVG_VOL20:
        out['reasons'].append('Thin (20d avg vol < %d)' % MIN_AVG_VOL20)
        return out
    if close[i] < MIN_PRICE:
        out['reasons'].append('Price < %g (penny/MF unit)' % MIN_PRICE)
        return out

    tr = find_trading_range(df, i)
    if tr is None:
        out['reasons'].append('No accumulation trading range '
                              '(lateral structure after a decline)')
        return out
    support, resistance = tr['support'], tr['resistance']
    out['checks'].update({
        'support': _round(support), 'resistance': _round(resistance),
        'range_height_pct': _round(tr['height_pct'], 1),
        'decline_into_range_pct': _round(tr['decline_pct'], 1),
    })

    # ---- SPRING: undercut of support in the last SPRING_RECENT_BARS bars,
    #      with TODAY's close back inside the range. --------------------------
    spring_idx = None
    for j in range(i, max(tr['end_idx'], i - SPRING_RECENT_BARS), -1):
        if low[j] < support:
            spring_idx = j
            break
    if spring_idx is not None:
        depth_pct = (support - low[spring_idx]) / support * 100
        under_rvol = (vol[spring_idx] / avg_vol20) if avg_vol20 > 0 else 0.0
        recovered = close[i] > support
        out['checks'].update({
            'spring_low': _round(low[spring_idx]),
            'spring_depth_pct': _round(depth_pct, 1),
            'spring_rvol': _round(under_rvol),
            'recovered': bool(recovered),
        })
        if depth_pct > SPRING_MAX_DEPTH:
            out['reasons'].append(
                f'Undercut too deep ({depth_pct:.0f}% > {SPRING_MAX_DEPTH:.0f}%'
                ' below support — breakdown, not a spring)')
            return out
        if not recovered:
            out['reasons'].append('Broke support but has not closed back '
                                  'inside the range (no recovery yet)')
            return out
        if under_rvol < SPRING_LOWVOL_RVOL:
            # Spring #3 — supply exhausted; the book allows a direct entry.
            out['is_wyckoff'] = True
            out['event'] = 'SPRING'
            out['checks']['spring_type'] = 3
            out['checks']['stop'] = _round(low[spring_idx] * 0.99)
            out['checks']['target'] = _round(
                resistance * (1 + tr['height_pct'] / 100))
            return out
        # Spring #1/#2 — high-volume shake: supply present, wait for the test.
        # Today can BE that test if it already satisfies the no-supply rule.
        out['checks']['spring_type'] = 1 if under_rvol >= 2.0 else 2

    # ---- SPRING TEST: a prior spring within TEST_MAX_BARS bars, today holds
    #      above the spring low on "no supply" volume (< previous two bars). --
    prior_spring = None
    for j in range(i - 1, max(tr['end_idx'] - 1, i - TEST_MAX_BARS - 1), -1):
        if low[j] < support:
            # recovery required: some later bar closed back above support
            if any(close[k] > support for k in range(j, i)):
                prior_spring = j
            break
    if prior_spring is not None and i - prior_spring >= 2:
        no_supply = vol[i] < vol[i - 1] and vol[i] < vol[i - 2]
        held = low[i] >= low[prior_spring] and close[i] > support
        out['checks'].update({
            'test_no_supply_vol': bool(no_supply),
            'test_held_above_spring': bool(held),
        })
        if no_supply and held:
            out['is_wyckoff'] = True
            out['event'] = 'SPRING_TEST'
            out['checks']['spring_low'] = _round(low[prior_spring])
            out['checks']['stop'] = _round(low[prior_spring] * 0.99)
            out['checks']['target'] = _round(
                resistance * (1 + tr['height_pct'] / 100))
            return out

    # ---- BUEC: SOS close above the creek within SOS_MAX_AGE bars, and today
    #      is a low-volume back-up holding above it (no re-entry). ------------
    sos_idx = None
    for j in range(i - 1, max(tr['end_idx'], i - SOS_MAX_AGE - 1), -1):
        if close[j] > resistance and close[j - 1] <= resistance:
            sos_idx = j
            break
    if sos_idx is not None:
        sos_rvol = (vol[sos_idx] / avg_vol20) if avg_vol20 > 0 else 0.0
        pulled_back = low[i] <= resistance * (1 + BUEC_TOLERANCE / 100)
        holds = (close[i] > resistance * (1 - BUEC_TOLERANCE / 100)
                 and close[i] > support)
        no_supply = vol[i] < vol[i - 1] and vol[i] < vol[i - 2]
        out['checks'].update({
            'sos_rvol': _round(sos_rvol),
            'buec_pulled_back': bool(pulled_back),
            'buec_holds': bool(holds),
            'buec_no_supply_vol': bool(no_supply),
        })
        if pulled_back and holds and no_supply:
            out['is_wyckoff'] = True
            out['event'] = 'BUEC'
            out['checks']['stop'] = _round(support)
            out['checks']['target'] = _round(
                resistance * (1 + tr['height_pct'] / 100))
            return out

    if not out['reasons']:
        out['reasons'].append('Trading range present but no spring, '
                              'spring test, or back-up entry today')
    return out
