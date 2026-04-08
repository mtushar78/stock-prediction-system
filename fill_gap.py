"""
Fill the gap in the stock_data table after the old server crash.

Pulls full history per ticker via stocksurferbd, then inserts ONLY rows
strictly newer than the existing MAX(date) for that ticker. Existing
historical rows are NEVER touched (data integrity is everything).

Usage:
    python fill_gap.py                   # process all stocksurferbd-source tickers
    python fill_gap.py --since 2026-01-21  # custom cutoff (inclusive lower bound, rows > cutoff)
    python fill_gap.py GP BATBC           # only specific tickers
"""

import sys
import os
import time
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))
from db_manager import DatabaseManager  # noqa: E402

try:
    from stocksurferbd import PriceData
except ImportError:
    print("ERROR: stocksurferbd not installed. Run: pip install stocksurferbd")
    sys.exit(1)

ROOT = Path(__file__).parent
LOG_PATH = ROOT / f"fill_gap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

REQUIRED_COLS = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
COLUMN_MAPPING = {
    'DATE': 'Date',
    'OPENP': 'Open',
    'HIGH': 'High',
    'LOW': 'Low',
    'CLOSEP': 'Close',
    'VOLUME': 'Volume',
    'TRADE': 'TradeCount',
    'VALUE_MN': 'ValueMN',
}


def log(msg: str):
    print(msg, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")


def get_target_tickers(conn, explicit=None):
    """Return tickers to process. By default: only stocksurferbd-source tickers."""
    if explicit:
        return [t.upper() for t in explicit]
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ticker FROM metadata WHERE data_source LIKE %s ORDER BY ticker",
            ('stocksurferbd%',),
        )
        return [r[0] for r in cur.fetchall()]
    except Exception:
        conn.rollback()
        raise


def get_max_date(conn, ticker):
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(date) FROM stock_data WHERE ticker = %s", (ticker,))
        r = cur.fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        conn.rollback()
        raise


def fetch_history(price_data: PriceData, ticker: str) -> pd.DataFrame:
    temp_file = f"_gap_{ticker}.xlsx"
    try:
        price_data.save_history_data(ticker, file_name=temp_file, market='DSE')
        if not os.path.exists(temp_file):
            return pd.DataFrame()
        df = pd.read_excel(temp_file)
    finally:
        try:
            os.remove(temp_file)
        except OSError:
            pass

    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns=COLUMN_MAPPING)
    if not all(c in df.columns for c in REQUIRED_COLS):
        return pd.DataFrame()

    df['Date'] = pd.to_datetime(df['Date'])
    for c in ['Open', 'High', 'Low', 'Close']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).astype('int64')
    if 'TradeCount' in df.columns:
        df['TradeCount'] = pd.to_numeric(df['TradeCount'], errors='coerce').fillna(0).astype('int64')
    if 'ValueMN' in df.columns:
        df['ValueMN'] = pd.to_numeric(df['ValueMN'], errors='coerce')

    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'], how='all')
    return df.sort_values('Date').reset_index(drop=True)


