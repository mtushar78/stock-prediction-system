"""Live REVERSAL signal tracker (the honest-verdict journal).

Logs every reversal the moment it fires (entry price + the checks) and, on every
analysis cycle, recomputes each signal's REAL forward outcome from price history
under a fixed ruleset (-7% stop / +25% target / 40-trading-day expiry). No
backtest assumptions — this is the prospective record that answers "does the
reversal signal actually work in live trading?"

Schema is created idempotently and works on both SQLite (local) and PG (prod).
"""
import json
import logging
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

STOP_PCT = -7.0      # hard stop
TARGET_PCT = 25.0    # take-profit target
EXPIRE_DAYS = 40     # trading days to give the move

DDL = """
CREATE TABLE IF NOT EXISTS reversal_tracker (
    ticker       TEXT NOT NULL,
    fire_date    TEXT NOT NULL,
    entry_price  REAL NOT NULL,
    checks_json  TEXT,
    deep_value   INTEGER,
    -- outcome (recomputed each cycle) --
    last_date    TEXT,
    last_price   REAL,
    days_held    INTEGER,
    cur_ret      REAL,
    peak_ret     REAL,
    peak_date    TEXT,
    trough_ret   REAL,
    r5           REAL,
    r10          REAL,
    r20          REAL,
    status       TEXT,           -- OPEN / TARGET / STOPPED / EXPIRED
    exit_date    TEXT,
    exit_ret     REAL,
    exit_reason  TEXT,
    PRIMARY KEY (ticker, fire_date)
)
"""


def ensure_table(engine):
    with engine.begin() as c:
        c.execute(text(DDL))


def _existing_keys(engine):
    try:
        df = pd.read_sql_query(text("SELECT ticker, fire_date FROM reversal_tracker"), engine)
        return set(zip(df['ticker'], df['fire_date'].astype(str)))
    except Exception:
        return set()


def record_fresh_reversals(engine, results_df):
    """Insert any newly-fired reversals from a day's analyzer output that we're
    not already tracking. `results_df` is StockAnalyzer.analyze_all_tickers()."""
    ensure_table(engine)
    if results_df is None or results_df.empty:
        return 0
    df = results_df
    if 'reversal_signal' not in df.columns:
        return 0
    # Log only the FIRST day of each episode (fresh) so a multi-day signal isn't
    # recorded repeatedly. Fall back to reversal_signal if freshness is absent.
    if 'is_fresh_reversal' in df.columns:
        fired = df[df['is_fresh_reversal'] == True]  # noqa: E712
    else:
        fired = df[df['reversal_signal'] == True]  # noqa: E712
    if fired.empty:
        return 0
    have = _existing_keys(engine)
    inserted = 0
    with engine.begin() as c:
        for _, r in fired.iterrows():
            fd = str(r['date'])[:10]
            key = (r['ticker'], fd)
            if key in have:
                continue
            checks = r.get('reversal_checks')
            if isinstance(checks, str):
                try:
                    checks = json.loads(checks)
                except Exception:
                    checks = {}
            checks = checks if isinstance(checks, dict) else {}
            c.execute(text(
                "INSERT INTO reversal_tracker (ticker, fire_date, entry_price, checks_json, deep_value, status) "
                "VALUES (:t, :d, :e, :j, :dv, 'OPEN')"),
                {"t": r['ticker'], "d": fd, "e": float(r['close']),
                 "j": json.dumps(checks), "dv": 1 if checks.get('deep_value') else 0})
            inserted += 1
    if inserted:
        logger.info(f"📓 reversal_tracker: recorded {inserted} new signal(s)")
    return inserted


def seed(engine, fires):
    """Seed known historical fires: list of (ticker, fire_date, entry_price, checks_dict)."""
    ensure_table(engine)
    have = _existing_keys(engine)
    with engine.begin() as c:
        for tk, fd, entry, checks in fires:
            if (tk, fd) in have:
                continue
            c.execute(text(
                "INSERT INTO reversal_tracker (ticker, fire_date, entry_price, checks_json, deep_value, status) "
                "VALUES (:t, :d, :e, :j, :dv, 'OPEN')"),
                {"t": tk, "d": fd, "e": float(entry),
                 "j": json.dumps(checks or {}), "dv": 1 if (checks or {}).get('deep_value') else 0})


