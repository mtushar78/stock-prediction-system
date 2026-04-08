"""
DSE Fundamentals Scraper
Scrapes company pages from DSE website for paid-up capital, sector, etc.
Stores in the fundamentals table for use by the scoring engine.

Usage:
    python src/fundamentals_scraper.py                  # Scrape all tickers
    python src/fundamentals_scraper.py GP BATBC BXPHARMA  # Scrape specific tickers
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reuse the same proxy as dse_scraper
PROXY_USERNAME = "erYDey6Xgu9ansHq"
PROXY_PASSWORD = "KqiazP8y7cMZZW41"
proxy_url = f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@geo.iproyal.com:12321"
PROXIES = {"http": proxy_url, "https": proxy_url}

DSE_COMPANY_URL = "https://www.dsebd.org/displayCompany.php?name={ticker}"


def _parse_number(text: str):
    """Parse a number from DSE page text, handling commas and whitespace."""
    if not text:
        return None
    text = text.strip().replace(',', '').replace('\n', '').replace('\r', '')
    # Remove any trailing units like 'mn', '%', 'BDT'
    text = re.sub(r'[^\d.\-]', '', text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def scrape_ticker_fundamentals(ticker: str) -> dict:
    """Scrape a single ticker's company page from DSE.

    Returns dict with fundamental data, or None on failure.
    """
    url = DSE_COMPANY_URL.format(ticker=ticker)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Retry with backoff — DSE is flaky through proxy
    last_err = None
    for attempt in range(3):
        try:
            response = requests.get(url, proxies=PROXIES, headers=headers, timeout=45)
            response.raise_for_status()
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    else:
        raise last_err

    soup = BeautifulSoup(response.content, 'html.parser')

    # DSE company pages use <th> labels with next sibling as value
    kv = {}

    # Pattern 1: <th>Label</th> followed by sibling text/element
    for th in soup.find_all('th'):
        label = th.get_text(strip=True).lower()
        next_sib = th.find_next_sibling()
        if next_sib:
            value = next_sib.get_text(strip=True)
            if label and value:
                kv[label] = value

    # Pattern 2: <td>Label</td> followed by <td>Value</td> in same row
    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            label = tds[0].get_text(strip=True).lower()
            value = tds[1].get_text(strip=True)
            if label and value and len(label) < 80:
                kv[label] = value

    def find_value(*keywords):
        """Find a value by matching any of the keywords in the label."""
        for key, val in kv.items():
            for kw in keywords:
                if kw in key:
                    return val
        return None

    # Extract fields
    paid_up_raw = find_value('paid-up capital', 'paid up capital')
    authorized_raw = find_value('authorized capital')
    sector = find_value('sector')
    market_category = find_value('market category')
    total_shares_raw = find_value('total no. of outstanding', 'outstanding securities')
    market_cap_raw = find_value('market capitalization')
    face_value_raw = find_value('face/par value', 'face value', 'par value')
    eps_raw = find_value('earning per share', 'eps')
    pe_raw = find_value('p/e ratio')
    nav_raw = find_value('nav per share', 'nav')

    paid_up_capital = _parse_number(paid_up_raw)
    # DSE reports paid-up capital in mn BDT. Convert to Crores (÷10).
    paid_up_capital_cr = round(paid_up_capital / 10, 2) if paid_up_capital else None

    result = {
        'ticker': ticker,
        'paid_up_capital': paid_up_capital,
        'paid_up_capital_cr': paid_up_capital_cr,
        'sector': sector,
        'market_category': market_category,
        'total_shares': int(_parse_number(total_shares_raw)) if _parse_number(total_shares_raw) else None,
        'market_cap': _parse_number(market_cap_raw),
        'face_value': _parse_number(face_value_raw),
        'eps': _parse_number(eps_raw),
        'pe_ratio': _parse_number(pe_raw),
        'nav': _parse_number(nav_raw),
    }
    return result


def save_fundamentals(db: DatabaseManager, data: dict):
    """UPSERT a single ticker's fundamentals into the DB."""
    cursor = db.conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO fundamentals
            (ticker, paid_up_capital, paid_up_capital_cr, sector, market_category,
             total_shares, market_cap, face_value, eps, pe_ratio, nav, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
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
        """, (
            data['ticker'],
            data.get('paid_up_capital'),
            data.get('paid_up_capital_cr'),
            data.get('sector'),
            data.get('market_category'),
            data.get('total_shares'),
            data.get('market_cap'),
            data.get('face_value'),
            data.get('eps'),
            data.get('pe_ratio'),
            data.get('nav'),
        ))
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise


def get_missing_tickers(db: DatabaseManager) -> list:
    """Return tickers that are in stock_data but NOT in fundamentals (or have NULL paid_up_capital)."""
    cursor = db.conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT s.ticker FROM stock_data s
            LEFT JOIN fundamentals f ON s.ticker = f.ticker
            WHERE f.ticker IS NULL OR f.paid_up_capital IS NULL
            ORDER BY s.ticker
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        db.conn.rollback()
        raise


def scrape_all(tickers: list = None, delay: float = 1.5, retry_failed: bool = False):
    """Scrape fundamentals for all (or specified) tickers.

    Args:
        tickers: List of tickers to scrape. If None, scrapes all from DB.
        delay: Seconds between requests (rate limiting).
        retry_failed: If True, only scrape tickers missing from fundamentals table.
    """
    db = DatabaseManager()

    if tickers is None:
        if retry_failed:
            tickers = get_missing_tickers(db)
            print(f"Retry mode: {len(tickers)} tickers missing fundamentals")
        else:
            tickers = db.get_all_tickers()

    total = len(tickers)
    success = 0
    failed = 0
    failed_list = []

    print(f"Scraping fundamentals for {total} tickers...")
    print("=" * 60)

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{total}] {ticker}", end=" ... ", flush=True)
        try:
            data = scrape_ticker_fundamentals(ticker)
            save_fundamentals(db, data)
            cap = data.get('paid_up_capital_cr')
            sector = data.get('sector', '?')
            print(f"OK (cap={cap} Cr, sector={sector})")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
            failed_list.append(ticker)

        if i < total:
            time.sleep(delay)

    db.close()

    print("\n" + "=" * 60)
    print(f"Success: {success}/{total}")
    print(f"Failed:  {failed}/{total}")
    if failed_list:
        print(f"Failed tickers: {', '.join(failed_list[:20])}"
              + (f" ... +{len(failed_list)-20} more" if len(failed_list) > 20 else ""))
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--retry':
        # Retry only tickers missing from fundamentals table
        scrape_all(retry_failed=True, delay=2.0)
    elif len(sys.argv) > 1:
        # Scrape specific tickers
        scrape_all(tickers=[t.upper() for t in sys.argv[1:]])
    else:
        # Scrape all
        scrape_all()
