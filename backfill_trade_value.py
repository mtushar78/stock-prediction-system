"""
One-time backfill: populate trade_count and value_mn for historical data.

Uses stocksurferbd to download full history per ticker, then UPDATEs
existing rows in stock_data (does NOT overwrite OHLCV data).

Usage: python backfill_trade_value.py
       python backfill_trade_value.py GP BATBC  # specific tickers only
"""

import sys
import os
import time
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.db_manager import DatabaseManager

try:
    from stocksurferbd import PriceData
except ImportError:
    print("stocksurferbd not installed. Run: pip install stocksurferbd")
    sys.exit(1)


def backfill_ticker(ticker: str, price_data: PriceData, db_conn) -> int:
    """Download full history for a ticker and UPDATE trade_count/value_mn.

    Returns number of rows updated.
    """
    temp_file = f"temp_backfill_tv_{ticker}.xlsx"

    try:
        price_data.save_history_data(ticker, file_name=temp_file, market='DSE')

        if not os.path.exists(temp_file):
            return 0

        df = pd.read_excel(temp_file)
    finally:
        try:
            os.remove(temp_file)
        except OSError:
            pass

    if df.empty:
        return 0

    # Check if TRADE and VALUE_MN columns exist
    if 'TRADE' not in df.columns and 'VALUE_MN' not in df.columns:
        return 0

    df['DATE'] = pd.to_datetime(df['DATE'])

    cursor = db_conn.cursor()
    updated = 0

    for _, row in df.iterrows():
        date_str = row['DATE'].strftime('%Y-%m-%d')
        trade_count = None
        value_mn = None

        if 'TRADE' in df.columns:
            try:
                trade_count = int(float(str(row['TRADE']).replace(',', '')))
            except (ValueError, TypeError):
                pass

        if 'VALUE_MN' in df.columns:
            try:
                value_mn = float(str(row['VALUE_MN']).replace(',', ''))
            except (ValueError, TypeError):
                pass

        if trade_count is not None or value_mn is not None:
            cursor.execute("""
                UPDATE stock_data
                SET trade_count = COALESCE(%s, trade_count),
                    value_mn = COALESCE(%s, value_mn)
                WHERE ticker = %s AND date = %s AND (trade_count IS NULL OR value_mn IS NULL)
            """, (trade_count, value_mn, ticker, date_str))
            updated += cursor.rowcount

    db_conn.commit()
    return updated


def main():
    db = DatabaseManager()
    price_data = PriceData()

    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        tickers = db.get_all_tickers()

    total = len(tickers)
    success = 0
    total_updated = 0
    failed = 0

    print(f"Backfilling trade_count & value_mn for {total} tickers...")
    print("=" * 60)

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{total}] {ticker}", end=" ... ", flush=True)
        try:
            count = backfill_ticker(ticker, price_data, db.conn)
            print(f"updated {count} rows")
            total_updated += count
            success += 1
        except Exception as e:
            try:
                db.conn.rollback()
            except Exception:
                pass
            print(f"FAILED: {e}")
            failed += 1

        if i < total:
            time.sleep(2.0)

    db.close()

    print("\n" + "=" * 60)
    print(f"Tickers processed: {success}/{total} (failed: {failed})")
    print(f"Total rows updated: {total_updated}")
    print("=" * 60)


if __name__ == "__main__":
    main()
