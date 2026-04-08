"""
Backfill missing data for a specific date using stocksurferbd.
Usage: python backfill_date.py 2026-03-02
"""

import sys
import time
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from src.db_manager import DatabaseManager

try:
    from stocksurferbd import PriceData
except ImportError:
    print("❌ stocksurferbd not installed. Run: pip install stocksurferbd")
    sys.exit(1)

def backfill_for_date(target_date: str, delay: float = 1.5):
    """
    Fetch historical data for all tickers and insert only the target date.

    Args:
        target_date: Date string in YYYY-MM-DD format
        delay: Seconds to wait between API requests
    """
    # Validate date
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        print(f"❌ Invalid date format: {target_date}. Use YYYY-MM-DD.")
        sys.exit(1)

    db = DatabaseManager()
    tickers = db.get_all_tickers()

    if not tickers:
        print("❌ No tickers found in database.")
        db.close()
        sys.exit(1)

    print(f"📅 Backfilling data for: {target_date}")
    print(f"📊 Total tickers: {len(tickers)}")
    print("=" * 60)

    price_data = PriceData()
    success_count = 0
    skip_count = 0
    fail_count = 0
    failed_tickers = []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}", end=" ... ", flush=True)
        try:
            temp_file = f"temp_backfill_{ticker}.xlsx"
            price_data.save_history_data(ticker, file_name=temp_file, market='DSE')

            if not os.path.exists(temp_file):
                print("⚠️  no file")
                skip_count += 1
                continue

            df = pd.read_excel(temp_file)
            try:
                os.remove(temp_file)
            except:
                pass

            if df.empty:
                print("⚠️  empty")
                skip_count += 1
                continue

            # Standardise columns
            column_mapping = {
                'DATE': 'Date',
                'OPENP': 'Open',
                'HIGH': 'High',
                'LOW': 'Low',
                'CLOSEP': 'Close',
                'VOLUME': 'Volume',
                'TRADE': 'TradeCount',
                'VALUE_MN': 'ValueMN',
            }
            df = df.rename(columns=column_mapping)

            required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            if not all(c in df.columns for c in required_cols):
                print("missing columns")
                skip_count += 1
                continue

            # Include optional v6 columns if available
            extra_cols = [c for c in ['TradeCount', 'ValueMN'] if c in df.columns]

            df['Date'] = pd.to_datetime(df['Date'])
            all_cols = required_cols + extra_cols
            day_df = df[df['Date'].dt.strftime('%Y-%m-%d') == target_date][all_cols].copy()

            # Convert types for optional columns
            if 'TradeCount' in day_df.columns:
                day_df['TradeCount'] = pd.to_numeric(day_df['TradeCount'], errors='coerce').fillna(0).astype(int)
            if 'ValueMN' in day_df.columns:
                day_df['ValueMN'] = pd.to_numeric(day_df['ValueMN'], errors='coerce')

            if day_df.empty:
                print(f"⚠️  no data for {target_date}")
                skip_count += 1
                continue

            db.insert_stock_data(day_df, ticker, source="stocksurferbd_backfill", is_final=True)
            print(f"✅ inserted {len(day_df)} row(s)")
            success_count += 1

        except Exception as e:
            print(f"❌ error: {e}")
            fail_count += 1
            failed_tickers.append(ticker)

        time.sleep(delay)

    db.close()

    print("\n" + "=" * 60)
    print(f"✅ Success : {success_count}")
    print(f"⚠️  Skipped : {skip_count}")
    print(f"❌ Failed  : {fail_count}")
    if failed_tickers:
        print(f"   Failed tickers: {', '.join(failed_tickers[:20])}"
              + (f" ... +{len(failed_tickers)-20} more" if len(failed_tickers) > 20 else ""))
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python backfill_date.py YYYY-MM-DD")
        print("Example: python backfill_date.py 2026-03-02")
        sys.exit(1)

    backfill_for_date(sys.argv[1])
