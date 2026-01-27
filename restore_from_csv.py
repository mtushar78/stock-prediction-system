"""
Restore stock data from CSV to database
"""

import pandas as pd
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from src.db_manager import DatabaseManager

def restore_from_csv(csv_path, date_str, is_final=1):
    """
    Restore data from CSV to stock_data table
    
    Args:
        csv_path: Path to CSV file
        date_str: Date to use (YYYY-MM-DD)
        is_final: 0 for intraday, 1 for final
    """
    print(f"📂 Loading CSV: {csv_path}")
    
    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"✅ Loaded {len(df)} records")
    
    # Connect to database
    db = DatabaseManager('data/dse_history.db')
    cursor = db.conn.cursor()
    
    # Insert records
    inserted = 0
    for _, row in df.iterrows():
        try:
            public_vol = row.get('public_volume', None)
            
            cursor.execute("""
                INSERT OR REPLACE INTO stock_data 
                (ticker, date, open, high, low, close, volume, public_volume, is_final)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['ticker'],
                date_str,
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume'],
                public_vol,
                is_final
            ))
            inserted += 1
        except Exception as e:
            print(f"⚠️  Error inserting {row['ticker']}: {e}")
            continue
    
    db.conn.commit()
    db.close()
    
    print(f"✅ Inserted {inserted}/{len(df)} records into stock_data")
    print(f"📅 Date: {date_str}")
    print(f"🔖 is_final: {is_final}")
    
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 restore_from_csv.py <csv_file> [date] [is_final]")
        print("Example: python3 restore_from_csv.py data/dse_data_2026-01-26.csv 2026-01-26 1")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else '2026-01-26'
    is_final = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    print("=" * 60)
    print("CSV TO DATABASE RESTORE")
    print("=" * 60)
    
    restore_from_csv(csv_file, date, is_final)
    
    print("=" * 60)
    print("✅ RESTORE COMPLETED")
    print("=" * 60)
