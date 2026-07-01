"""
Standalone chart-pattern scan — run OUT OF PROCESS.

The Bulkowski multi-week pattern scan across ~430 tickers is CPU-bound
(hundreds of full-history DB reads + zigzag + detectors). Running it inside
the FastAPI web process pegged a core and starved the event loop, making the
whole site return 502s for minutes after every restart/scrape.

So the web process launches THIS as a detached subprocess (fire-and-forget)
instead. It has its own interpreter/GIL, writes the results to
chart_pattern_signals, and exits. The site stays responsive throughout.

Run directly:  python scan_patterns.py
"""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pattern-scan] %(levelname)s %(message)s",
)
logger = logging.getLogger("scan_patterns")


def main() -> int:
    t0 = time.time()
    try:
        from src.db_manager import DatabaseManager
        from src.pattern_analyzer import PatternAnalyzer
    except Exception as e:  # pragma: no cover
        logger.error("import failed: %s", e)
        return 1
    try:
        db = DatabaseManager()
        rows = PatternAnalyzer().analyze_all(db)
        db.save_chart_pattern_signals_bulk(rows)
        db.close()
        logger.info("chart-pattern scan done: %d tickers with formations in %.1fs",
                    len(rows), time.time() - t0)
        return 0
    except Exception as e:
        logger.error("chart-pattern scan failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
