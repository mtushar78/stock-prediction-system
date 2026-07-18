"""Momentum scanner — the "Stage-2 momentum watchlist" (techno-funda).

Implements the medium-term momentum framework the user distilled from three
DSE-focused strategy videos (docs/fromVideos/*): filter the ~400-name universe
down to a small, slow-moving watchlist of fundamentally clean stocks that are in
an *early Stage-2 advance* on the MONTHLY chart, then time entries on the DAILY
chart with a volume-backed breakout trigger.

The pipeline, top to bottom:

  1. MONTHLY structure (Stan Weinstein stage analysis). Resample each ticker's
     daily bars to monthly candles and classify the macro stage from the 10- and
     20-month moving averages: Stage 1 (basing) → Stage 2 (advancing) → Stage 3
     (topping) → Stage 4 (declining). The prize is EARLY STAGE 2 — a fresh
     break out of a long base, the "launchpad" the videos describe.

  2. DAILY trend state. Compute the 10/20/50/200-day SMA stack and classify the
     alignment (STACKED_BULL = price>10>20>50>200). Detect a "launchpad" — the
     10/20/50 SMAs compressing into a tight cluster (volatility dried up) — and
     the daily entry status (TRIGGER / PULLBACK / EXTENDED / WAITING).

  3. TECHNO-FUNDA hygiene. Cross-reference the fundamentals + dividend_history
     tables: A-category, positive EPS, sane P/E, a recent dividend, adequate
     market cap. A stock that passes is tagged techno_funda_pass=True.

  4. SCORE + reasons. A 0-100 blend (stage + monthly structure + daily alignment
     + launchpad + funda quality) with plain-English reasons and a concrete
     entry status, so every row is a decision aid, not a data dump.

IMPORTANT HONESTY NOTE: like the rebound scanner, this is a WATCHLIST screen,
not a validated buy signal. DSE's own profitability audit found trend-following
breakouts are ≈breakeven net of costs; the videos' return claims are unverified
marketing. The value here is organisation and discipline (a slow monthly list
you commit to, instead of churning) plus catching Stage-2 launches early to
watch — see backtest_momentum.py for the point-in-time reality check. Nothing
here asserts an edge.

All thresholds are module constants so they are easy to tune.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

# Reuse the corporate-action back-adjustment + Wilder RSI already proven in the
# rebound scanner, so multi-year monthly MAs aren't polluted by ex-date drops and
# the RSI shown here matches the full-analysis modal.
from src.rebound_scanner import _back_adjust, _rsi

logger = logging.getLogger(__name__)

# ---- Universe / liquidity gates (mirror the other scanners) ------------- #
CALENDAR_LOOKBACK_DAYS = 3300   # ~9 years — enough daily history for monthly SMAs
MIN_MONTHS = 30                 # need >=30 monthly candles to trust a 20M SMA + slope
MIN_PRICE = 5.0                 # avoid untradeable penny names
MIN_AVG_VOL20 = 5000            # sanity floor on shares/day
MIN_AVG_TURNOVER_BDT = 500_000  # traded VALUE floor — the real liquidity filter
MAX_STALE_TRADING_DAYS = 5      # must have traded within N of the last session

# ---- Monthly stage-analysis parameters ---------------------------------- #
STAGE_SLOPE_MONTHS = 3          # look-back (months) for the 10M-SMA slope
EARLY_CROSS_MAX_MONTHS = 8      # a "fresh" Stage-2 golden cross is <= this old
EARLY_MAX_EXT_ABOVE_S10 = 25.0  # ...and price isn't already >25% above the 10M SMA
BASE_CEILING_MONTHS = 12        # a Stage-2 breakout clears the prior N-month ceiling

# ---- Daily entry / trend-state parameters ------------------------------- #
BRK_20D_TOL = 0.01              # within 1% of the 20-day high counts as a break
BRK_MAX_EXT_PCT = 12.0          # ...but reject if already >12% above that base
BRK_MIN_RVOL = 1.5              # breakout needs >=1.5x the 20-day avg volume
LAUNCHPAD_MAX_SPREAD_PCT = 4.0  # 10/20/50 daily SMAs within 4% of price = coiled
EXT_ABOVE_SMA20_PCT = 20.0      # >20% above the 20-day SMA = extended (anti-FOMO)
EXT_RET20_PCT = 50.0            # ...or up >50% in 20 sessions
PULLBACK_BAND_PCT = 3.0         # price within +/-3% of a rising 20-day SMA = a dip

# ---- Techno-funda hygiene (Part 3 of the videos) ------------------------ #
FUNDA_MAX_PE = 30.0             # P/E ceiling (skipped for insurers, per the video)
FUNDA_MIN_MCAP_CR = 250.0       # minimum market cap in Crore BDT
FUNDA_DIV_LOOKBACK_YEARS = 3    # "recent dividend" window


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


def _adjusted_daily(df: pd.DataFrame):
    """Return (dates, o, h, l, c, v) as numpy arrays, back-adjusted for corporate
    actions. The latest bar's adjustment factor is always 1.0, so the last close
    equals the raw traded price.
    """
    df = df[df['close'] > 0].sort_values('date').reset_index(drop=True)
    closes_raw = df['close'].to_numpy(dtype=float)
    opens_raw = df['open'].to_numpy(dtype=float)
    highs_raw = df['high'].to_numpy(dtype=float)
    lows_raw = df['low'].to_numpy(dtype=float)
    vols = df['volume'].to_numpy(dtype=float)
    dates = pd.to_datetime(df['date'])

    # DSE stores some bars with close>0 but low/high/open<=0 — repair before use.
    lows_raw = np.where(lows_raw <= 0, closes_raw, lows_raw)
    highs_raw = np.where(highs_raw <= 0, closes_raw, highs_raw)
    opens_raw = np.where((opens_raw <= 0) | np.isnan(opens_raw), closes_raw, opens_raw)

    closes, highs, lows, gap_idx = _back_adjust(closes_raw, highs_raw, lows_raw)
    factor = np.where(closes_raw > 0, closes / closes_raw, 1.0)
    opens = opens_raw * factor
    action_dates = [dates.iloc[i].strftime('%Y-%m-%d') for i in gap_idx]
    return dates, opens, highs, lows, closes, vols, closes_raw, action_dates


def _to_monthly(dates: pd.Series, o, h, l, c, v) -> pd.DataFrame:
    """Aggregate adjusted daily bars into monthly OHLCV candles.

    Uses Period('M') grouping (version-stable, unlike resample('M'/'ME') whose
    alias changed across pandas releases). The last row is the CURRENT, possibly
    partial, month — deliberately kept so the stage read is live.
    """
    d = pd.DataFrame({'date': dates.values, 'open': o, 'high': h, 'low': l,
                      'close': c, 'volume': v})
    d['ym'] = pd.PeriodIndex(pd.to_datetime(d['date']), freq='M')
    g = d.groupby('ym', sort=True)
    m = g.agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'),
              close=('close', 'last'), volume=('volume', 'sum'))
    return m.reset_index()


def _months_since_cross(cross: np.ndarray) -> int | None:
    """How many months the 10M SMA has held above the 20M SMA (None if below)."""
    if len(cross) == 0 or not cross[-1]:
        return None
    k = 0
    for v in reversed(cross):
        if v:
            k += 1
        else:
            break
    return k


def _classify_stage(monthly: pd.DataFrame) -> dict:
    """Weinstein stage from the 10/20-month moving averages.

    Returns a dict with stage code, a human label, confidence and the raw
    booleans (so the caller can build reasons + score). Stages, in the order the
    money is made:
      STAGE_1        basing / accumulation (flat MAs after a decline)
      EARLY_STAGE_2  a FRESH break out of the base — the launchpad (the prize)
      STAGE_2        established advance (price stacked above rising MAs)
      STAGE_3        topping (advance stalling, MAs flattening)
      STAGE_4        declining (price below falling MAs)
      NEUTRAL        none of the above cleanly
    """
    mc = monthly['close'].to_numpy(dtype=float)
    mh = monthly['high'].to_numpy(dtype=float)
    s10 = pd.Series(mc).rolling(10).mean().to_numpy()
    s20 = pd.Series(mc).rolling(20).mean().to_numpy()

    price = float(mc[-1])
    s10_now, s20_now = s10[-1], s20[-1]
    # 3-month slope of the 10M SMA.
    s10_slope = (s10[-1] - s10[-1 - STAGE_SLOPE_MONTHS]
                 if len(s10) > STAGE_SLOPE_MONTHS and not math.isnan(s10[-1 - STAGE_SLOPE_MONTHS])
                 else np.nan)
    s20_slope = (s20[-1] - s20[-1 - STAGE_SLOPE_MONTHS]
                 if len(s20) > STAGE_SLOPE_MONTHS and not math.isnan(s20[-1 - STAGE_SLOPE_MONTHS])
                 else np.nan)

    above10 = not math.isnan(s10_now) and price > s10_now
    above20 = not math.isnan(s20_now) and price > s20_now
    s10_up = not math.isnan(s10_slope) and s10_slope > 0
    s20_up = not math.isnan(s20_slope) and s20_slope > 0
    s10_over_s20 = not math.isnan(s10_now) and not math.isnan(s20_now) and s10_now > s20_now
    s10_flat = not math.isnan(s10_slope) and abs(s10_slope) / price * 100.0 < 4.0

    cross = np.where(np.isnan(s10) | np.isnan(s20), False, s10 > s20)
    since_cross = _months_since_cross(cross)
    ext_above_s10 = (price / s10_now - 1) * 100.0 if above10 and s10_now > 0 else 0.0

    # Prior-base ceiling: highest monthly high over the last year excluding the
    # current month. A Stage-2 breakout clears it.
    prior = mh[-1 - BASE_CEILING_MONTHS:-1] if len(mh) > BASE_CEILING_MONTHS else mh[:-1]
    base_ceiling = float(np.max(prior)) if len(prior) else price
    broke_base = price >= base_ceiling * 0.99

    # ---- Classify (priority order) ----
    stage, label, conf = 'NEUTRAL', 'Neutral / unclear', 'low'
    if above10 and s10_up and s10_over_s20:
        # Advancing. Fresh cross + not-yet-extended + clearing the base = EARLY.
        is_fresh = (since_cross is not None and since_cross <= EARLY_CROSS_MAX_MONTHS)
        if is_fresh and ext_above_s10 <= EARLY_MAX_EXT_ABOVE_S10 and broke_base:
            stage, label = 'EARLY_STAGE_2', 'Early Stage 2 — fresh breakout'
            conf = 'high' if (above20 and s20_up) else 'medium'
        else:
            stage, label = 'STAGE_2', 'Stage 2 — advancing'
            conf = 'high' if (above20 and s20_up and s10_over_s20) else 'medium'
    elif (not above10) and (not s10_up) and (not s10_over_s20):
        stage, label, conf = 'STAGE_4', 'Stage 4 — declining', 'high' if not above20 else 'medium'
    elif s10_flat and abs((price / s10_now - 1) * 100.0) <= 15.0:
        stage, label, conf = 'STAGE_1', 'Stage 1 — basing', 'medium'
    elif above20 and (not s10_up):
        stage, label, conf = 'STAGE_3', 'Stage 3 — topping', 'medium'

    return {
        'stage': stage, 'stage_label': label, 'stage_confidence': conf,
        'sma10_m': _clean(s10_now), 'sma20_m': _clean(s20_now),
        'above_sma10_m': bool(above10), 'above_sma20_m': bool(above20),
        'sma10_m_rising': bool(s10_up), 'sma20_m_rising': bool(s20_up),
        'sma10_over_sma20_m': bool(s10_over_s20),
        'months_since_cross': since_cross,
        'months_of_history': int(len(mc)),
        'base_ceiling': _clean(base_ceiling), 'broke_base': bool(broke_base),
        'ext_above_sma10_m_pct': _clean(ext_above_s10),
    }


def _daily_state(o, h, l, c, v, price_raw: float) -> dict:
    """Daily 10/20/50/200 SMA stack, launchpad detection and entry status."""
    n = len(c)
    sma10 = _sma(c, 10)
    sma20 = _sma(c, 20)
    sma50 = _sma(c, 50)
    sma200 = _sma(c, 200)
    sma20_10ago = _sma_ago(c, 20, 10)
    sma50_10ago = _sma_ago(c, 50, 10)
    price = float(c[-1])
    avg_vol20 = float(v[-20:].mean()) if n >= 20 else float(v.mean())

    s20_up = sma20 is not None and sma20_10ago is not None and sma20 > sma20_10ago
    s50_up = sma50 is not None and sma50_10ago is not None and sma50 > sma50_10ago

    # ---- MA stack alignment ----
    have = all(x is not None for x in (sma10, sma20, sma50, sma200))
    stacked_bull = have and price > sma10 > sma20 > sma50 > sma200
    partial_bull = (sma10 is not None and sma20 is not None and sma50 is not None
                    and price > sma10 > sma20 and price > sma50)
    if stacked_bull:
        ma_stack = 'STACKED_BULL'
    elif partial_bull:
        ma_stack = 'PARTIAL'
    elif sma20 is not None and price > sma20:
        ma_stack = 'ABOVE_20'
    else:
        ma_stack = 'BELOW'

    # ---- Launchpad: 10/20/50 SMAs compressed into a tight cluster ----
    launchpad = False
    cluster_spread_pct = None
    if sma10 is not None and sma20 is not None and sma50 is not None and price > 0:
        cluster = [sma10, sma20, sma50]
        cluster_spread_pct = (max(cluster) - min(cluster)) / price * 100.0
        near_cluster = abs(price - float(np.mean(cluster))) / price * 100.0 <= LAUNCHPAD_MAX_SPREAD_PCT * 1.5
        launchpad = cluster_spread_pct <= LAUNCHPAD_MAX_SPREAD_PCT and near_cluster

    # ---- 20-day-high breakout trigger (the v9 entry rule) ----
    hi20 = float(np.max(h[-21:-1])) if n >= 21 else float(np.max(h[:-1])) if n >= 2 else price
    broke20 = price >= hi20 * (1 - BRK_20D_TOL)
    ext20 = (price / hi20 - 1) * 100.0 if hi20 > 0 else 0.0
    rvol = float(v[-1]) / avg_vol20 if avg_vol20 > 0 else 1.0
    trigger = broke20 and rvol >= BRK_MIN_RVOL and ext20 <= BRK_MAX_EXT_PCT

    # ---- Extended / pullback context ----
    ret20 = (price / float(c[-21]) - 1) * 100.0 if n >= 21 else None
    ext_above_sma20 = (price / sma20 - 1) * 100.0 if sma20 else 0.0
    extended = ext_above_sma20 > EXT_ABOVE_SMA20_PCT or (ret20 is not None and ret20 > EXT_RET20_PCT)
    pullback = (sma20 is not None and s20_up and abs(ext_above_sma20) <= PULLBACK_BAND_PCT
                and sma50 is not None and price > sma50)

    # ---- Entry status (priority: act > watch-coil > buy-dip > too-late > wait) ----
    if trigger:
        entry_status = 'TRIGGER'
    elif launchpad:
        entry_status = 'LAUNCHPAD'
    elif pullback:
        entry_status = 'PULLBACK'
    elif extended:
        entry_status = 'EXTENDED'
    else:
        entry_status = 'WAITING'

    return {
        'sma10': _clean(sma10), 'sma20': _clean(sma20), 'sma50': _clean(sma50),
        'sma200': _clean(sma200),
        'sma20_rising': bool(s20_up), 'sma50_rising': bool(s50_up),
        'ma_stack': ma_stack,
        'launchpad': bool(launchpad),
        'cluster_spread_pct': _clean(cluster_spread_pct),
        'breakout_trigger': bool(trigger),
        'broke_20d_high': bool(broke20),
        'ext_20d_high_pct': _clean(ext20),
        'rvol': _clean(rvol),
        'avg_vol20': int(avg_vol20),
        'ret20_pct': _clean(ret20),
        'ext_above_sma20_pct': _clean(ext_above_sma20),
        'extended': bool(extended),
        'pullback': bool(pullback),
        'entry_status': entry_status,
    }


def _funda_assess(f: dict | None, div_years: list[int] | None, cur_year: int,
                  sector: str | None) -> dict:
    """Techno-funda hygiene from the fundamentals + dividend_history tables.

    Insurers get the P/E gate waived (the video's own exception — life insurers
    don't report standard quarterly EPS). Returns quality points (0-20), a
    techno_funda_pass boolean, and the individual flags for the reasons list.
    """
    def _n(x):
        try:
            v = float(x)
            return v if (v == v and not math.isinf(v)) else None
        except (TypeError, ValueError):
            return None

    cat = ((f or {}).get('market_category') or '').strip().upper()
    eps = _n((f or {}).get('eps'))
    pe = _n((f or {}).get('pe_ratio'))
    mcap_mn = _n((f or {}).get('market_cap'))
    mcap_cr = mcap_mn / 10.0 if mcap_mn else None      # mn -> Crore (matches long-term list)
    is_insurer = bool(sector and 'insurance' in sector.lower())

    recent_div = bool(div_years and max(div_years) >= cur_year - FUNDA_DIV_LOOKBACK_YEARS)

    cat_a = cat == 'A'
    eps_ok = eps is not None and eps > 0
    pe_ok = is_insurer or (pe is not None and 0 < pe <= FUNDA_MAX_PE)
    mcap_ok = mcap_cr is not None and mcap_cr >= FUNDA_MIN_MCAP_CR

    # Techno-funda pass = the video's hard hygiene: A-cat + earnings + a recent
    # dividend + a sane valuation. Market cap is a quality bonus, not a gate
    # (the video itself bypasses it for sound small insurers).
    techno_funda_pass = cat_a and eps_ok and pe_ok and recent_div

    pts = 0.0
    pts += 5.0 if cat_a else 0.0
    pts += 5.0 if eps_ok else 0.0
    pts += 4.0 if pe_ok else 0.0
    pts += 3.0 if recent_div else 0.0
    pts += 3.0 if mcap_ok else 0.0

    return {
        'category': cat or None, 'eps': eps, 'pe': pe,
        'market_cap_cr': round(mcap_cr, 0) if mcap_cr else None,
        'is_insurer': is_insurer,
        'cat_a': cat_a, 'eps_positive': eps_ok, 'pe_ok': pe_ok,
        'mcap_ok': mcap_ok, 'recent_dividend': recent_div,
        'techno_funda_pass': techno_funda_pass,
        'funda_pts': pts,
    }


def _analyze_one(ticker: str, df: pd.DataFrame, sector: str | None,
                 funda: dict | None, div_years: list[int] | None,
                 cur_year: int, stale_cutoff: str | None) -> dict | None:
    """Return a momentum row for `ticker`, or None if it lacks the data / structure."""
    df = df[df['close'] > 0]
    if len(df) < 60:
        return None

    dates, o, h, l, c, v, closes_raw, action_dates = _adjusted_daily(df)
    n = len(c)
    if n < 60:
        return None

    last_date = dates.iloc[-1].strftime('%Y-%m-%d')
    if stale_cutoff is not None and last_date < stale_cutoff:
        return None

    price = float(closes_raw[-1])
    if price < MIN_PRICE:
        return None

    # Liquidity by traded VALUE (shares alone is meaningless on DSE).
    turnover = c * v
    avg_turnover20 = float(turnover[-20:].mean()) if n >= 20 else float(turnover.mean())
    avg_vol20 = float(v[-20:].mean()) if n >= 20 else float(v.mean())
    if avg_turnover20 < MIN_AVG_TURNOVER_BDT or avg_vol20 < MIN_AVG_VOL20:
        return None

    # ---- Monthly stage analysis ----
    monthly = _to_monthly(dates, o, h, l, c, v)
    if len(monthly) < MIN_MONTHS:
        return None
    stg = _classify_stage(monthly)

    # ---- Daily trend state + entry ----
    dst = _daily_state(o, h, l, c, v, price)

    # ---- Techno-funda hygiene ----
    fa = _funda_assess(funda, div_years, cur_year, sector)

    rsi = _rsi(c)

    # ---- Momentum context numbers ----
    close_20ago = float(c[-21]) if n >= 21 else None
    close_60ago = float(c[-61]) if n >= 61 else None
    ret_1m = (price / close_20ago - 1) * 100.0 if close_20ago else None
    ret_3m = (price / close_60ago - 1) * 100.0 if close_60ago else None

    # =====================================================================
    # SCORE (0-100): stage (35) + monthly structure (15) + daily stack (20)
    #                + launchpad (10) + techno-funda quality (20).
    # Deliberately weights the MACRO stage highest — this is a monthly-chart
    # watchlist; the daily state only fine-tunes timing.
    # =====================================================================
    stage_pts = {'EARLY_STAGE_2': 35.0, 'STAGE_2': 27.0, 'STAGE_1': 17.0,
                 'NEUTRAL': 9.0, 'STAGE_3': 7.0, 'STAGE_4': 0.0}.get(stg['stage'], 8.0)
    struct_pts = (5.0 if stg['above_sma10_m'] else 0.0) \
        + (5.0 if stg['sma10_over_sma20_m'] else 0.0) \
        + (5.0 if stg['sma10_m_rising'] else 0.0)
    stack_pts = {'STACKED_BULL': 20.0, 'PARTIAL': 12.0, 'ABOVE_20': 6.0, 'BELOW': 0.0}.get(dst['ma_stack'], 0.0)
    if dst['launchpad']:
        launch_pts = 10.0
    elif dst['cluster_spread_pct'] is not None:
        # partial credit as the cluster tightens toward the launchpad threshold
        launch_pts = max(0.0, min(6.0, (LAUNCHPAD_MAX_SPREAD_PCT * 2 - dst['cluster_spread_pct'])))
    else:
        launch_pts = 0.0
    score = stage_pts + struct_pts + stack_pts + launch_pts + fa['funda_pts']
    score = int(round(max(0.0, min(100.0, score))))
    grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D'

    # ---- Plain-English reasons ----
    reasons = []
    reasons.append(f"Monthly chart: {stg['stage_label']} "
                   f"({stg['stage_confidence']} confidence, {stg['months_of_history']}mo history)")
    if stg['stage'] == 'EARLY_STAGE_2' and stg['months_since_cross'] is not None:
        reasons.append(f"10-month avg crossed above the 20-month {stg['months_since_cross']}mo ago "
                       f"and broke its {BASE_CEILING_MONTHS}-month base — a fresh launchpad")
    elif stg['sma10_over_sma20_m'] and stg['months_since_cross'] is not None:
        reasons.append(f"10-month avg has held above the 20-month for {stg['months_since_cross']}mo")
    if dst['ma_stack'] == 'STACKED_BULL':
        reasons.append("Daily averages perfectly stacked: price > 10 > 20 > 50 > 200")
    elif dst['ma_stack'] == 'PARTIAL':
        reasons.append("Daily short/medium averages aligned bullishly (above the 50-day)")
    if dst['launchpad']:
        reasons.append(f"Launchpad — the 10/20/50-day averages are compressed within "
                       f"{dst['cluster_spread_pct']:.1f}% (volatility dried up, coiled to move)")
    if dst['entry_status'] == 'TRIGGER':
        reasons.append(f"Breakout TODAY: cleared the 20-day high on {dst['rvol']:.1f}x volume")
    elif dst['entry_status'] == 'PULLBACK':
        reasons.append("Pulled back to a rising 20-day average — a lower-risk entry zone")
    elif dst['entry_status'] == 'EXTENDED':
        reasons.append("Extended above its averages — wait for a pullback, don't chase (FOMO)")
    elif dst['entry_status'] == 'WAITING':
        reasons.append("No daily trigger yet — on the watchlist, waiting for a volume breakout")
    if fa['techno_funda_pass']:
        bits = ['A-category', 'positive EPS']
        if fa['pe'] is not None:
            bits.append(f"P/E {fa['pe']:.0f}")
        if fa['recent_dividend']:
            bits.append('recent dividend')
        reasons.append("Techno-funda clean: " + ", ".join(bits))
    else:
        miss = []
        if not fa['cat_a']:
            miss.append(f"not A-category ({fa['category'] or '?'})")
        if not fa['eps_positive']:
            miss.append('no positive EPS')
        if not fa['pe_ok']:
            miss.append('P/E over 30' if fa['pe'] else 'no P/E')
        if not fa['recent_dividend']:
            miss.append('no recent dividend')
        if miss:
            reasons.append("Fails techno-funda hygiene: " + ", ".join(miss))
    if ret_3m is not None:
        reasons.append(f"{'+' if ret_3m >= 0 else ''}{ret_3m:.0f}% over ~3 months")
    if rsi is not None:
        reasons.append(f"RSI {rsi:.0f}")
    if action_dates:
        reasons.append("History back-adjusted for a corporate action on " + ", ".join(action_dates))

    # ---- Sparkline: the monthly close path (macro stage story), ~48 points ----
    mcloses = monthly['close'].to_numpy(dtype=float)
    seg = mcloses[-48:] if len(mcloses) > 48 else mcloses
    spark = [round(float(x), 2) for x in seg]

    row = {
        'ticker': ticker,
        'sector': sector,
        'price': _clean(price),
        'score': score, 'grade': grade,
        # monthly stage
        'stage': stg['stage'], 'stage_label': stg['stage_label'],
        'stage_confidence': stg['stage_confidence'],
        'months_since_cross': stg['months_since_cross'],
        'sma10_m': stg['sma10_m'], 'sma20_m': stg['sma20_m'],
        'above_sma10_m': stg['above_sma10_m'], 'above_sma20_m': stg['above_sma20_m'],
        'sma10_m_rising': stg['sma10_m_rising'], 'broke_base': stg['broke_base'],
        # daily state
        'ma_stack': dst['ma_stack'], 'launchpad': dst['launchpad'],
        'cluster_spread_pct': dst['cluster_spread_pct'],
        'entry_status': dst['entry_status'],
        'breakout_trigger': dst['breakout_trigger'],
        'ext_20d_high_pct': dst['ext_20d_high_pct'],
        'rvol': dst['rvol'], 'avg_vol20': dst['avg_vol20'],
        'sma20': dst['sma20'], 'sma50': dst['sma50'], 'sma200': dst['sma200'],
        'sma20_rising': dst['sma20_rising'],
        'extended': dst['extended'], 'pullback': dst['pullback'],
        # momentum context
        'ret_1m': _clean(ret_1m), 'ret_3m': _clean(ret_3m), 'rsi': _clean(rsi),
        # techno-funda
        'category': fa['category'], 'eps': fa['eps'], 'pe': fa['pe'],
        'market_cap_cr': fa['market_cap_cr'], 'is_insurer': fa['is_insurer'],
        'techno_funda_pass': fa['techno_funda_pass'],
        'recent_dividend': fa['recent_dividend'],
        'adjusted_for_action': bool(action_dates), 'action_dates': action_dates,
        'reasons': reasons,
        'spark': spark,
    }
    return row


def scan(engine, sector_map: dict | None = None) -> dict:
    """Scan the whole universe for the Stage-2 momentum watchlist.

    Returns {as_of, universe, count, counts:{...}, stocks:[...]} sorted by score.
    A structural + techno-funda screen — NOT a validated buy list.
    """
    try:
        last = pd.read_sql_query(text("SELECT MAX(date) AS d FROM stock_data"), engine)
        as_of = str(last['d'].iloc[0])[:10] if not last.empty and last['d'].iloc[0] else None
    except Exception as e:
        logger.error(f"momentum scan: latest-date lookup failed: {e}")
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if not as_of:
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

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
        logger.error(f"momentum scan: bulk read failed: {e}")
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if allrows.empty:
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

    for col in ('open', 'high', 'low', 'close', 'volume'):
        allrows[col] = pd.to_numeric(allrows[col], errors='coerce')
    allrows = allrows.dropna(subset=['close', 'high', 'low'])

    udates = sorted(pd.unique(allrows['date'].astype(str).str[:10]))
    stale_cutoff = (udates[-MAX_STALE_TRADING_DAYS] if len(udates) >= MAX_STALE_TRADING_DAYS
                    else (udates[0] if udates else None))
    cur_year = int(as_of[:4])

    # Fundamentals (sector + category + eps + pe + market cap) in one read.
    funda_map: dict = {}
    if sector_map is None:
        sector_map = {}
    try:
        fdf = pd.read_sql_query(text("SELECT * FROM fundamentals"), engine)
        for _, fr in fdf.iterrows():
            tk = str(fr['ticker'])
            funda_map[tk] = fr.to_dict()
            if tk not in sector_map and fr.get('sector'):
                sector_map[tk] = fr.get('sector')
    except Exception as e:
        logger.debug(f"momentum scan: fundamentals read failed: {e}")

    # Dividend years per ticker (for the "recent dividend" hygiene check).
    div_map: dict = {}
    try:
        ddf = pd.read_sql_query(
            text("SELECT ticker, year FROM dividend_history WHERE cash_pct > 0 OR stock_pct > 0"), engine)
        for tk, g in ddf.groupby('ticker'):
            div_map[str(tk)] = [int(y) for y in g['year'].tolist()]
    except Exception as e:
        logger.debug(f"momentum scan: dividend read failed: {e}")

    stocks = []
    universe = 0
    for ticker, g in allrows.groupby('ticker'):
        universe += 1
        try:
            row = _analyze_one(str(ticker), g, sector_map.get(str(ticker)),
                               funda_map.get(str(ticker)), div_map.get(str(ticker)),
                               cur_year, stale_cutoff)
            if row:
                stocks.append(row)
        except Exception as e:
            logger.debug(f"momentum scan: {ticker} failed: {e}")
            continue

    # Rank: score, then techno-funda pass, then a fired trigger, then freshness.
    stage_order = {'EARLY_STAGE_2': 5, 'STAGE_2': 4, 'STAGE_1': 3, 'NEUTRAL': 2, 'STAGE_3': 1, 'STAGE_4': 0}
    stocks.sort(key=lambda x: (x['score'], int(x['techno_funda_pass']),
                               int(x['breakout_trigger']), stage_order.get(x['stage'], 0)),
                reverse=True)

    counts = {
        'early_stage2': sum(1 for s in stocks if s['stage'] == 'EARLY_STAGE_2'),
        'stage2': sum(1 for s in stocks if s['stage'] == 'STAGE_2'),
        'stage1': sum(1 for s in stocks if s['stage'] == 'STAGE_1'),
        'launchpad': sum(1 for s in stocks if s['launchpad']),
        'trigger': sum(1 for s in stocks if s['breakout_trigger']),
        'techno_funda_pass': sum(1 for s in stocks if s['techno_funda_pass']),
    }
    return {'as_of': as_of, 'universe': universe, 'count': len(stocks),
            'counts': counts, 'stocks': stocks}
