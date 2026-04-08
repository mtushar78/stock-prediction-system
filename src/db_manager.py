"""
Database Manager for DSE Sniper System
Handles PostgreSQL database operations for stock data storage.

Migrated from SQLite — public API is preserved so callers that use the
high-level methods (insert_stock_data, get_stock_data, get_all_tickers, ...)
do not need to change. Callers that touch ``db.conn`` directly with
``cursor.execute(...)`` must use ``%s`` placeholders and PostgreSQL syntax
(``ON CONFLICT`` instead of ``INSERT OR REPLACE``).
"""

import os
import logging
from pathlib import Path
from typing import Optional, List

import pandas as pd
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_database_url() -> str:
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Create a .env file at project root with: "
            "DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
        )
    return url


_engine_singleton = None


def _get_engine():
    """Return a singleton SQLAlchemy engine. Pooled, shared by every
    ``DatabaseManager`` instance, used for pandas read_sql / to_sql."""
    global _engine_singleton
    if _engine_singleton is None:
        url = _resolve_database_url()
        sa_url = url
        if sa_url.startswith('postgresql://'):
            sa_url = 'postgresql+psycopg2://' + sa_url[len('postgresql://'):]
        _engine_singleton = create_engine(
            sa_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
    return _engine_singleton


class DatabaseManager:
    """Manages PostgreSQL database operations for stock data."""

    _schema_initialized = False

    def __init__(self):
        """Connect to PostgreSQL using DATABASE_URL from the environment."""
        self.database_url = _resolve_database_url()
        self.engine = _get_engine()
        # Pooled raw psycopg2 connection (returns to pool on close()).
        self.conn = self.engine.raw_connection()
        if not DatabaseManager._schema_initialized:
            self.init_db()
            DatabaseManager._schema_initialized = True

    # ------------------------------------------------------------------ #
    # Schema bootstrap
    # ------------------------------------------------------------------ #

    def init_db(self):
        """Create all tables and indexes if they don't exist."""
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticker_date
                ON stock_data(ticker, date)
            """)

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

            # Portfolio tables (also created lazily by portfolio_manager.py).
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_purchase_history_ticker
                ON purchase_history(ticker)
            """)

            self.conn.commit()
            host = self.database_url.split('@')[-1].split('/')[0]
            logger.info(f"Database initialized at {host}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error initializing database: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Insert / update
    # ------------------------------------------------------------------ #

    def insert_stock_data(self, df: pd.DataFrame, ticker: str,
                          source: str = "adjusted_data", is_final: bool = True):
        """
        Insert stock data into database.

        Args:
            df: DataFrame with columns: Date, Open, High, Low, Close, Volume.
                Optional columns: TradeCount, ValueMN (mapped to trade_count, value_mn).
            ticker: Stock ticker symbol.
            source: Data source identifier.
            is_final: True for EOD closed candle, False for intraday snapshot.
        """
        try:
            df = df.copy()
            df['ticker'] = ticker
            df['is_final'] = 1 if is_final else 0
            df.columns = [col.lower() for col in df.columns]

            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            columns = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'is_final']
            extra_col_map = {'tradecount': 'trade_count', 'valuemn': 'value_mn'}
            for df_col, db_col in extra_col_map.items():
                if df_col in df.columns:
                    df.rename(columns={df_col: db_col}, inplace=True)
                    columns.append(db_col)

            df = df[columns]

            cursor = self.conn.cursor()
            col_names = ', '.join(columns)
            update_cols = [c for c in columns if c not in ('date', 'ticker')]
            update_clause = ', '.join([f'{c}=EXCLUDED.{c}' for c in update_cols])

            sql = (
                f"INSERT INTO stock_data ({col_names}) VALUES %s "
                f"ON CONFLICT (date, ticker) DO UPDATE SET {update_clause}"
            )

            rows = [
                tuple(_to_python(v) for v in row)
                for row in df.itertuples(index=False, name=None)
            ]
            psycopg2.extras.execute_values(cursor, sql, rows, page_size=500)

            cursor.execute(
                """
                INSERT INTO metadata (ticker, last_updated, data_source, record_count)
                VALUES (%s, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), %s, %s)
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
        """Return a NEW pooled raw connection. Caller must close() it."""
        return self.engine.raw_connection()

    def get_stock_data(self, ticker: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """Retrieve stock data using the pooled SQLAlchemy engine."""
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
        """Get list of all tickers in database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM stock_data ORDER BY ticker")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting tickers: {e}")
            return []

    def get_latest_date(self, ticker: str) -> Optional[str]:
        """Get the latest date for a ticker."""
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
        """Clear all data for a specific ticker."""
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
        """Get database statistics."""
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
                'date_range': f"{date_range[0]} to {date_range[1]}" if date_range[0] else "No data",
            }
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting stats: {e}")
            return {}

    def get_all_fundamentals(self) -> dict:
        """Return {ticker: paid_up_capital_cr} dict for Low Float scoring."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT ticker, paid_up_capital_cr FROM fundamentals")
            return {row[0]: row[1] for row in cursor.fetchall() if row[1] is not None}
        except Exception:
            self.conn.rollback()
            return {}

    def get_fundamentals_full(self) -> pd.DataFrame:
        """Return full fundamentals table as DataFrame."""
        try:
            return pd.read_sql_query(text("SELECT * FROM fundamentals"), self.engine)
        except Exception:
            return pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def close(self):
        """Return the pooled connection back to the engine."""
        if self.conn is not None:
            try:
                self.conn.close()  # SQLAlchemy returns to pool
            except Exception:
                pass
            self.conn = None
        # Don't dispose the shared engine.
        logger.info("Database connection released")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def _to_python(v):
    """Convert pandas/numpy values to plain Python primitives for psycopg2."""
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
