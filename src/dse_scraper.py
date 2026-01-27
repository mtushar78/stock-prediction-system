"""
DSE Daily Data Scraper
Scrapes stock data from DSE website and saves to CSV and database
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


def scrape_dse_data(with_agent=False):
    """Scrape stock data handling both Mobile (9 cols) and Desktop (11 cols) layouts"""
    agent_text = " [WITH AGENT]" if with_agent else ""
    print(f"🌐 Fetching data from {DSE_URL}{agent_text}...")
    
    try:
        headers = {}
        if with_agent:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            print(f"   Using User-Agent: {headers['User-Agent'][:50]}...")
        else:
            print(f"   No User-Agent (requests default)")
        
        response = requests.get(DSE_URL, proxies=PROXIES, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract date from header (e.g., "Latest Share Price On Jan 26, 2026 at 3:10 PM")
        date_str = None
        header = soup.find('h2', {'class': 'BodyHead'})
        if header:
            header_text = header.text.strip()
            # Parse "Jan 26, 2026" from the header
            try:
                import re
                match = re.search(r'On\s+([A-Za-z]+)\s+(\d+),\s+(\d{4})', header_text)
                if match:
                    month_name, day, year = match.groups()
                    # Convert month name to number
                    from datetime import datetime as dt
                    date_obj = dt.strptime(f"{month_name} {day}, {year}", "%b %d, %Y")
                    date_str = date_obj.strftime('%Y-%m-%d')
                    print(f"📅 Extracted date: {date_str}")
            except Exception as e:
                print(f"⚠️ Error parsing date from header: {e}")
        
        # Fallback to current date if parsing fails
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
            print(f"⚠️ Using fallback date: {date_str}")
        
        table = soup.find('table', {'class': 'table'})
        if not table:
            return None, None
        
        data = []
        rows = table.find_all('tr')[1:]
        
        for row in rows:
            cols = row.find_all('td')
            
            # --- THE FIX STARTS HERE ---
            # Determine View Type based on column count
            
            # DESKTOP VIEW (11 Columns) -> Volume is Index 10
            if len(cols) >= 11:
                ticker = cols[1].text.strip()
                ltp = cols[2].text.strip().replace(',', '')
                high = cols[3].text.strip().replace(',', '')
                low = cols[4].text.strip().replace(',', '')
                # Col 6 is YCP in Desktop view, not Open. 
                # Open is usually not explicitly in this scroll list, using YCP as proxy or 0
                open_price = cols[6].text.strip().replace(',', '') 
                
                # CRITICAL: Volume is at Index 10
                volume = cols[10].text.strip().replace(',', '')
                
            # MOBILE VIEW (9 Columns) -> Volume is Index 8
            elif len(cols) >= 9:
                ticker = cols[1].text.strip()
                ltp = cols[2].text.strip().replace(',', '')
                high = cols[3].text.strip().replace(',', '')
                low = cols[4].text.strip().replace(',', '')
                open_price = cols[6].text.strip().replace(',', '')
                
                # CRITICAL: Volume is at Index 8
                volume = cols[8].text.strip().replace(',', '')
            
            else:
                continue # Skip malformed rows

            # --- END FIX ---

            try:
                data.append({
                    'ticker': ticker,
                    'open': float(open_price) if open_price else 0.0,
                    'high': float(high) if high else 0.0,
                    'low': float(low) if low else 0.0,
                    'close': float(ltp) if ltp else 0.0,
                    'volume': int(float(volume)) if volume else 0
                })
            except ValueError:
                continue
        
        print(f"✅ Scraped {len(data)} stocks (Mode: {'Desktop' if with_agent else 'Mobile'})")
        return data, date_str # Assuming date_str was extracted above
        
    except Exception as e:
        print(f"❌ Error: {e}")
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
    
    print(f"💾 Saved to {csv_path}")
    return csv_path


def insert_to_database(data, date_str=None, db_path=None, is_final=1):
    """Insert scraped data into stock_data table with both volume and public_volume
    
    Args:
        data: List of dicts with 'volume' and optionally 'public_volume'
        is_final: 0 for intraday, 1 for final EOD data
    """
    if not data:
        return False
    
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    if not db_path:
        db_path = str(DATA_DIR / "dse_history.db")
    
    try:
        db = DatabaseManager(db_path)
        cursor = db.conn.cursor()
        
        inserted = 0
        for stock in data:
            try:
                public_vol = stock.get('public_volume', None)
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_data 
                    (ticker, date, open, high, low, close, volume, public_volume, is_final)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock['ticker'],
                    date_str,
                    stock['open'],
                    stock['high'],
                    stock['low'],
                    stock['close'],
                    stock['volume'],
                    public_vol,
                    is_final
                ))
                inserted += 1
            except Exception as e:
                print(f"⚠️  Error inserting {stock['ticker']}: {e}")
                continue
        
        db.conn.commit()
        db.close()
        print(f"✅ Inserted {inserted}/{len(data)} into stock_data (is_final={is_final})")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def run_daily_scraper(is_final=1):
    """Main function to run daily scraper with retry and dual volume scraping
    
    Args:
        is_final: 0 for intraday (11 AM, 1 PM, 2:30 PM), 1 for final (3:15 PM)
    """
    update_type = "FINAL" if is_final else "INTRADAY"
    print("=" * 60)
    print(f"DSE SCRAPER [{update_type}] - " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 60)
    
    # Step 1: Scrape without agent (with retry)
    data, date_str = None, None
    for attempt in range(3):
        data, date_str = scrape_dse_data(with_agent=False)
        if data and date_str:
            break
        if attempt < 2:
            print(f"⚠️ Retry {attempt + 1}/2 after 5 seconds...")
            time.sleep(5)
    
    if not data or not date_str:
        print("❌ Failed to scrape data after 3 attempts")
        return False
    
    # Step 2: Scrape with agent to get public_volume (with retry)
    print("\n" + "=" * 60)
    print("📊 Scraping public volume with user agent...")
    print("=" * 60)
    
    public_data, _ = None, None
    for attempt in range(3):
        public_data, _ = scrape_dse_data(with_agent=True)
        if public_data:
            break
        if attempt < 2:
            print(f"⚠️ Retry {attempt + 1}/2 after 5 seconds...")
            time.sleep(5)
    
    # Step 3: Merge both datasets
    if public_data:
        print("\n🔀 Merging volume data...")
        # Create lookup dict for public volumes
        public_volume_map = {stock['ticker']: stock['volume'] for stock in public_data}
        
        # Add public_volume to main data
        for stock in data:
            ticker = stock['ticker']
            if ticker in public_volume_map:
                stock['public_volume'] = public_volume_map[ticker]
            else:
                stock['public_volume'] = None
        
        print(f"✅ Merged {len(public_volume_map)} public volumes")
    else:
        print("⚠️ Public volume scraping failed, continuing with regular volume only")
    
    # Step 4: Save to CSV
    csv_path = save_to_csv(data, date_str)
    if not csv_path:
        print("❌ Failed to save CSV")
        return False
    
    # Step 5: Insert to database with both volume types
    success = insert_to_database(data, date_str, is_final=is_final)
    if not success:
        print("❌ Failed to insert to database")
        return False
    
    print("\n" + "=" * 60)
    print(f"✅ SCRAPER COMPLETED [{update_type}] - Date: {date_str}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    run_daily_scraper()