def update_outcomes(engine, get_stock_data):
    """Recompute the forward outcome of every tracked signal from price history.
    `get_stock_data(ticker)` -> DataFrame with date/close (the DatabaseManager method)."""
    ensure_table(engine)
    rows = pd.read_sql_query(text("SELECT ticker, fire_date, entry_price FROM reversal_tracker"), engine)
    if rows.empty:
        return 0
    updated = 0
    with engine.begin() as c:
        for _, r in rows.iterrows():
            tk, fd, entry = r['ticker'], str(r['fire_date'])[:10], float(r['entry_price'])
            h = get_stock_data(tk)
            if h is None or h.empty:
                continue
            h = h.copy()
            # Coerce FIRST (PG may return Decimal/None), then drop non-trading
            # rows — otherwise a single bad close NaN-poisons max()/min().
            h['close'] = pd.to_numeric(h['close'], errors='coerce')
            h = h[h['close'] > 0]
            h['d'] = h['date'].astype(str).str[:10]
            fut = h[h['d'] > fd].drop_duplicates('d').sort_values('d').reset_index(drop=True)
            if fut.empty:
                continue
            closes = fut['close'].to_numpy(dtype=float)
            dates = fut['d'].tolist()
            last_price = float(closes[-1]); days = len(closes)
            cur_ret = (last_price - entry) / entry * 100
            peak_i = int(closes.argmax()); peak_ret = (float(closes[peak_i]) - entry) / entry * 100
            trough_ret = (float(closes.min()) - entry) / entry * 100

            def at(k):
                return (float(closes[k - 1]) - entry) / entry * 100 if days >= k else None

            # walk forward applying the exit ruleset
            status, exit_date, exit_ret, exit_reason = 'OPEN', None, None, None
            for j in range(days):
                ret = (float(closes[j]) - entry) / entry * 100
                if ret <= STOP_PCT:
                    status, exit_date, exit_ret, exit_reason = 'STOPPED', dates[j], ret, '-7% stop'; break
                if ret >= TARGET_PCT:
                    status, exit_date, exit_ret, exit_reason = 'TARGET', dates[j], ret, '+25% target'; break
                if j + 1 >= EXPIRE_DAYS:
                    status, exit_date, exit_ret, exit_reason = 'EXPIRED', dates[j], ret, '40d expiry'; break

            c.execute(text(
                "UPDATE reversal_tracker SET last_date=:ld, last_price=:lp, days_held=:dh, cur_ret=:cr, "
                "peak_ret=:pr, peak_date=:pd, trough_ret=:tr, r5=:r5, r10=:r10, r20=:r20, "
                "status=:st, exit_date=:ed, exit_ret=:er, exit_reason=:ers "
                "WHERE ticker=:t AND fire_date=:fd"),
                {"ld": dates[-1], "lp": last_price, "dh": days, "cr": cur_ret,
                 "pr": peak_ret, "pd": dates[peak_i], "tr": trough_ret,
                 "r5": at(5), "r10": at(10), "r20": at(20),
                 "st": status, "ed": exit_date, "er": exit_ret, "ers": exit_reason,
                 "t": tk, "fd": fd})
            updated += 1
    logger.info(f"📓 reversal_tracker: updated {updated} outcome(s)")
    return updated


def get_journal(engine):
    """Return all tracked signals + summary stats for the API."""
    ensure_table(engine)
    df = pd.read_sql_query(text("SELECT * FROM reversal_tracker ORDER BY fire_date DESC"), engine)
    if df.empty:
        return {"signals": [], "summary": {"total": 0, "open": 0, "closed": 0}}
    closed = df[df['status'].isin(['TARGET', 'STOPPED', 'EXPIRED'])]
    def wr(s):
        s = s.dropna()
        return round(100 * (s > 0).mean(), 1) if len(s) else None
    summary = {
        "total": int(len(df)),
        "open": int((df['status'] == 'OPEN').sum()),
        "closed": int(len(closed)),
        "win_rate_realized": wr(closed['exit_ret']) if len(closed) else None,
        "avg_realized": round(float(closed['exit_ret'].dropna().mean()), 2) if len(closed) else None,
        "win_rate_10d": wr(df['r10']),
        "avg_10d": round(float(df['r10'].dropna().mean()), 2) if df['r10'].notna().any() else None,
        "win_rate_dv_10d": wr(df[df['deep_value'] == 1]['r10']),
        "win_rate_reg_10d": wr(df[df['deep_value'] == 0]['r10']),
    }
    df = df.where(pd.notna(df), None)
    return {"signals": df.to_dict(orient="records"), "summary": summary}
