"""Unusual-activity radar — the data-driven "rumor" detector.

Rumors on the floor show up in the tape *before* the exchange makes it
official: abnormal volume and a price pushing the circuit limit, with nothing
declared. This scanner surfaces exactly that and cross-references each name
against the official news feed (``company_news``) to classify *why* it is
moving:

  * ``exchange_flagged`` — DSE has issued a query / halt / the company put out a
    rumor clarification. The exchange itself is telling you the move is
    unexplained. Strongest signal.
  * ``unexplained``       — big volume + price move, and NO price-sensitive news
    in the recent window. This is the "possible rumor / quiet accumulation"
    bucket the user is hunting.
  * ``news_driven``       — the move is explained by a recent PSI (dividend,
    earnings, etc.). Shown, but ranked below the unexplained moves.

It is a *watchlist*, not a buy signal: an unexplained spike is as often a pump
as it is early smart money. The value is seeing it the same day the broker-house
crowd starts whispering, with the reason (or the conspicuous absence of one)
attached.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---- Liquidity floors (ignore untradeable names) ---------------------- #
MIN_PRICE = 5.0
MIN_AVG_TURNOVER_BDT = 500_000        # avg daily traded value floor

# ---- What counts as "unusual" ----------------------------------------- #
RVOL_FLAG = 2.5           # today's volume >= 2.5x its 20-day average
TURNOVER_X_FLAG = 2.5     # today's traded VALUE >= 2.5x its 20-day average
PRICE_MOVE_FLAG = 3.5     # abs day move >= 3.5% (DSE circuit caps ~10%)
BASELINE_BARS = 20        # lookback for the "normal" volume/turnover
CALENDAR_LOOKBACK_DAYS = 45
NEWS_WINDOW_DAYS = 5      # a PSI within this many days "explains" a move


def _clean(f):
    if f is None:
        return None
    try:
        f = float(f)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(f) or np.isinf(f)) else round(f, 3)


def _analyse_one(ticker: str, g: pd.DataFrame) -> dict | None:
    g = g[g['close'] > 0].sort_values('date')
    if len(g) < 6:
        return None
    closes = g['close'].to_numpy(dtype=float)
    highs = g['high'].to_numpy(dtype=float)
    lows = g['low'].to_numpy(dtype=float)
    vols = g['volume'].to_numpy(dtype=float)

    price = float(closes[-1])
    if price < MIN_PRICE:
        return None

    prev_close = float(closes[-2])
    change_pct = (price / prev_close - 1) * 100.0 if prev_close > 0 else 0.0

    # Baselines EXCLUDE today so a spike doesn't dilute its own reference.
    hist_vol = vols[-(BASELINE_BARS + 1):-1]
    avg_vol = float(hist_vol.mean()) if len(hist_vol) else float(vols[:-1].mean() or 0)
    turnover = closes * vols
    hist_to = turnover[-(BASELINE_BARS + 1):-1]
    avg_turnover = float(hist_to.mean()) if len(hist_to) else float(turnover[:-1].mean() or 0)
    if avg_turnover < MIN_AVG_TURNOVER_BDT:
        return None

    vol_today = float(vols[-1])
    turnover_today = float(turnover[-1])
    rvol = vol_today / avg_vol if avg_vol > 0 else 0.0
    turnover_x = turnover_today / avg_turnover if avg_turnover > 0 else 0.0

    # Intraday range (volatility) as a secondary tell.
    day_range_pct = ((float(highs[-1]) - float(lows[-1])) / prev_close * 100.0
                     if prev_close > 0 else 0.0)

    vol_unusual = rvol >= RVOL_FLAG or turnover_x >= TURNOVER_X_FLAG
    price_unusual = abs(change_pct) >= PRICE_MOVE_FLAG
    if not (vol_unusual or price_unusual):
        return None
    # Require at least SOME volume conviction — a lone price tick on thin volume
    # isn't a "move". (A price flag still needs volume >= ~1.3x to count.)
    if price_unusual and not vol_unusual and rvol < 1.3:
        return None

    # Unusualness score 0-100: volume surprise + price thrust + range.
    vol_pts = min(45.0, max(rvol, turnover_x) * 9.0)
    price_pts = min(35.0, abs(change_pct) * 3.5)
    range_pts = min(10.0, day_range_pct * 1.2)
    near_limit = 10.0 if abs(change_pct) >= 8.0 else 0.0   # slammed the circuit
    score = vol_pts + price_pts + range_pts + near_limit

    return {
        'ticker': ticker,
        'price': _clean(price),
        'change_pct': _clean(change_pct),
        'rvol': _clean(rvol),
        'turnover_x': _clean(turnover_x),
        'turnover_today_mn': _clean(turnover_today / 1e6),
        'day_range_pct': _clean(day_range_pct),
        'direction': 'up' if change_pct >= 0 else 'down',
        '_score_raw': score,
    }


def scan(engine, news_window_days: int = NEWS_WINDOW_DAYS) -> dict:
    """Scan the latest session for unusual activity and classify each name by
    whether the official news feed explains the move.

    Returns {as_of, universe, count, counts:{...}, stocks:[...]}.
    """
    try:
        last = pd.read_sql_query(text("SELECT MAX(date) d FROM stock_data"), engine)
        as_of = str(last['d'].iloc[0])[:10] if not last.empty and last['d'].iloc[0] else None
    except Exception as e:
        logger.error(f"unusual-activity: latest-date lookup failed: {e}")
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if not as_of:
        return {'as_of': None, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

    cutoff = (datetime.strptime(as_of, '%Y-%m-%d')
              - timedelta(days=CALENDAR_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    try:
        allrows = pd.read_sql_query(text(
            "SELECT ticker, date, open, high, low, close, volume FROM stock_data "
            "WHERE date >= :cutoff ORDER BY ticker, date"
        ), engine, params={'cutoff': cutoff})
    except Exception as e:
        logger.error(f"unusual-activity: bulk read failed: {e}")
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}
    if allrows.empty:
        return {'as_of': as_of, 'universe': 0, 'count': 0, 'counts': {}, 'stocks': []}

    for col in ('open', 'high', 'low', 'close', 'volume'):
        allrows[col] = pd.to_numeric(allrows[col], errors='coerce')
    allrows = allrows.dropna(subset=['close', 'volume'])

    # Only consider names that actually traded on the latest session.
    traded_today = set(allrows[allrows['date'].astype(str).str[:10] == as_of]['ticker'])

    # Recent news, keyed by ticker, for the cross-reference.
    news_cutoff = (datetime.strptime(as_of, '%Y-%m-%d')
                   - timedelta(days=news_window_days)).strftime('%Y-%m-%d')
    news_by_ticker: dict = {}
    try:
        ndf = pd.read_sql_query(text(
            "SELECT ticker, news_date, category, title, is_price_sensitive, is_query "
            "FROM company_news WHERE news_date >= :c ORDER BY news_date DESC"
        ), engine, params={'c': news_cutoff})
        for _, r in ndf.iterrows():
            news_by_ticker.setdefault(r['ticker'], []).append(r.to_dict())
    except Exception as e:
        logger.debug(f"unusual-activity: news join skipped: {e}")

    sector_map: dict = {}
    try:
        sdf = pd.read_sql_query(text(
            "SELECT ticker, sector FROM fundamentals WHERE sector IS NOT NULL"), engine)
        sector_map = dict(zip(sdf['ticker'], sdf['sector']))
    except Exception:
        pass

    stocks, universe = [], 0
    for ticker, g in allrows.groupby('ticker'):
        if ticker not in traded_today:
            continue
        universe += 1
        try:
            row = _analyse_one(ticker, g)
        except Exception as e:
            logger.debug(f"unusual-activity: {ticker} failed: {e}")
            continue
        if not row:
            continue

        # ---- Cross-reference the news feed to classify the move ----
        nlist = news_by_ticker.get(ticker, [])
        has_query = any(int(n.get('is_query') or 0) for n in nlist)
        has_psi = any(int(n.get('is_price_sensitive') or 0) for n in nlist)
        latest = nlist[0] if nlist else None

        if has_query:
            cls, cls_label = 'exchange_flagged', 'Exchange flagged (query/halt)'
        elif not has_psi:
            cls, cls_label = 'unexplained', 'Unexplained move — no disclosed news'
        else:
            cls, cls_label = 'news_driven', 'Explained by recent news'

        reasons = []
        if row['rvol'] and row['rvol'] >= RVOL_FLAG:
            reasons.append(f"Volume {row['rvol']:.1f}x its 20-day average")
        if row['turnover_x'] and row['turnover_x'] >= TURNOVER_X_FLAG:
            reasons.append(f"Traded value {row['turnover_x']:.1f}x normal "
                           f"(৳{row['turnover_today_mn']:.1f}M today)")
        if abs(row['change_pct'] or 0) >= PRICE_MOVE_FLAG:
            arrow = '▲' if row['direction'] == 'up' else '▼'
            reasons.append(f"Price {arrow}{abs(row['change_pct']):.1f}% on the day")
        if cls == 'exchange_flagged':
            reasons.insert(0, "DSE has queried/halted this stock for unusual activity")
        elif cls == 'unexplained':
            reasons.append("No price-sensitive disclosure in the last "
                           f"{news_window_days} days — move is unexplained")

        # Ranking: exchange-flagged and unexplained moves float to the top; a
        # move fully explained by news is the least interesting for rumor-hunting.
        cls_boost = {'exchange_flagged': 25.0, 'unexplained': 12.0, 'news_driven': 0.0}[cls]
        score = int(round(min(100.0, row.pop('_score_raw') + cls_boost)))

        row.update({
            'sector': sector_map.get(ticker),
            'classification': cls,
            'classification_label': cls_label,
            'has_news': bool(nlist),
            'has_query': has_query,
            'has_psi': has_psi,
            'latest_news_date': latest['news_date'] if latest else None,
            'latest_news_category': latest['category'] if latest else None,
            'latest_news_title': latest['title'] if latest else None,
            'score': score,
            'reasons': reasons,
        })
        stocks.append(row)

    order = {'exchange_flagged': 0, 'unexplained': 1, 'news_driven': 2}
    stocks.sort(key=lambda x: (order[x['classification']], -x['score']))
    counts = {
        'exchange_flagged': sum(s['classification'] == 'exchange_flagged' for s in stocks),
        'unexplained': sum(s['classification'] == 'unexplained' for s in stocks),
        'news_driven': sum(s['classification'] == 'news_driven' for s in stocks),
    }
    return {'as_of': as_of, 'universe': universe, 'count': len(stocks),
            'counts': counts, 'stocks': stocks}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    from src.db_manager import DatabaseManager
    db = DatabaseManager()
    try:
        res = scan(db.engine)
        print(f"\nas_of={res['as_of']} universe={res['universe']} flagged={res['count']}")
        print(f"counts: {res['counts']}\n" + "=" * 70)
        for s in res['stocks'][:20]:
            tag = {'exchange_flagged': '[EXCH]', 'unexplained': '[RUMOR?]',
                   'news_driven': '[NEWS]'}[s['classification']]
            print(f"{tag:9} {s['ticker']:11} {s['change_pct']:+6.1f}%  "
                  f"rvol {s['rvol']:.1f}x  score {s['score']}  "
                  f"{s['latest_news_category'] or '-'}")
    finally:
        db.close()