def insert_gap_rows(conn, ticker: str, df_gap: pd.DataFrame, today: str):
    """Insert ONLY rows in df_gap. Uses ON CONFLICT DO NOTHING so we never
    overwrite any pre-existing row (defensive — caller already filtered to
    gap window)."""
    if df_gap.empty:
        return 0

    has_trade = 'TradeCount' in df_gap.columns
    has_value = 'ValueMN' in df_gap.columns

    rows = []
    for _, row in df_gap.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d')
        if date_str > today:
            continue  # never insert future rows
        rows.append((
            date_str, ticker,
            float(row['Open']) if pd.notna(row['Open']) else None,
            float(row['High']) if pd.notna(row['High']) else None,
            float(row['Low']) if pd.notna(row['Low']) else None,
            float(row['Close']) if pd.notna(row['Close']) else None,
            int(row['Volume']) if pd.notna(row['Volume']) else 0,
            1,  # is_final
            int(row['TradeCount']) if has_trade and pd.notna(row['TradeCount']) else None,
            float(row['ValueMN']) if has_value and pd.notna(row['ValueMN']) else None,
        ))

    if not rows:
        return 0

    cur = conn.cursor()
    try:
        import psycopg2.extras
        # ON CONFLICT DO NOTHING — preserves existing rows untouched.
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO stock_data
              (date, ticker, open, high, low, close, volume, is_final, trade_count, value_mn)
            VALUES %s
            ON CONFLICT (date, ticker) DO NOTHING
            """,
            rows,
            page_size=500,
        )
        inserted = cur.rowcount  # actual inserted (excluding skipped conflicts)

        if inserted > 0:
            cur.execute(
                """
                INSERT INTO metadata (ticker, last_updated, data_source, record_count)
                VALUES (
                    %s,
                    to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                    COALESCE((SELECT data_source FROM metadata WHERE ticker=%s), 'stocksurferbd'),
                    (SELECT COUNT(*) FROM stock_data WHERE ticker=%s)
                )
                ON CONFLICT (ticker) DO UPDATE SET
                    last_updated = EXCLUDED.last_updated,
                    record_count = EXCLUDED.record_count
                """,
                (ticker, ticker, ticker),
            )
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tickers', nargs='*', help='Specific tickers (default: all stocksurferbd-source)')
    parser.add_argument('--since', default=None, help='Cutoff date YYYY-MM-DD; only insert rows > cutoff (default: per-ticker MAX(date))')
    parser.add_argument('--delay', type=float, default=1.5, help='Seconds between API requests')
    args = parser.parse_args()

    today = datetime.now().strftime('%Y-%m-%d')
    log(f"== fill_gap starting at {datetime.now().isoformat()} ==")
    log(f"Today: {today}")
    log(f"Cutoff override: {args.since or '(per-ticker MAX(date))'}")

    db = DatabaseManager()
    conn = db.conn
    tickers = get_target_tickers(conn, args.tickers or None)
    log(f"Tickers to process: {len(tickers)}")

    price_data = PriceData()
    total_inserted = 0
    success = 0
    no_new = 0
    failed = 0
    failed_tickers = []

    for i, ticker in enumerate(tickers, 1):
        cutoff = args.since or get_max_date(conn, ticker) or '1900-01-01'
        try:
            df = fetch_history(price_data, ticker)
            if df.empty:
                log(f"[{i}/{len(tickers)}] {ticker}: no data returned")
                failed += 1
                failed_tickers.append(ticker)
                continue

            df_gap = df[df['Date'].dt.strftime('%Y-%m-%d') > cutoff].copy()
            if df_gap.empty:
                log(f"[{i}/{len(tickers)}] {ticker}: nothing newer than {cutoff}")
                no_new += 1
            else:
                n = insert_gap_rows(conn, ticker, df_gap, today)
                total_inserted += n
                success += 1
                last = df_gap['Date'].max().strftime('%Y-%m-%d')
                log(f"[{i}/{len(tickers)}] {ticker}: +{n} rows ({cutoff} -> {last})")
        except Exception as e:
            log(f"[{i}/{len(tickers)}] {ticker}: ERROR {e}")
            failed += 1
            failed_tickers.append(ticker)

        if i < len(tickers):
            time.sleep(args.delay)

    db.close()

    log("=" * 60)
    log(f"Tickers processed : {len(tickers)}")
    log(f"Success           : {success}")
    log(f"Nothing new       : {no_new}")
    log(f"Failed            : {failed}")
    log(f"Total rows inserted: {total_inserted}")
    if failed_tickers:
        log(f"Failed tickers ({len(failed_tickers)}): {', '.join(failed_tickers[:30])}"
            + (f" ... +{len(failed_tickers)-30} more" if len(failed_tickers) > 30 else ""))
    log(f"== fill_gap done at {datetime.now().isoformat()} ==")


if __name__ == "__main__":
    main()
