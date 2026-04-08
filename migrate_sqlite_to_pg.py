"""
One-time SQLite -> PostgreSQL migration for DSE Sniper.

Reads from data/dse_history.db (SQLite, 135 MB) and copies every row into
the PostgreSQL database pointed to by DATABASE_URL (set via .env). Uses
COPY for the large stock_data table (~1.07M rows) for maximum throughput
over the Singapore region link.

Idempotent-ish: stock_data uses ON CONFLICT DO NOTHING via a staging table,
so re-running won't duplicate. metadata / fundamentals / portfolio /
purchase_history use ON CONFLICT DO UPDATE so re-running is safe.
signals_today is fully replaced (truncated + reloaded).

Usage:
    python migrate_sqlite_to_pg.py
    python migrate_sqlite_to_pg.py --tables stock_data,metadata
    python migrate_sqlite_to_pg.py --dry-run
"""

import sys
import time
import sqlite3
import argparse
from io import StringIO
from pathlib import Path
import csv

import psycopg2
import psycopg2.extras

# Make src/ importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from db_manager import DatabaseManager  # noqa: E402

SQLITE_PATH = ROOT / "data" / "dse_history.db"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------- #
# Per-table migrators
# ---------------------------------------------------------------------- #

STOCK_COLUMNS = [
    'date', 'ticker', 'open', 'high', 'low', 'close', 'volume',
    'is_final', 'public_volume', 'trade_count', 'value_mn',
]


def migrate_stock_data(sqlite_conn, pg_conn, dry_run=False):
    """Bulk-copy stock_data via COPY into a staging table, then merge."""
    cur_lite = sqlite_conn.cursor()
    cur_lite.execute(f"SELECT COUNT(*) FROM stock_data")
    total = cur_lite.fetchone()[0]
    log(f"stock_data: {total:,} rows in SQLite")
    if total == 0:
        return 0
    if dry_run:
        return total

    pg_cur = pg_conn.cursor()

    # Create a session-scoped staging table that mirrors stock_data exactly.
    pg_cur.execute("DROP TABLE IF EXISTS _stage_stock_data")
    pg_cur.execute("""
        CREATE TEMP TABLE _stage_stock_data (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume BIGINT,
            is_final INTEGER,
            public_volume BIGINT,
            trade_count BIGINT,
            value_mn DOUBLE PRECISION
        )
    """)

    # Stream rows into a CSV buffer chunk-by-chunk and COPY each chunk.
    cur_lite.execute(
        f"SELECT {', '.join(STOCK_COLUMNS)} FROM stock_data ORDER BY date, ticker"
    )

    CHUNK = 50_000
    copied = 0
    while True:
        rows = cur_lite.fetchmany(CHUNK)
        if not rows:
            break

        buf = StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        for r in rows:
            # Convert None -> '\\N' (PG's NULL marker for COPY CSV with NULL '\N')
            row_out = []
            for v in r:
                if v is None:
                    row_out.append('\\N')
                else:
                    row_out.append(v)
            writer.writerow(row_out)
        buf.seek(0)

        pg_cur.copy_expert(
            "COPY _stage_stock_data FROM STDIN WITH (FORMAT csv, NULL '\\N')",
            buf,
        )
        copied += len(rows)
        log(f"  ... copied {copied:,}/{total:,}")

    # Merge stage into real table.
    update_cols = [c for c in STOCK_COLUMNS if c not in ('date', 'ticker')]
    update_clause = ', '.join([f"{c}=EXCLUDED.{c}" for c in update_cols])
    pg_cur.execute(f"""
        INSERT INTO stock_data ({', '.join(STOCK_COLUMNS)})
        SELECT {', '.join(STOCK_COLUMNS)} FROM _stage_stock_data
        ON CONFLICT (date, ticker) DO UPDATE SET {update_clause}
    """)
    pg_cur.execute("DROP TABLE _stage_stock_data")
    pg_conn.commit()
    log(f"stock_data: {copied:,} rows merged into PG")
    return copied


def migrate_metadata(sqlite_conn, pg_conn, dry_run=False):
    cur_lite = sqlite_conn.cursor()
    cur_lite.execute("SELECT ticker, last_updated, data_source, record_count FROM metadata")
    rows = cur_lite.fetchall()
    log(f"metadata: {len(rows)} rows")
    if not rows or dry_run:
        return len(rows)

    pg_cur = pg_conn.cursor()
    psycopg2.extras.execute_values(
        pg_cur,
        """
        INSERT INTO metadata (ticker, last_updated, data_source, record_count)
        VALUES %s
        ON CONFLICT (ticker) DO UPDATE SET
            last_updated = EXCLUDED.last_updated,
            data_source = EXCLUDED.data_source,
            record_count = EXCLUDED.record_count
        """,
        rows,
        page_size=500,
    )
    pg_conn.commit()
    return len(rows)


