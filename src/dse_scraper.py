"""
DSE Daily Data Scraper
Scrapes stock data from DSE website and saves to CSV and database
v6: Extracts TRADE count and VALUE_MN, removed broken dual-scrape
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db_manager import DatabaseManager
from src.dse_tls import dse_get

# Proxy configuration
PROXY_SERVER = "http://geo.iproyal.com:12321"
PROXY_USERNAME = "erYDey6Xgu9ansHq"
PROXY_PASSWORD = "KqiazP8y7cMZZW41"
proxy_url = f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@geo.iproyal.com:12321"

PROXIES = {
    "http": proxy_url,
    "https": proxy_url
}

DSE_URL = "https://www.dsebd.org/latest_share_price_scroll_l.php"
DATA_DIR = Path(__file__).parent.parent / "data"


def scrape_dse_data():
    """Scrape stock data with TRADE and VALUE_MN from DSE desktop view (11 cols).

    DSE page columns (desktop, 11 cols):
      0: #  1: TRADING CODE  2: LTP  3: HIGH  4: LOW
      5: CLOSEP  6: YCP  7: CHANGE  8: TRADE  9: VALUE(mn)  10: VOLUME
    """
    print(f"Fetching data from {DSE_URL}...")

    try:
        # Use desktop User-Agent to get the full 11-column view
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = dse_get(DSE_URL, proxies=PROXIES, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract date from header
        date_str = None
        header = soup.find('h2', {'class': 'BodyHead'})
        if header:
            import re
            match = re.search(r'On\s+([A-Za-z]+)\s+(\d+),\s+(\d{4})', header.text.strip())
            if match:
                month_name, day, year = match.groups()
                date_obj = datetime.strptime(f"{month_name} {day}, {year}", "%b %d, %Y")
                date_str = date_obj.strftime('%Y-%m-%d')
                print(f"Extracted date: {date_str}")

        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
            print(f"Using fallback date: {date_str}")

        table = soup.find('table', {'class': 'table'})
        if not table:
            return None, None

        data = []
        rows = table.find_all('tr')[1:]

        for row in rows:
            cols = row.find_all('td')

            if len(cols) >= 11:
                # Desktop view — all 11 columns available
                ticker = cols[1].text.strip()
                ltp = cols[2].text.strip().replace(',', '')
                high = cols[3].text.strip().replace(',', '')
                low = cols[4].text.strip().replace(',', '')
                open_price = cols[6].text.strip().replace(',', '')  # YCP as open proxy
                trade_count = cols[8].text.strip().replace(',', '')
                value_mn = cols[9].text.strip().replace(',', '')
                volume = cols[10].text.strip().replace(',', '')
            elif len(cols) >= 9:
                # Mobile fallback — TRADE and VALUE not available
                ticker = cols[1].text.strip()
                ltp = cols[2].text.strip().replace(',', '')
                high = cols[3].text.strip().replace(',', '')
                low = cols[4].text.strip().replace(',', '')
                open_price = cols[6].text.strip().replace(',', '')
                volume = cols[8].text.strip().replace(',', '')
                trade_count = None
                value_mn = None
            else:
                continue

            try:
                entry = {
                    'ticker': ticker,
                    'open': float(open_price) if open_price else 0.0,
                    'high': float(high) if high else 0.0,
                    'low': float(low) if low else 0.0,
                    'close': float(ltp) if ltp else 0.0,
                    'volume': int(float(volume)) if volume else 0,
                }
                if trade_count is not None:
                    entry['trade_count'] = int(float(trade_count)) if trade_count else None
                if value_mn is not None:
                    entry['value_mn'] = float(value_mn) if value_mn else None
                data.append(entry)
            except ValueError:
                continue

        view = 'Desktop' if data and 'trade_count' in data[0] else 'Mobile'
        print(f"Scraped {len(data)} stocks (Mode: {view})")
        return data, date_str

    except Exception as e:
        print(f"Error: {e}")
        return None, None


def save_to_csv(data, date_str=None):
    """Save scraped data to CSV"""
    if not data:
        return None

    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    DATA_DIR.mkdir(exist_ok=True)
    csv_path = DATA_DIR / f"dse_data_{date_str}.csv"

    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)

    print(f"Saved to {csv_path}")
    return csv_path


def insert_to_database(data, date_str=None, is_final=1):
    """Insert scraped data into stock_data table with trade_count and value_mn"""
    if not data:
        return False

    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()

        rows = [
            (
                stock['ticker'],
                date_str,
                stock['open'],
                stock['high'],
                stock['low'],
                stock['close'],
                stock['volume'],
                stock.get('trade_count'),
                stock.get('value_mn'),
                is_final,
            )
            for stock in data
        ]

        try:
            import psycopg2.extras
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO stock_data
                (ticker, date, open, high, low, close, volume, trade_count, value_mn, is_final)
                VALUES %s
                ON CONFLICT (date, ticker) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    trade_count = EXCLUDED.trade_count,
                    value_mn = EXCLUDED.value_mn,
                    is_final = EXCLUDED.is_final
                """,
                rows,
                page_size=500,
            )
            inserted = len(rows)
            db.conn.commit()
        except Exception as e:
            db.conn.rollback()
            print(f"Bulk insert failed: {e}")
            db.close()
            return False

        db.close()
        print(f"Inserted {inserted}/{len(data)} into stock_data (is_final={is_final})")
        return True

    except Exception as e:
        print(f"Database error: {e}")
        return False


def run_daily_scraper(is_final=1):
    """Run daily scraper: single scrape, save CSV, insert to DB.

    Args:
        is_final: 0 for intraday, 1 for final EOD
    """
    update_type = "FINAL" if is_final else "INTRADAY"
    print("=" * 60)
    print(f"DSE SCRAPER [{update_type}] - " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 60)

    # Scrape with retry
    data, date_str = None, None
    for attempt in range(3):
        data, date_str = scrape_dse_data()
        if data and date_str:
            break
        if attempt < 2:
            print(f"Retry {attempt + 1}/2 after 5 seconds...")
            time.sleep(5)

    if not data or not date_str:
        print("Failed to scrape data after 3 attempts")
        return False

    # Save to CSV
    csv_path = save_to_csv(data, date_str)
    if not csv_path:
        print("Failed to save CSV")
        return False

    # Insert to database
    success = insert_to_database(data, date_str, is_final=is_final)
    if not success:
        print("Failed to insert to database")
        return False

    print("\n" + "=" * 60)
    print(f"SCRAPER COMPLETED [{update_type}] - Date: {date_str}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    run_daily_scraper()
