"""
Database Manager for DSE Sniper System (SQLite primary).

SQLite at ``data/dse_history.db`` is the authoritative operational DB.
PostgreSQL (``DATABASE_URL``) is kept as a backup only — a scheduled
job in the backend (see ``src/pg_backup.py``) mirrors today's rows from
SQLite to PG once per day.

The public API is preserved so the rest of the codebase keeps working:
 - ``cursor.execute(sql, params)`` accepts PG-style ``%s`` placeholders.
 - A lightweight SQL translation layer maps PG-isms (``to_char(NOW(),...)``,
   ``SERIAL PRIMARY KEY``, ``DOUBLE PRECISION``, ``BIGINT``) to SQLite.
 - ``psycopg2.extras.execute_values`` is monkey-patched at import time to
   dispatch onto sqlite3 ``executemany`` so existing bulk-insert call
   sites work unchanged. The original function is preserved under
   ``pg_execute_values`` for use by the backup sync.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLITE_PATH = PROJECT_ROOT / 'data' / 'dse_history.db'


# ---------------------------------------------------------------------- #
# SQL translation layer (PG → SQLite)
# ---------------------------------------------------------------------- #

_TRANSLATE_RULES = [
    # to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') → SQLite equivalent.
    (re.compile(
        r"to_char\s*\(\s*NOW\s*\(\s*\)\s*,\s*'YYYY-MM-DD\s+HH24:MI:SS'\s*\)",
        re.IGNORECASE),
     "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"),
    # CURRENT_TIMESTAMP style NOW() fallback.
    (re.compile(r"\bNOW\s*\(\s*\)", re.IGNORECASE),
     "CURRENT_TIMESTAMP"),
    # Type mappings — SQLite is typeless but keep the spelling valid.
    (re.compile(r"\bSERIAL\s+PRIMARY\s+KEY\b", re.IGNORECASE),
     "INTEGER PRIMARY KEY AUTOINCREMENT"),
    (re.compile(r"\bSERIAL\b", re.IGNORECASE), "INTEGER"),
    (re.compile(r"\bDOUBLE\s+PRECISION\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bBIGINT\b", re.IGNORECASE), "INTEGER"),
]


def _translate_sql(sql: str) -> str:
    for pattern, repl in _TRANSLATE_RULES:
        sql = pattern.sub(repl, sql)
    # Swap PG positional %s for SQLite qmark ?. Run after the structural
    # rules above so we don't disturb strftime format specifiers (%Y etc.).
    sql = sql.replace('%s', '?')
    return sql


class _CompatCursor:
    """Wraps a sqlite3 Cursor to accept PG-style SQL on execute()."""

    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def execute(self, sql, params=None):
        sql = _translate_sql(sql)
        if params is None:
            return self._cur.execute(sql)
        return self._cur.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return self._cur.executemany(_translate_sql(sql), seq_of_params)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=-1):
        if size < 0:
            return self._cur.fetchmany()
        return self._cur.fetchmany(size)

    def close(self):
        return self._cur.close()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def __iter__(self):
        return iter(self._cur)


class _CompatConnection:
    """Wraps a DB-API connection (SQLAlchemy pool fairy) so cursor()
    yields a PG-style-accepting cursor. commit/rollback/close pass through
    to the pool fairy, which returns the underlying sqlite3 connection
    to the engine pool on close()."""

    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return _CompatCursor(self._raw.cursor())

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    def close(self):
        return self._raw.close()


# ---------------------------------------------------------------------- #
# psycopg2.extras.execute_values shim
# ---------------------------------------------------------------------- #

def _execute_values_shim(cur, sql, argslist, template=None,
                         page_size=100, fetch=False):
    """SQLite-safe stand-in for ``psycopg2.extras.execute_values``.

    Rewrites ``VALUES %s`` into a row-shaped placeholder block and
    dispatches to ``executemany``. Other ``%s`` placeholders (usually in
    ``ON CONFLICT`` subqueries) are left to the cursor's translation
    layer.
    """
    if not argslist:
        return None

    rows = list(argslist)
    if not rows:
        return None

    # Number of columns inferred from first row
    n = len(rows[0])
    placeholder = "(" + ", ".join(["?"] * n) + ")"

    new_sql = re.sub(
        r'VALUES\s+%s', f'VALUES {placeholder}',
        sql, count=1, flags=re.IGNORECASE,
    )
    # The cursor's executemany will translate any remaining PG-isms.
    cur.executemany(new_sql, rows)
    return None


# Capture the original for the backup sync to talk to real Postgres,
# then install the SQLite-safe shim globally.
try:
    import psycopg2  # noqa: F401
    import psycopg2.extras as _pg_extras
    pg_execute_values = _pg_extras.execute_values  # real implementation
    _pg_extras.execute_values = _execute_values_shim
except ImportError:
    pg_execute_values = None


# ---------------------------------------------------------------------- #
# SQLite engine singleton
# ---------------------------------------------------------------------- #

_engine_singleton = None


def _get_engine():
    """Shared SQLAlchemy engine over SQLite. StaticPool + WAL is the
    right default for a single-process FastAPI app: one connection
    shared across threads, writes serialized by SQLite, reads
    non-blocking thanks to WAL."""
    global _engine_singleton
    if _engine_singleton is None:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine_singleton = create_engine(
            f'sqlite:///{SQLITE_PATH}',
            future=True,
            connect_args={'check_same_thread': False, 'timeout': 30},
            poolclass=StaticPool,
        )
        with _engine_singleton.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.exec_driver_sql("PRAGMA busy_timeout=30000")
    return _engine_singleton


def get_pg_backup_url() -> Optional[str]:
    """Return DATABASE_URL for the PG backup, or None if not configured."""
    return os.environ.get('DATABASE_URL') or None


class DatabaseManager:
    """SQLite-primary DB manager."""

    _schema_initialized = False

    def __init__(self):
        self.engine = _get_engine()
        self._conn: Optional[_CompatConnection] = None
        if not DatabaseManager._schema_initialized:
            self.init_db()
            DatabaseManager._schema_initialized = True
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    @property
    def conn(self):
        """Lazy pooled connection, wrapped so execute() accepts %s."""
        if self._conn is None:
            self._conn = _CompatConnection(self.engine.raw_connection())
        return self._conn

    # ------------------------------------------------------------------ #
    # Schema bootstrap
    # ------------------------------------------------------------------ #

    def init_db(self):
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    is_final INTEGER DEFAULT 1,
                    public_volume BIGINT DEFAULT NULL,
                    trade_count BIGINT DEFAULT NULL,
                    value_mn DOUBLE PRECISION DEFAULT NULL,
                    PRIMARY KEY (date, ticker)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticker_date "
                "ON stock_data(ticker, date)"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    ticker TEXT PRIMARY KEY,
                    last_updated TEXT,
                    data_source TEXT,
                    record_count INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fundamentals (
                    ticker TEXT PRIMARY KEY,
                    paid_up_capital DOUBLE PRECISION,
                    paid_up_capital_cr DOUBLE PRECISION,
                    sector TEXT,
                    market_category TEXT,
                    total_shares BIGINT,
                    market_cap DOUBLE PRECISION,
                    face_value DOUBLE PRECISION,
                    eps DOUBLE PRECISION,
                    pe_ratio DOUBLE PRECISION,
                    nav DOUBLE PRECISION,
                    sponsor_pct DOUBLE PRECISION,
                    reserves_mn DOUBLE PRECISION,
                    short_term_loan_mn DOUBLE PRECISION,
                    long_term_loan_mn DOUBLE PRECISION,
                    debt_to_equity DOUBLE PRECISION,
                    eps_growth_pa DOUBLE PRECISION,
                    roe DOUBLE PRECISION,
                    last_updated TEXT
                )
            """)
            # v12 migration: add the 6-step quality columns to pre-existing tables.
            for _col in ('sponsor_pct', 'reserves_mn', 'short_term_loan_mn',
                         'long_term_loan_mn', 'debt_to_equity', 'eps_growth_pa', 'roe'):
                try:
                    cursor.execute(f"ALTER TABLE fundamentals ADD COLUMN IF NOT EXISTS {_col} DOUBLE PRECISION")
                except Exception:
                    try:  # SQLite has no IF NOT EXISTS on ADD COLUMN
                        cursor.execute(f"ALTER TABLE fundamentals ADD COLUMN {_col} DOUBLE PRECISION")
                    except Exception:
                        pass

            # Users (multi-user auth). Credentials are bcrypt-hashed; see src/auth.py.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    buy_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    highest_seen DOUBLE PRECISION NOT NULL,
                    purchase_date TEXT NOT NULL,
                    notes TEXT,
                    total_cost DOUBLE PRECISION DEFAULT 0,
                    commission_paid DOUBLE PRECISION DEFAULT 0,
                    PRIMARY KEY (user_id, ticker)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    buy_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission DOUBLE PRECISION NOT NULL,
                    total_cost DOUBLE PRECISION NOT NULL,
                    purchase_date TEXT NOT NULL,
                    notes TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_purchase_history_ticker "
                "ON purchase_history(ticker)"
            )
            # Realized-P&L journal: every sell is recorded here (portfolio rows
            # are deleted on exit, so without this the track record vanishes).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sale_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    sell_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission DOUBLE PRECISION NOT NULL,
                    proceeds DOUBLE PRECISION NOT NULL,
                    cost_basis DOUBLE PRECISION NOT NULL,
                    realized_pnl DOUBLE PRECISION NOT NULL,
                    buy_price DOUBLE PRECISION,
                    purchase_date TEXT,
                    sale_date TEXT NOT NULL,
                    notes TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sale_history_user "
                "ON sale_history(user_id)"
            )

            # Chart-analysis output — a second, INDEPENDENT scoring engine.
            # Each row = one ticker's classical candlestick-pattern verdict for
            # a given analysis_date. patterns + context are JSON blobs.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chart_signals (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    overall_score INTEGER NOT NULL,
                    overall_bias TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    pattern_count INTEGER NOT NULL,
                    price DOUBLE PRECISION,
                    patterns TEXT NOT NULL,
                    context TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, analysis_date)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_chart_signals_date "
                "ON chart_signals(analysis_date DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_chart_signals_date_score "
                "ON chart_signals(analysis_date DESC, overall_score DESC)"
            )

            # v14: Bulkowski multi-week CHART patterns (double bottoms, H&S,
            # triangles, flags, dead-cat bounce…). Separate from the candlestick
            # chart_signals table. One row per ticker with ≥1 active chart
            # pattern; `patterns` is the full JSON, the flat columns exist for
            # cheap list sorting/filtering.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chart_pattern_signals (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    price DOUBLE PRECISION,
                    bias TEXT,
                    confidence TEXT,
                    top_code TEXT,
                    top_name TEXT,
                    status TEXT,
                    target DOUBLE PRECISION,
                    target_pct DOUBLE PRECISION,
                    edge INTEGER DEFAULT 0,
                    grade TEXT,
                    verdict TEXT,
                    verdict_reason TEXT,
                    room_pct DOUBLE PRECISION,
                    has_conflict INTEGER DEFAULT 0,
                    pattern_count INTEGER NOT NULL DEFAULT 0,
                    confirmed_count INTEGER NOT NULL DEFAULT 0,
                    has_dcb INTEGER NOT NULL DEFAULT 0,
                    patterns TEXT NOT NULL,
                    summary TEXT,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, analysis_date)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_chart_pattern_signals_date "
                "ON chart_pattern_signals(analysis_date DESC)"
            )
            # Migrate the decision-layer columns onto any pre-existing table
            # (the table was created a version earlier without them).
            cursor.execute("PRAGMA table_info(chart_pattern_signals)")
            _cp_cols = {r[1] for r in cursor.fetchall()}
            for _c, _t in (('edge', 'INTEGER DEFAULT 0'), ('grade', 'TEXT'),
                           ('verdict', 'TEXT'), ('verdict_reason', 'TEXT'),
                           ('room_pct', 'DOUBLE PRECISION'),
                           ('has_conflict', 'INTEGER DEFAULT 0')):
                if _c not in _cp_cols:
                    cursor.execute(f"ALTER TABLE chart_pattern_signals ADD COLUMN {_c} {_t}")

            # Older SQLite DBs created portfolio without total_cost /
            # commission_paid — upgrade in-place.
            cursor.execute("PRAGMA table_info(portfolio)")
            cols = {r[1] for r in cursor.fetchall()}
            if 'total_cost' not in cols:
                cursor.execute(
                    "ALTER TABLE portfolio ADD COLUMN total_cost REAL DEFAULT 0"
                )
            if 'commission_paid' not in cols:
                cursor.execute(
                    "ALTER TABLE portfolio ADD COLUMN commission_paid REAL DEFAULT 0"
                )

            self.conn.commit()
            logger.info(f"SQLite database initialized at {SQLITE_PATH}")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error(f"Error initializing database: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Insert / update
    # ------------------------------------------------------------------ #

    def insert_stock_data(self, df: pd.DataFrame, ticker: str,
                          source: str = "adjusted_data", is_final: bool = True):
        try:
            df = df.copy()
            df['ticker'] = ticker
            df['is_final'] = 1 if is_final else 0
            df.columns = [c.lower() for c in df.columns]

            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            columns = ['date', 'ticker', 'open', 'high', 'low',
                       'close', 'volume', 'is_final']
            extra_col_map = {'tradecount': 'trade_count', 'valuemn': 'value_mn'}
            for df_col, db_col in extra_col_map.items():
                if df_col in df.columns:
                    df.rename(columns={df_col: db_col}, inplace=True)
                    columns.append(db_col)

            df = df[columns]

            cursor = self.conn.cursor()
            col_names = ', '.join(columns)
            update_cols = [c for c in columns if c not in ('date', 'ticker')]
            update_clause = ', '.join(
                [f'{c}=EXCLUDED.{c}' for c in update_cols]
            )
            placeholders = '(' + ', '.join(['?'] * len(columns)) + ')'

            sql = (
                f"INSERT INTO stock_data ({col_names}) VALUES {placeholders} "
                f"ON CONFLICT (date, ticker) DO UPDATE SET {update_clause}"
            )

            rows = [
                tuple(_to_python(v) for v in row)
                for row in df.itertuples(index=False, name=None)
            ]
            cursor.executemany(sql, rows)

            cursor.execute(
                """
                INSERT INTO metadata (ticker, last_updated, data_source, record_count)
                VALUES (?, strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'), ?, ?)
                ON CONFLICT (ticker) DO UPDATE SET
                    last_updated = EXCLUDED.last_updated,
                    data_source = EXCLUDED.data_source,
                    record_count = EXCLUDED.record_count
                """,
                (ticker, source, len(df))
            )

            self.conn.commit()
            logger.info(f"Inserted {len(df)} records for {ticker}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting data for {ticker}: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Read / query
    # ------------------------------------------------------------------ #

    def get_connection(self):
        """Return a NEW wrapped pooled connection. Caller must close()."""
        return _CompatConnection(self.engine.raw_connection())

    def get_stock_data(self, ticker: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        try:
            query_str = "SELECT * FROM stock_data WHERE ticker = :ticker"
            params = {"ticker": ticker}
            if start_date:
                query_str += " AND date >= :start_date"
                params["start_date"] = start_date
            if end_date:
                query_str += " AND date <= :end_date"
                params["end_date"] = end_date
            query_str += " ORDER BY date ASC"

            df = pd.read_sql_query(text(query_str), self.engine, params=params)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
            return df
        except Exception as e:
            logger.error(f"Error retrieving data for {ticker}: {e}")
            return pd.DataFrame()

    def get_all_tickers(self) -> List[str]:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM stock_data ORDER BY ticker")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting tickers: {e}")
            return []

    def get_latest_date(self, ticker: str) -> Optional[str]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT MAX(date) FROM stock_data WHERE ticker = %s",
                (ticker,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting latest date for {ticker}: {e}")
            return None

    def clear_ticker_data(self, ticker: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM stock_data WHERE ticker = %s", (ticker,))
            cursor.execute("DELETE FROM metadata WHERE ticker = %s", (ticker,))
            self.conn.commit()
            logger.info(f"Cleared data for {ticker}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error clearing data for {ticker}: {e}")

    def get_stats(self) -> dict:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM stock_data")
            ticker_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM stock_data")
            record_count = cursor.fetchone()[0]
            cursor.execute("SELECT MIN(date), MAX(date) FROM stock_data")
            date_range = cursor.fetchone()
            return {
                'total_tickers': ticker_count,
                'total_records': record_count,
                'date_range': (f"{date_range[0]} to {date_range[1]}"
                               if date_range[0] else "No data"),
            }
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting stats: {e}")
            return {}

    def get_all_fundamentals(self) -> dict:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT ticker, paid_up_capital_cr FROM fundamentals")
            return {row[0]: row[1] for row in cursor.fetchall() if row[1] is not None}
        except Exception:
            self.conn.rollback()
            return {}

    def get_fundamentals_full(self) -> pd.DataFrame:
        try:
            return pd.read_sql_query(text("SELECT * FROM fundamentals"), self.engine)
        except Exception:
            return pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Chart-signal storage (independent of signals_today)
    # ------------------------------------------------------------------ #

    def save_chart_signals_bulk(self, results: list):
        """UPSERT a list of chart-analysis results into chart_signals.

        Each entry must look like ChartAnalyzer.analyze_ticker output.
        UNIQUE(ticker, analysis_date) means re-running on the same day is
        idempotent — existing rows get refreshed.

        Important: rows for analysis_dates in the new results that are NOT
        in the new ticker set are DELETED first. This prevents stale rows
        from a previous (buggy) run from lingering after newer code
        legitimately rejects those tickers (e.g. broken OHLC)."""
        import json as _json
        if not results:
            return
        try:
            cursor = self.conn.cursor()

            # Group new results by analysis_date and known tickers
            from collections import defaultdict
            tickers_by_date: dict = defaultdict(set)
            for r in results:
                tickers_by_date[r['analysis_date']].add(r['ticker'])
            # For each (date, tickers) pair: delete rows for that date
            # that are NOT in the new ticker set.
            for adate, tset in tickers_by_date.items():
                placeholders = ','.join(['?'] * len(tset))
                cursor.execute(
                    f"DELETE FROM chart_signals "
                    f"WHERE analysis_date = ? AND ticker NOT IN ({placeholders})",
                    (adate, *sorted(tset))
                )

            sql = (
                "INSERT INTO chart_signals "
                "(ticker, analysis_date, overall_score, overall_bias, "
                " confidence, pattern_count, price, patterns, context, explanation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (ticker, analysis_date) DO UPDATE SET "
                "  overall_score = EXCLUDED.overall_score, "
                "  overall_bias  = EXCLUDED.overall_bias, "
                "  confidence    = EXCLUDED.confidence, "
                "  pattern_count = EXCLUDED.pattern_count, "
                "  price         = EXCLUDED.price, "
                "  patterns      = EXCLUDED.patterns, "
                "  context       = EXCLUDED.context, "
                "  explanation   = EXCLUDED.explanation, "
                "  detected_at   = CURRENT_TIMESTAMP"
            )
            rows = []
            for r in results:
                rows.append((
                    r['ticker'],
                    r['analysis_date'],
                    int(r['overall_score']),
                    r['overall_bias'],
                    r['confidence'],
                    int(r['pattern_count']),
                    float(r.get('price') or 0),
                    _json.dumps(r.get('patterns', []), default=str),
                    _json.dumps(r.get('context', {}), default=str),
                    r.get('explanation', ''),
                ))
            cursor.executemany(sql, rows)
            self.conn.commit()
            logger.info(f"Saved {len(rows)} chart-signal rows")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error(f"save_chart_signals_bulk failed: {e}")
            raise

    def get_chart_signals_today(self) -> pd.DataFrame:
        """Return the most recent analysis_date's chart signals."""
        try:
            return pd.read_sql_query(text(
                "SELECT * FROM chart_signals "
                "WHERE analysis_date = (SELECT MAX(analysis_date) FROM chart_signals) "
                "ORDER BY overall_score DESC, ticker ASC"
            ), self.engine)
        except Exception as e:
            logger.error(f"get_chart_signals_today failed: {e}")
            return pd.DataFrame()

    def get_chart_signal(self, ticker: str) -> Optional[dict]:
        """Return the most recent chart signal for one ticker, or None."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT ticker, analysis_date, overall_score, overall_bias, "
                "       confidence, pattern_count, price, patterns, context, "
                "       explanation, detected_at "
                "FROM chart_signals WHERE ticker = %s "
                "ORDER BY analysis_date DESC LIMIT 1",
                (ticker,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            import json as _json
            return {
                'ticker': row[0],
                'analysis_date': row[1],
                'overall_score': row[2],
                'overall_bias': row[3],
                'confidence': row[4],
                'pattern_count': row[5],
                'price': row[6],
                'patterns': _json.loads(row[7]) if row[7] else [],
                'context': _json.loads(row[8]) if row[8] else {},
                'explanation': row[9] or '',
                'detected_at': row[10],
            }
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error(f"get_chart_signal({ticker}) failed: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Chart-PATTERN storage (Bulkowski multi-week formations, v14)
    # ------------------------------------------------------------------ #

    def save_chart_pattern_signals_bulk(self, rows: list):
        """UPSERT chart-pattern scanner rows. Deletes rows for the same
        analysis_date not in the new set (so de-flagged tickers drop out)."""
        import json as _json
        if not rows:
            return
        try:
            cursor = self.conn.cursor()
            from collections import defaultdict
            by_date: dict = defaultdict(set)
            for r in rows:
                by_date[r['analysis_date']].add(r['ticker'])
            for adate, tset in by_date.items():
                placeholders = ','.join(['?'] * len(tset))
                cursor.execute(
                    f"DELETE FROM chart_pattern_signals "
                    f"WHERE analysis_date = ? AND ticker NOT IN ({placeholders})",
                    (adate, *sorted(tset))
                )
            sql = (
                "INSERT INTO chart_pattern_signals "
                "(ticker, analysis_date, price, bias, confidence, top_code, top_name, "
                " status, target, target_pct, edge, grade, verdict, verdict_reason, "
                " room_pct, has_conflict, pattern_count, confirmed_count, has_dcb, "
                " patterns, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (ticker, analysis_date) DO UPDATE SET "
                "  price=EXCLUDED.price, bias=EXCLUDED.bias, confidence=EXCLUDED.confidence, "
                "  top_code=EXCLUDED.top_code, top_name=EXCLUDED.top_name, status=EXCLUDED.status, "
                "  target=EXCLUDED.target, target_pct=EXCLUDED.target_pct, "
                "  edge=EXCLUDED.edge, grade=EXCLUDED.grade, verdict=EXCLUDED.verdict, "
                "  verdict_reason=EXCLUDED.verdict_reason, room_pct=EXCLUDED.room_pct, "
                "  has_conflict=EXCLUDED.has_conflict, "
                "  pattern_count=EXCLUDED.pattern_count, confirmed_count=EXCLUDED.confirmed_count, "
                "  has_dcb=EXCLUDED.has_dcb, patterns=EXCLUDED.patterns, summary=EXCLUDED.summary, "
                "  detected_at=CURRENT_TIMESTAMP"
            )
            payload = []
            for r in rows:
                payload.append((
                    r['ticker'], r['analysis_date'],
                    float(r.get('price') or 0), r.get('bias'), r.get('confidence'),
                    r.get('top_code'), r.get('top_name'), r.get('status'),
                    (float(r['target']) if r.get('target') is not None else None),
                    (float(r['target_pct']) if r.get('target_pct') is not None else None),
                    int(r.get('edge') or 0), r.get('grade'), r.get('verdict'),
                    r.get('verdict_reason'),
                    (float(r['room_pct']) if r.get('room_pct') is not None else None),
                    int(r.get('has_conflict') or 0),
                    int(r.get('pattern_count') or 0), int(r.get('confirmed_count') or 0),
                    int(r.get('has_dcb') or 0),
                    _json.dumps(r.get('patterns', []), default=str),
                    _json.dumps(r.get('summary', {}), default=str),
                ))
            cursor.executemany(sql, payload)
            self.conn.commit()
            logger.info(f"Saved {len(payload)} chart-pattern rows")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error(f"save_chart_pattern_signals_bulk failed: {e}")
            raise

    def get_chart_pattern_signals_today(self) -> pd.DataFrame:
        """Most recent analysis_date's chart-pattern scanner rows."""
        try:
            return pd.read_sql_query(text(
                "SELECT * FROM chart_pattern_signals "
                "WHERE analysis_date = (SELECT MAX(analysis_date) FROM chart_pattern_signals) "
                "ORDER BY edge DESC, (status='confirmed') DESC, ticker ASC"
            ), self.engine)
        except Exception as e:
            logger.error(f"get_chart_pattern_signals_today failed: {e}")
            return pd.DataFrame()

    def get_ohlcv_for_chart(self, ticker: str, days: int = 60) -> pd.DataFrame:
        """Return last N days of OHLCV for chart rendering, oldest-first."""
        try:
            query = text(
                "SELECT date, open, high, low, close, volume "
                "FROM stock_data WHERE ticker = :ticker "
                "ORDER BY date DESC LIMIT :n"
            )
            df = pd.read_sql_query(query, self.engine,
                                   params={'ticker': ticker, 'n': int(days)})
            if df.empty:
                return df
            # Re-sort oldest → newest for the chart
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df = df.sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"get_ohlcv_for_chart({ticker}) failed: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        logger.info("Database connection released")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def _to_python(v):
    """Convert pandas/numpy values to plain Python primitives."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, 'item'):
        try:
            return v.item()
        except (ValueError, TypeError):
            pass
    return v


if __name__ == "__main__":
    db = DatabaseManager()
    print("Database Stats:", db.get_stats())
    db.close()
