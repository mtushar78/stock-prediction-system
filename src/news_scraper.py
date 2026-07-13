"""DSE company news / price-sensitive-information (PSI) scraper.

The single authoritative feed of what actually moves DSE stocks: dividend
declarations, board meetings, AGM/record dates, credit ratings, financial
results, capital-raising, and — most valuable of all — the exchange's own
**query responses**, where DSE formally asks a company to explain an "unusual
price hike / increase in trading volume". Those queries are the closest thing
the market has to a public rumor flag: the exchange only sends them when a
stock is moving on something that isn't yet officially disclosed.

Data source
-----------
The public News Archive page renders every item server-side when a date range
is supplied:

    old_news.php?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&criteria=4&archive=news

(The bare pages — dse_news.php / news_archive_7days.php — are JavaScript-driven
and return an empty shell to a plain HTTP client, so we never use them.) The
news lives in a single ``<table class="table-news">`` whose rows are flat,
one-cell lines in the repeating shape:

    TICKER
    TICKER: Headline
    (Cont. news of TICKER): body ...
    YYYY-MM-DD              <- terminates the item

We walk the cells, cut an item on each date line, then merge consecutive
fragments that share (date, ticker, headline) — the archive frequently splits
one announcement across several blocks.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from src.dse_tls import dse_get

logger = logging.getLogger(__name__)

NEWS_URL = "https://www.dsebd.org/old_news.php"
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_TITLE_RE = re.compile(r'^([A-Z0-9&]+):\s*(.*)$')
_CONT_RE = re.compile(r'^\(Cont\.?\s*news of [^)]+\):\s*', re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Categorisation — cheap keyword routing into buckets the UI can filter on.
# Order matters: the first matching rule wins, most-specific first.
# --------------------------------------------------------------------------- #
# category, is_price_sensitive(default), matcher(regex on "title. body")
_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    # Rumor flag — the exchange querying/halting a stock, or a company denying
    # or clarifying press/rumor. Highest priority: this is the whole point.
    ('Query Response', re.compile(
        r'\bquery\b|unusual (price|trade|volume)|price hike|halt of trading|rumou?r|'
        r'clarification|no (undisclosed|price sensitive)|no undisclosed price', re.I)),
    # Routine mutual-fund NAV disclosures — high-volume noise, not real news.
    ('Fund NAV', re.compile(r'^\s*(daily|weekly|monthly)\s+nav\b|net asset value.*(weekly|monthly)', re.I)),
    ('Board Meeting', re.compile(r'board meeting', re.I)),
    ('AGM/EGM', re.compile(r'\bAGM\b|\bEGM\b|annual general|extra[\s-]?ordinary general', re.I)),
    ('Dividend', re.compile(r'dividend|bonus (share|issue)|stock dividend|entitlement', re.I)),
    ('Financial Result', re.compile(
        r'\bEPS\b|earnings per share|quarterly|half[\s-]?yearly|un[\s-]?audited|audited '
        r'financial|financial statement|net profit|net asset value|\bNOCFPS\b', re.I)),
    ('Record Date / Spot', re.compile(r'record date|spot market|book closure', re.I)),
    ('Credit Rating', re.compile(r'credit rating|entity rating', re.I)),
    ('Capital / Rights / IPO', re.compile(
        r'raising of capital|right share|rights issue|\bIPO\b|repeat public|preference share|'
        r'subscription|BSEC consent', re.I)),
    ('Corporate Action', re.compile(
        r'amalgamat|merger|acquisition|subsidiary|resign|appointment|director|land|'
        r'plant|expansion|loan|investment|winding up|litigation|court', re.I)),
]
# Categories that are NOT, on their own, price-sensitive (routine housekeeping).
_NON_PSI_CATEGORIES = {'Record Date / Spot', 'Fund NAV'}


def _categorise(title: str, body: str) -> tuple[str, bool, bool]:
    """Return (category, is_price_sensitive, is_query).

    ``is_query`` marks the exchange's own "explain your unusual price/volume"
    letters and the company's response to them — the rumor flag.
    """
    blob = f"{title}. {body}"
    is_query = bool(_CATEGORY_RULES[0][1].search(blob))
    for cat, rx in _CATEGORY_RULES:
        if rx.search(blob):
            psi = cat not in _NON_PSI_CATEGORIES
            return cat, psi, is_query
    return 'Other', False, is_query


def _news_hash(ticker: str, date: str, title: str, body: str) -> str:
    raw = f"{ticker}|{date}|{title}|{body[:200]}".encode('utf-8', 'ignore')
    return hashlib.sha1(raw).hexdigest()


def parse_news_html(html: bytes | str) -> list[dict]:
    """Parse the News Archive page HTML into structured news items."""
    soup = BeautifulSoup(html, 'html.parser')
    tbl = soup.find('table', class_='table-news')
    if tbl is None:
        return []

    cells = [td.get_text(' ', strip=True) for td in tbl.find_all('td')]
    cells = [c for c in cells if c]

    # Cut the flat cell stream into items on each terminating date line.
    raw_items: list[tuple[list[str], str]] = []
    buf: list[str] = []
    for c in cells:
        if _DATE_RE.match(c):
            if buf:
                raw_items.append((buf, c))
            buf = []
        else:
            buf.append(c)

    parsed: list[dict] = []
    for block, date in raw_items:
        if not block:
            continue
        # First "TICKER: headline" line gives ticker + title; a leading bare
        # ticker line (no colon) is redundant and skipped.
        ticker = title = None
        body_parts: list[str] = []
        for line in block:
            m = _TITLE_RE.match(line)
            if m and title is None and m.group(2):
                ticker, title = m.group(1), m.group(2).strip()
            elif m and title is None:
                ticker = m.group(1)  # bare "TICKER:" — keep ticker, wait for title
            else:
                body_parts.append(_CONT_RE.sub('', line).strip())
        if not ticker:
            continue
        title = title or (body_parts.pop(0) if body_parts else '')
        # Drop the redundant leading bare-ticker line that precedes the body.
        body_parts = [p for p in body_parts if p and p != ticker]
        body = ' '.join(body_parts).strip()
        parsed.append({'ticker': ticker, 'date': date, 'title': title, 'body': body})

    return _merge_fragments(parsed)


def _merge_fragments(items: list[dict]) -> list[dict]:
    """Merge consecutive fragments of the same announcement.

    The archive splits long items across blocks that repeat the same
    (date, ticker, title); we glue their bodies back together and drop exact
    duplicate bodies.
    """
    merged: list[dict] = []
    for it in items:
        if merged:
            last = merged[-1]
            if (last['ticker'] == it['ticker'] and last['date'] == it['date']
                    and last['title'] == it['title']):
                if it['body'] and it['body'] not in last['body']:
                    last['body'] = (last['body'] + ' ' + it['body']).strip()
                continue
        merged.append(dict(it))

    for it in merged:
        cat, psi, is_query = _categorise(it['title'], it['body'])
        it['category'] = cat
        it['is_price_sensitive'] = psi
        it['is_query'] = is_query
        it['hash'] = _news_hash(it['ticker'], it['date'], it['title'], it['body'])
    return merged


def fetch_news(start_date: str | None = None, end_date: str | None = None,
               days: int = 7) -> list[dict]:
    """Fetch + parse DSE news for a date range (default: the last `days` days).

    Returns a list of dicts: ticker, date, title, body, category,
    is_price_sensitive, is_query, hash — newest first.
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.strptime(end_date, '%Y-%m-%d')
                      - timedelta(days=days)).strftime('%Y-%m-%d')

    params = {'startDate': start_date, 'endDate': end_date,
              'criteria': '4', 'archive': 'news'}
    try:
        r = dse_get(NEWS_URL, params=params, headers=_HEADERS, timeout=40)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"news fetch failed ({start_date}..{end_date}): {e}")
        return []

    items = parse_news_html(r.content)
    # Newest first; within a day preserve archive order.
    items.sort(key=lambda x: x['date'], reverse=True)
    logger.info(f"Fetched {len(items)} news items ({start_date}..{end_date})")
    return items


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    news = fetch_news(days=7)
    print(f"\n{len(news)} items\n" + "=" * 70)
    from collections import Counter
    for cat, n in Counter(i['category'] for i in news).most_common():
        print(f"  {cat:24} {n}")
    print("=" * 70)
    for it in news[:12]:
        flag = ' [QUERY]' if it['is_query'] else (' [PSI]' if it['is_price_sensitive'] else '')
        print(f"[{it['date']}] {it['ticker']:12} {it['category']:20}{flag}")
        print(f"    {it['title'][:90]}")
