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
                    last_updated TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    ticker TEXT PRIMARY KEY,
                    buy_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    highest_seen DOUBLE PRECISION NOT NULL,
                    purchase_date TEXT NOT NULL,
                    notes TEXT,
                    total_cost DOUBLE PRECISION DEFAULT 0,
                    commission_paid DOUBLE PRECISION DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id SERIAL PRIMARY KEY,
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