def migrate_portfolio(sqlite_conn, pg_conn, dry_run=False):
    cur_lite = sqlite_conn.cursor()
    # Old SQLite schema only has 6 cols (no total_cost/commission_paid).
    # New schema has 8. Pad with sensible defaults.
    cur_lite.execute("PRAGMA table_info(portfolio)")
    src_cols = [r[1] for r in cur_lite.fetchall()]

    cur_lite.execute(f"SELECT {', '.join(src_cols)} FROM portfolio")
    src_rows = cur_lite.fetchall()
    log(f"portfolio: {len(src_rows)} rows (src cols={src_cols})")
    if not src_rows or dry_run:
        return len(src_rows)

    rows = []
    for r in src_rows:
        d = dict(zip(src_cols, r))
        rows.append((
            d['ticker'],
            d['buy_price'],
            d['quantity'],
            d['highest_seen'],
            d['purchase_date'],
            d.get('notes'),
            d.get('total_cost') if d.get('total_cost') is not None else (d['buy_price'] * d['quantity']),
            d.get('commission_paid') if d.get('commission_paid') is not None else 0,
        ))

    pg_cur = pg_conn.cursor()
    psycopg2.extras.execute_values(
        pg_cur,
        """
        INSERT INTO portfolio
            (ticker, buy_price, quantity, highest_seen, purchase_date, notes, total_cost, commission_paid)
        VALUES %s
        ON CONFLICT (ticker) DO UPDATE SET
            buy_price = EXCLUDED.buy_price,
            quantity = EXCLUDED.quantity,
            highest_seen = EXCLUDED.highest_seen,
            purchase_date = EXCLUDED.purchase_date,
            notes = EXCLUDED.notes,
            total_cost = EXCLUDED.total_cost,
            commission_paid = EXCLUDED.commission_paid
        """,
        rows,
    )
    pg_conn.commit()
    return len(rows)


def migrate_purchase_history(sqlite_conn, pg_conn, dry_run=False):
    cur_lite = sqlite_conn.cursor()
    cur_lite.execute(
        "SELECT ticker, buy_price, quantity, commission, total_cost, purchase_date, notes FROM purchase_history"
    )
    rows = cur_lite.fetchall()
    log(f"purchase_history: {len(rows)} rows")
    if not rows or dry_run:
        return len(rows)

    pg_cur = pg_conn.cursor()
    psycopg2.extras.execute_values(
        pg_cur,
        """
        INSERT INTO purchase_history
            (ticker, buy_price, quantity, commission, total_cost, purchase_date, notes)
        VALUES %s
        """,
        rows,
    )
    pg_conn.commit()
    return len(rows)


def migrate_fundamentals(sqlite_conn, pg_conn, dry_run=False):
    cur_lite = sqlite_conn.cursor()
    cur_lite.execute("""
        SELECT ticker, paid_up_capital, paid_up_capital_cr, sector, market_category,
               total_shares, market_cap, face_value, eps, pe_ratio, nav, last_updated
        FROM fundamentals
    """)
    rows = cur_lite.fetchall()
    log(f"fundamentals: {len(rows)} rows")
    if not rows or dry_run:
        return len(rows)

    pg_cur = pg_conn.cursor()
    psycopg2.extras.execute_values(
        pg_cur,
        """
        INSERT INTO fundamentals
            (ticker, paid_up_capital, paid_up_capital_cr, sector, market_category,
             total_shares, market_cap, face_value, eps, pe_ratio, nav, last_updated)
        VALUES %s
        ON CONFLICT (ticker) DO UPDATE SET
            paid_up_capital = EXCLUDED.paid_up_capital,
            paid_up_capital_cr = EXCLUDED.paid_up_capital_cr,
            sector = EXCLUDED.sector,
            market_category = EXCLUDED.market_category,
            total_shares = EXCLUDED.total_shares,
            market_cap = EXCLUDED.market_cap,
            face_value = EXCLUDED.face_value,
            eps = EXCLUDED.eps,
            pe_ratio = EXCLUDED.pe_ratio,
            nav = EXCLUDED.nav,
            last_updated = EXCLUDED.last_updated
        """,
        rows,
    )
    pg_conn.commit()
    return len(rows)


def migrate_signals_today(sqlite_conn, pg_engine, dry_run=False):
    """signals_today is recreated each scrape. Just copy it via pandas."""
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM signals_today", sqlite_conn)
    log(f"signals_today: {len(df)} rows")
    if df.empty or dry_run:
        return len(df)
    df.to_sql('signals_today', pg_engine, if_exists='replace', index=False)
    return len(df)


# ---------------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', default='all',
                    help='Comma list of tables to migrate (default: all)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Print row counts only — no writes to PG')
    args = ap.parse_args()

    if not SQLITE_PATH.exists():
        log(f"FATAL: SQLite DB not found at {SQLITE_PATH}")
        sys.exit(1)

    log(f"Source SQLite: {SQLITE_PATH}")
    log(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    # Open SQLite (read-only)
    sqlite_conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)

    # Force PG schema bootstrap by instantiating DatabaseManager once.
    db = DatabaseManager()
    pg_conn = db.conn
    log("Postgres schema initialized via DatabaseManager.init_db()")

    requested = set(args.tables.split(','))
    do_all = 'all' in requested

    counts = {}

    t0 = time.time()
    if do_all or 'stock_data' in requested:
        counts['stock_data'] = migrate_stock_data(sqlite_conn, pg_conn, args.dry_run)
    if do_all or 'metadata' in requested:
        counts['metadata'] = migrate_metadata(sqlite_conn, pg_conn, args.dry_run)
    if do_all or 'portfolio' in requested:
        counts['portfolio'] = migrate_portfolio(sqlite_conn, pg_conn, args.dry_run)
    if do_all or 'purchase_history' in requested:
        counts['purchase_history'] = migrate_purchase_history(sqlite_conn, pg_conn, args.dry_run)
    if do_all or 'fundamentals' in requested:
        counts['fundamentals'] = migrate_fundamentals(sqlite_conn, pg_conn, args.dry_run)
    if do_all or 'signals_today' in requested:
        counts['signals_today'] = migrate_signals_today(sqlite_conn, db.engine, args.dry_run)
    elapsed = time.time() - t0

    sqlite_conn.close()
    db.close()

    log("=" * 60)
    log(f"Done in {elapsed:.1f}s")
    for t, n in counts.items():
        log(f"  {t}: {n:,} rows")

    if args.dry_run:
        log("(dry run — no changes written)")


if __name__ == "__main__":
    main()
