"""
PostgreSQL backup sync.

Mirrors the authoritative SQLite DB (``data/dse_history.db``) to the PG
instance configured via ``DATABASE_URL``. PG is backup-only — the app
reads and writes through SQLite. This module is invoked by a daily
scheduler (4:00 PM Asia/Dhaka) in ``backend/main.py``.

Sync strategy per table:
 - stock_data       : UPSERT rows with date >= (today - lookback_days),
                       keyed on (date, ticker). Lookback defaults to 7
                       so intraday corrections and weekend catch-up are
                       picked up without full-table scans.
 - metadata         : full UPSERT.
 - fundamentals     : full UPSERT.
 - portfolio        : mirror (truncate + insert). Small table.
 - purchase_history : UPSERT by id.
 - signals_today    : mirror (truncate + insert) — it's a snapshot table.

Uses the original ``psycopg2.extras.execute_values`` (saved as
``pg_execute_values`` in ``db_manager`` before the SQLite-safe shim
replaced it globally) against a real psycopg2 connection.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.db_manager import (
    SQLITE_PATH,
    get_pg_backup_url,
    pg_execute_values,
)

logger = logging.getLogger(__name__)


STOCK_DATA_LOOKBACK_DAYS = 7


# ---------------------------------------------------------------------- #
# Connection helpers
# ---------------------------------------------------------------------- #

def _open_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _open_pg(database_url: str):
    import psycopg2
    return psycopg2.connect(database_url)


# ---------------------------------------------------------------------- #
# Table-by-table sync
# ---------------------------------------------------------------------- #

def _ensure_pg_schema(pg_conn) -> None:
    """Idempotently create PG tables that match the SQLite schema."""
    cur = pg_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume BIGINT,
            is_final INTEGER DEFAULT 1,
            public_volume BIGINT,
            trade_count BIGINT,
            value_mn DOUBLE PRECISION,
            PRIMARY KEY (date, ticker)
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ticker_date ON stock_data(ticker, date)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            ticker TEXT PRIMARY KEY,
            last_updated TEXT,
            data_source TEXT,
            record_count INTEGER
        )
    """)
    cur.execute("""
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
    cur.execute("""
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            buy_price DOUBLE PRECISION NOT NULL,
            quantity INTEGER NOT NULL,
            commission DOUBLE PRECISION NOT NULL,
            total_cost DOUBLE PRECISION NOT NULL,
            purchase_date TEXT NOT NULL,
            notes TEXT
        )
    """)
    pg_conn.commit()


def _table_columns(sqlite_conn, table: str) -> list[str]:
    cur = sqlite_conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def _fetch_rows(sqlite_conn, table: str, columns: list[str],
                where: str = "") -> list[tuple]:
    cur = sqlite_conn.cursor()
    col_list = ", ".join(columns)
    sql = f"SELECT {col_list} FROM {table} {where}".strip()
    cur.execute(sql)
    return [tuple(row) for row in cur.fetchall()]


def _upsert(pg_conn, table: str, columns: list[str], rows: list[tuple],
            conflict_cols: list[str]) -> int:
    if not rows:
        return 0
    col_list = ", ".join(columns)
    update_cols = [c for c in columns if c not in conflict_cols]
    update_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
    conflict_target = ", ".join(conflict_cols)

    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES %s "
        f"ON CONFLICT ({conflict_target}) DO UPDATE SET {update_clause}"
        if update_cols else
        f"INSERT INTO {table} ({col_list}) VALUES %s "
        f"ON CONFLICT ({conflict_target}) DO NOTHING"
    )

    cur = pg_conn.cursor()
    pg_execute_values(cur, sql, rows, page_size=500)
    return len(rows)


def _mirror(pg_conn, table: str, columns: list[str], rows: list[tuple]) -> int:
    """Truncate the PG table and insert all rows. For small snapshot tables."""
    cur = pg_conn.cursor()
    cur.execute(f"DELETE FROM {table}")
    if rows:
        col_list = ", ".join(columns)
        sql = f"INSERT INTO {table} ({col_list}) VALUES %s"
        pg_execute_values(cur, sql, rows, page_size=500)
    return len(rows)


def _sync_stock_data(sqlite_conn, pg_conn, lookback_days: int) -> int:
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    cols = _table_columns(sqlite_conn, 'stock_data')
    rows = _fetch_rows(
        sqlite_conn, 'stock_data', cols,
        where=f"WHERE date >= '{cutoff}'",
    )
    return _upsert(pg_conn, 'stock_data', cols, rows, conflict_cols=['date', 'ticker'])


def _sync_metadata(sqlite_conn, pg_conn) -> int:
    cols = _table_columns(sqlite_conn, 'metadata')
    rows = _fetch_rows(sqlite_conn, 'metadata', cols)
    return _upsert(pg_conn, 'metadata', cols, rows, conflict_cols=['ticker'])


def _sync_fundamentals(sqlite_conn, pg_conn) -> int:
    cols = _table_columns(sqlite_conn, 'fundamentals')
    rows = _fetch_rows(sqlite_conn, 'fundamentals', cols)
    return _upsert(pg_conn, 'fundamentals', cols, rows, conflict_cols=['ticker'])


def _sync_portfolio(sqlite_conn, pg_conn) -> int:
    cols = _table_columns(sqlite_conn, 'portfolio')
    rows = _fetch_rows(sqlite_conn, 'portfolio', cols)
    return _mirror(pg_conn, 'portfolio', cols, rows)


def _sync_purchase_history(sqlite_conn, pg_conn) -> int:
    cols = _table_columns(sqlite_conn, 'purchase_history')
    rows = _fetch_rows(sqlite_conn, 'purchase_history', cols)
    return _upsert(pg_conn, 'purchase_history', cols, rows, conflict_cols=['id'])


def _sync_signals_today(sqlite_conn, pg_conn) -> int:
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='signals_today'"
    )
    if not cur.fetchone():
        return 0

    cols = _table_columns(sqlite_conn, 'signals_today')
    rows = _fetch_rows(sqlite_conn, 'signals_today', cols)

    # signals_today is rebuilt each analysis run — mirror schema in PG too.
    pg_cur = pg_conn.cursor()
    pg_cur.execute("DROP TABLE IF EXISTS signals_today")
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)  # TEXT is safe; table is snapshot
    pg_cur.execute(f"CREATE TABLE signals_today ({col_defs})")
    if rows:
        col_list = ", ".join(f'"{c}"' for c in cols)
        sql = f"INSERT INTO signals_today ({col_list}) VALUES %s"
        pg_execute_values(pg_cur, sql, rows, page_size=500)
    return len(rows)


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #

def sync_sqlite_to_pg(lookback_days: int = STOCK_DATA_LOOKBACK_DAYS) -> dict:
    """Mirror SQLite → PG. Returns a per-table row count summary.

    Safe to invoke repeatedly (upserts/mirrors are idempotent). Raises
    if DATABASE_URL is not configured or psycopg2 is unavailable — the
    caller (scheduler) should catch and log, not crash the app.
    """
    if pg_execute_values is None:
        raise RuntimeError(
            "psycopg2 is not installed — cannot sync to PG backup."
        )
    database_url = get_pg_backup_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set — cannot sync to PG backup."
        )
    if not Path(SQLITE_PATH).exists():
        raise RuntimeError(f"SQLite DB not found at {SQLITE_PATH}")

    t0 = datetime.now()
    logger.info(f"PG backup sync starting at {t0.isoformat()}")

    sqlite_conn = _open_sqlite()
    pg_conn = _open_pg(database_url)

    counts: dict[str, int] = {}
    try:
        _ensure_pg_schema(pg_conn)

        counts['stock_data'] = _sync_stock_data(
            sqlite_conn, pg_conn, lookback_days=lookback_days,
        )
        counts['metadata'] = _sync_metadata(sqlite_conn, pg_conn)
        counts['fundamentals'] = _sync_fundamentals(sqlite_conn, pg_conn)
        counts['portfolio'] = _sync_portfolio(sqlite_conn, pg_conn)
        counts['purchase_history'] = _sync_purchase_history(sqlite_conn, pg_conn)
        counts['signals_today'] = _sync_signals_today(sqlite_conn, pg_conn)

        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

    elapsed = (datetime.now() - t0).total_seconds()
    logger.info(
        f"PG backup sync done in {elapsed:.1f}s — "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    counts['_elapsed_seconds'] = elapsed
    return counts


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )
    result = sync_sqlite_to_pg()
    print("Sync result:", result)
