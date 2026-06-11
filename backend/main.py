"""
DSE Sniper API - FastAPI Backend
Professional full-stack architecture for stock analysis and portfolio management
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.db_manager import DatabaseManager
from src.analyzer import StockAnalyzer
from src.chart_analyzer import ChartAnalyzer
from src.portfolio_manager import PortfolioManager
from src.stocksurfer_fetcher import StockSurferFetcher
from src.dse_scraper import run_daily_scraper
from src.pg_backup import sync_sqlite_to_pg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BANGLADESH_TZ = pytz.timezone('Asia/Dhaka')

# Global scheduler
scheduler = AsyncIOScheduler(timezone=BANGLADESH_TZ)

# Pydantic models
class Trade(BaseModel):
    ticker: str
    buy_price: float
    quantity: int
    date: Optional[str] = None
    notes: Optional[str] = ""

    @field_validator('ticker')
    @classmethod
    def _ticker_nonempty(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v or not v.replace("_", "").isalnum():
            raise ValueError("ticker must be non-empty alphanumeric")
        return v

    @field_validator('buy_price')
    @classmethod
    def _price_positive(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("buy_price must be greater than 0")
        return float(v)

    @field_validator('quantity')
    @classmethod
    def _qty_positive(cls, v: int) -> int:
        if v is None or v <= 0:
            raise ValueError("quantity must be a positive integer")
        return int(v)

class BudgetBuyRequest(BaseModel):
    ticker: str
    budget: float
    current_price: Optional[float] = None
    signal_strength: Optional[int] = 50

class SystemStatus(BaseModel):
    status: str
    market_status: str
    last_update: Optional[str] = None
    next_update: Optional[str] = None


class TickerAnalyzeRequest(BaseModel):
    ticker: str
    analysis_date: Optional[str] = None  # YYYY-MM-DD
    paid_up_capital: Optional[float] = None  # optional override

# Background task using DSE Scraper
def _prepare_signals_for_sqlite(df_results):
    """v7: serialize list and dict columns into strings/JSON so SQLite's
    bound-parameter layer can accept them. Without this the to_sql call
    raises `type 'list' is not supported` on early_reasons / early_components.
    Applies to all known list-typed and dict-typed columns produced by
    StockAnalyzer.analyze_ticker."""
    import json as _json
    df_results_copy = df_results.copy()
    list_cols = ['reasons', 'early_reasons']
    dict_cols = ['v5_details', 'early_components']
    for col in list_cols:
        if col in df_results_copy.columns:
            df_results_copy[col] = df_results_copy[col].apply(
                lambda x: str(x) if isinstance(x, list) else x
            )
    for col in dict_cols:
        if col in df_results_copy.columns:
            df_results_copy[col] = df_results_copy[col].apply(
                lambda x: _json.dumps(x) if isinstance(x, dict) else x
            )
    return df_results_copy


def run_chart_analysis(label: str = "") -> int:
    """Run the independent chart-pattern engine and persist its output.
    Returns the number of tickers with detected patterns (0 on failure)."""
    try:
        db = DatabaseManager()
        analyzer = ChartAnalyzer(db)
        results = analyzer.analyze_all_tickers()
        analyzer.save_results(results)
        logger.info(f"📈 [{label}] Chart analysis: {len(results)} tickers with patterns")
        db.close()
        return len(results)
    except Exception as e:
        logger.error(f"❌ [{label}] Chart analysis FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


async def scheduled_scraper_and_analysis(is_final: int = 0):
    """
    Run DSE scraper and analysis
    
    Args:
        is_final: 0 for intraday, 1 for final EOD
    """
    try:
        update_type = "FINAL" if is_final else "INTRADAY"
        logger.info(f"⏰ Starting scraper [{update_type}]...")
        
        # Run DSE scraper
        success = await asyncio.to_thread(run_daily_scraper, is_final)
        
        if not success:
            logger.error("❌ Scraper failed")
            return
        
        # Run analysis after scraping
        try:
            db = DatabaseManager()
            analyzer = StockAnalyzer(db)
            
            # v6: Load fundamentals for Low Float scoring
            paid_up_data = db.get_all_fundamentals()
            logger.info(f"[{update_type}] Loaded fundamentals for {len(paid_up_data)} tickers")
            df_results = analyzer.analyze_all_tickers(paid_up_data=paid_up_data)
            
            logger.info(f"[{update_type}] Analysis returned: {len(df_results)} results")
            
            if not df_results.empty:
                # v7: serialize list/dict columns (reasons, early_reasons,
                # v5_details, early_components) before SQLite write.
                df_results_copy = _prepare_signals_for_sqlite(df_results)

                # Save to database (pandas requires the SQLAlchemy engine for PG).
                df_results_copy.to_sql('signals_today', db.engine, if_exists='replace', index=False)

                # Verify save
                cursor = db.conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM signals_today')
                count = cursor.fetchone()[0]

                logger.info(f"✅ [{update_type}] Analysis: {len(df_results)} signals generated")
                logger.info(f"✅ [{update_type}] Verified: {count} signals saved to signals_today")
                
                # Count signal types
                buy_count = len(df_results[df_results['signal'] == 'BUY'])
                wait_count = len(df_results[df_results['signal'] == 'WAIT'])
                logger.info(f"   [{update_type}] BUY signals: {buy_count}, WAIT signals: {wait_count}")
            else:
                logger.warning(f"⚠️  [{update_type}] No signals generated - DataFrame empty")
                logger.warning(f"   Possible reasons: All stocks below 200 SMA or insufficient data")

            db.close()

            # Independent chart-pattern engine runs after every scrape — its
            # own pipeline, own table. Failures here do NOT affect the quant
            # signals; they're logged and swallowed.
            await asyncio.to_thread(run_chart_analysis, update_type)
            
        except Exception as e:
            logger.error(f"❌ [{update_type}] Analysis FAILED: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        logger.info(f"✅ Scraper and analysis completed [{update_type}]")
        logger.info("🔄 Data refresh complete - fresh connections will be used on next API call")
        
    except Exception as e:
        logger.error(f"❌ Scraper failed: {e}")

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("🚀 DSE Sniper API starting up...")
    from src.db_manager import SQLITE_PATH
    _pg_host = os.environ.get('DATABASE_URL', '').split('@')[-1].split('/')[0] or '(unset)'
    logger.info(f"📊 Primary DB: sqlite @ {SQLITE_PATH}")
    logger.info(f"📦 Backup DB: postgres @ {_pg_host}")
    
    # Run initial analysis on startup
    logger.info("📊 Running initial analysis...")
    analysis_success = False
    try:
        db = DatabaseManager()
        analyzer = StockAnalyzer(db)
        
        # v6: Load fundamentals for Low Float scoring
        paid_up_data = db.get_all_fundamentals()
        logger.info(f"Loaded fundamentals for {len(paid_up_data)} tickers")
        df_results = analyzer.analyze_all_tickers(paid_up_data=paid_up_data)
        
        logger.info(f"Analysis complete: {len(df_results)} results returned")
        
        if not df_results.empty:
            # v7: serialize list/dict columns (reasons, early_reasons,
            # v5_details, early_components) before SQLite write.
            df_results_copy = _prepare_signals_for_sqlite(df_results)

            # Save to database (SQLAlchemy engine required for PostgreSQL).
            df_results_copy.to_sql('signals_today', db.engine, if_exists='replace', index=False)

            # Verify save
            cursor = db.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM signals_today')
            count = cursor.fetchone()[0]

            logger.info(f"✅ Initial analysis completed: {len(df_results)} signals generated")
            logger.info(f"✅ Verified: {count} signals saved to signals_today table")
            
            # Count BUY and WAIT signals
            buy_count = len(df_results[df_results['signal'] == 'BUY'])
            wait_count = len(df_results[df_results['signal'] == 'WAIT'])
            logger.info(f"   - BUY signals: {buy_count}")
            logger.info(f"   - WAIT signals: {wait_count}")
            
            analysis_success = True
        else:
            logger.warning("⚠️  No signals generated on startup - DataFrame is empty")
            logger.warning("This could indicate:")
            logger.warning("  1. No stocks meet v4 criteria (all in downtrends)")
            logger.warning("  2. Insufficient historical data (need 200 days)")
            logger.warning("  3. Analysis logic error")

        db.close()

        # Run the chart-pattern engine on startup too so the dashboard has
        # data immediately, even before the first scrape fires.
        try:
            await asyncio.to_thread(run_chart_analysis, "STARTUP")
        except Exception as _e:
            logger.error(f"Startup chart analysis errored (non-fatal): {_e}")
        
    except Exception as e:
        logger.error(f"❌ Initial analysis FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("CRITICAL: Startup analysis failed - signals table may be empty!")
    
    if not analysis_success:
        logger.warning("⚠️  STARTUP ANALYSIS DID NOT COMPLETE SUCCESSFULLY")
        logger.warning("API will return empty signals until next scheduled update")
    
    # Schedule DSE Scraper - 4 times daily
    # 1. Morning scrape at 10:30 AM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=10, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape_1030',
        name='Morning Scrape (10:30 AM)',
        replace_existing=True
    )
    
        # 1. Morning scrape at 11:00 AM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=11, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape_1100',
        name='Morning Scrape (11 AM)',
        replace_existing=True
    )
        # 1. Morning scrape at 11:30 AM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=11, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape_1130',
        name='Morning Scrape (11:30 AM)',
        replace_existing=True
    )    # 1. Morning scrape at 12:00 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=12, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape_1200',
        name='Morning Scrape (12 PM)',
        replace_existing=True
    )
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=12, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape_1230',
        name='Morning Scrape (12:30 PM)',
        replace_existing=True
    )
    # 2. Afternoon scrape at 1:00 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=13, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='afternoon_scrape_1300',
        name='Afternoon Scrape (1 PM)',
        replace_existing=True
    )
    
        # 2. Afternoon scrape at 1:30 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=13, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='afternoon_scrape_1330',
        name='Afternoon Scrape (1:30 PM)',
        replace_existing=True
    )
        # 2. Afternoon scrape at 2:00 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=14, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='afternoon_scrape_1400',
        name='Afternoon Scrape (2 PM)',
        replace_existing=True
    )

    # 3. Pre-close scrape at 2:30 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=14, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='preclose_scrape_1430',
        name='Pre-Close Scrape (2:30 PM)',
        replace_existing=True
    )
    
        # 3. Pre-close scrape at 3:00 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=15, minute=00, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='preclose_scrape_1500',
        name='Pre-Close Scrape (3 PM)',
        replace_existing=True
    )
    # 4. Final scrape at 3:15 PM - FINAL EOD (is_final=1)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=15, minute=15, timezone=BANGLADESH_TZ),
        args=[1],  # is_final = 1
        id='final_scrape_1515',
        name='Final Scrape (3:15 PM)',
        replace_existing=True
    )

    # 5. SQLite -> PG backup sync at 4:00 PM BDT (post-EOD, market closed).
    async def scheduled_pg_backup_sync():
        try:
            logger.info("⏰ Starting SQLite -> PG backup sync...")
            result = await asyncio.to_thread(sync_sqlite_to_pg)
            logger.info(f"✅ PG backup sync complete: {result}")
        except Exception as e:
            logger.error(f"❌ PG backup sync failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    scheduler.add_job(
        scheduled_pg_backup_sync,
        CronTrigger(hour=16, minute=0, timezone=BANGLADESH_TZ),
        id='pg_backup_sync_1600',
        name='PG Backup Sync (4:00 PM)',
        replace_existing=True
    )

    # v6: Weekly fundamentals scrape — Saturday 8 AM (market closed)
    async def scheduled_fundamentals_scrape():
        try:
            from src.fundamentals_scraper import scrape_all
            logger.info("Starting weekly fundamentals scrape...")
            await asyncio.to_thread(scrape_all, delay=1.5)
            logger.info("Weekly fundamentals scrape complete")
        except Exception as e:
            logger.error(f"Fundamentals scrape failed: {e}")

    scheduler.add_job(
        scheduled_fundamentals_scrape,
        CronTrigger(day_of_week='sat', hour=8, minute=0, timezone=BANGLADESH_TZ),
        id='weekly_fundamentals',
        name='Weekly Fundamentals Scrape',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started: DSE Scraper + Weekly Fundamentals")
    logger.info("  - 11:30 AM (intraday)")
    logger.info("  - 2:00 PM (intraday)")
    logger.info("  - 3:00 PM (intraday)")
    logger.info("  - 3:15 PM (FINAL)")
    logger.info("  - 4:00 PM (SQLite -> PG backup sync)")
    logger.info("  - Saturday 8 AM (fundamentals refresh)")
    
    # Get next run times
    for job_id in ['morning_scrape', 'afternoon_scrape', 'preclose_scrape', 'final_scrape']:
        job = scheduler.get_job(job_id)
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            logger.info(f"⏰ Next {job.name}: {next_run}")
    
    yield
    
    # Shutdown
    logger.info("🛑 DSE Sniper API shutting down...")
    scheduler.shutdown()
    logger.info("✅ Scheduler stopped")

# Create FastAPI app
app = FastAPI(
    title="DSE Sniper API",
    description="Algorithmic Volume Analysis System for Dhaka Stock Exchange",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "http://localhost:12002",  # Frontend service
        "https://dse-sniper.maksudul.com"  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

@app.get("/")
def health_check() -> SystemStatus:
    """System health check and status"""
    try:
        # Get last update time from database
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Try to get last update from stock_data
        cursor.execute("SELECT MAX(date) FROM stock_data")
        result = cursor.fetchone()
        last_update = result[0] if result and result[0] else None
        
        db.close()
        
        # Get next scheduled update from all 3 jobs
        next_update = None
        job_ids = ['morning_update', 'afternoon_update', 'closing_update']
        next_times = []
        
        for job_id in job_ids:
            job = scheduler.get_job(job_id)
            if job and job.next_run_time:
                next_times.append(job.next_run_time)
        
        if next_times:
            # Get the soonest next run time
            next_run = min(next_times)
            next_update = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Determine market status (DSE trading hours: 10:00 AM - 2:30 PM)
        now = datetime.now(BANGLADESH_TZ)
        hour = now.hour
        minute = now.minute
        
        if 10 <= hour < 14 or (hour == 14 and minute <= 30):
            market_status = "OPEN"
        else:
            market_status = "CLOSED"
        
        return SystemStatus(
            status="ONLINE",
            market_status=market_status,
            last_update=last_update,
            next_update=next_update
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return SystemStatus(
            status="ONLINE",
            market_status="UNKNOWN",
            last_update=None,
            next_update=None
        )

@app.get("/api/sniper-signals")
def get_sniper_signals():
    """Get BUY signals from analysis engine"""
    try:
        db = DatabaseManager()
        
        # Fetch pre-calculated signals (use SQLAlchemy engine).
        # v7: Include EARLY/WATCH from the parallel EarlyScore engine as well.
        # Sort by signal_strength = max(score, early_score) so the best entries
        # (whether confirmed BUY or fresh EARLY) surface at the top.
        from sqlalchemy import text
        # Detect whether v7 columns exist (graceful fallback for older snapshots)
        try:
            cols = pd.read_sql_query(text("SELECT * FROM signals_today LIMIT 1"), db.engine).columns.tolist()
        except Exception:
            cols = []
        has_v7 = 'early_signal' in cols and 'signal_strength' in cols

        if has_v7:
            df = pd.read_sql_query(
                text(
                    "SELECT * FROM signals_today "
                    "WHERE signal IN ('BUY', 'WAIT') OR early_signal IN ('EARLY', 'WATCH') "
                    "ORDER BY signal_strength DESC"
                ),
                db.engine,
            )
        else:
            df = pd.read_sql_query(
                text("SELECT * FROM signals_today WHERE signal IN ('BUY', 'WAIT') ORDER BY score DESC"),
                db.engine,
            )
        
        logger.info(f"✅ Fetched {len(df)} signals from signals_today table")
        
        db.close()
        
        if df.empty:
            logger.warning("⚠️  No signals found in database")
            return []
        
        try:
            # Replace inf/-inf with NaN first, then NaN with None for JSON compatibility
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.replace({float('nan'): None})

            # Fill numeric columns with 0 (except sma_200 which stays None)
            numeric_columns = ['projected_vol', 'price_change_pct', 'avg_volume_20', 'rvol', 'score', 'volume', 'close']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = df[col].fillna(0)

            # v7.1.2: SQLite stores Python bools as ints — round-trip them
            # back to True/False so the frontend JSX conditionals
            # (`{sig.IsFreshEarly && ...}`) don't render a literal "0".
            for col in ('is_fresh_buy', 'is_fresh_early'):
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: bool(x) if x is not None and not (isinstance(x, float) and pd.isna(x)) else False
                    )
            
            logger.info(f"✅ Processed NaN values successfully")
            
            # Rename columns for frontend (including v4 fields)
            df = df.rename(columns={
                'ticker': 'Ticker',
                'close': 'Price',
                'rvol': 'RVOL',
                'score': 'Score',
                'signal': 'Signal',
                'reasons': 'Reason',
                'volume': 'Volume',
                'last_closing_vol': 'LastClosingVol',
                'current_vol': 'CurrentVol',
                'projected_vol': 'ProjectedVol',
                'is_market_open': 'IsMarketOpen',
                'is_intraday': 'IsIntraday',
                'avg_volume_20': 'AvgVolume20',
                'price_change_pct': 'PriceChange',
                'sma_200': 'SMA200',
                # v4 NEW FIELDS
                'nearest_support': 'NearestSupport',
                'nearest_resistance': 'NearestResistance',
                'recommended_stop_loss': 'RecommendedStopLoss',
                'reward_risk_ratio': 'RewardRiskRatio',
                'atr': 'ATR',
                'trend_status': 'TrendStatus',
                'raw_score': 'RawScore',
                # v7 NEW FIELDS
                'early_score': 'EarlyScore',
                'early_signal': 'EarlySignal',
                'early_reasons': 'EarlyReasons',
                'early_components': 'EarlyComponents',
                'is_fresh_buy': 'IsFreshBuy',
                'is_fresh_early': 'IsFreshEarly',
                'prev_signal': 'PrevSignal',
                'prev_early_signal': 'PrevEarlySignal',
                'signal_strength': 'SignalStrength',
            })

            # v7: deserialize EarlyReasons (stored as repr-list) and components (JSON)
            if 'EarlyReasons' in df.columns:
                df['EarlyReasons'] = df['EarlyReasons'].apply(
                    lambda x: eval(x) if isinstance(x, str) and x.startswith('[') else (x or [])
                )
            if 'EarlyComponents' in df.columns:
                def _parse_components(x):
                    if isinstance(x, str):
                        try:
                            import json as _j
                            return _j.loads(x)
                        except Exception:
                            return {}
                    return x if isinstance(x, dict) else {}
                df['EarlyComponents'] = df['EarlyComponents'].apply(_parse_components)
            
            # Format Reason (convert list to string)
            if 'Reason' in df.columns:
                df['Reason'] = df['Reason'].apply(lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x)
            
            # Deserialize v5_details JSON string back to dict for frontend
            import json as _json
            if 'v5_details' in df.columns:
                def _parse_v5(x):
                    if isinstance(x, str):
                        try:
                            return _json.loads(x)
                        except Exception:
                            return {}
                    if isinstance(x, dict):
                        return x
                    return {}
                df['v5_details'] = df['v5_details'].apply(_parse_v5)
            else:
                df['v5_details'] = [{}] * len(df)
            
            result = df.to_dict(orient="records")

            # Recursively sanitize inf/nan inside nested structures (e.g. v5_details)
            import math as _math
            def _sanitize(o):
                if isinstance(o, float):
                    if _math.isinf(o) or _math.isnan(o):
                        return None
                    return o
                if isinstance(o, dict):
                    return {k: _sanitize(v) for k, v in o.items()}
                if isinstance(o, list):
                    return [_sanitize(v) for v in o]
                return o
            result = _sanitize(result)

            logger.info(f"✅ Returning {len(result)} signals to frontend")

            return result
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR processing signals data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error processing signals: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in get_sniper_signals: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ====================================================================== #
# Chart-Pattern Analysis Engine — INDEPENDENT second opinion
#
# This is a separate scoring pipeline based on classical Japanese
# candlestick analysis. It reads from the same `stock_data` table as the
# quant scorer but writes to its own `chart_signals` table and has its
# own API surface. The two engines are intentionally NOT mixed — they
# exist to provide cross-confirmation.
# ====================================================================== #

@app.get("/api/chart-analysis/signals")
def get_chart_signals():
    """Today's chart-pattern signals (one row per ticker, latest analysis_date).
    Returns a JSON-friendly list with patterns + context parsed back to objects."""
    try:
        db = DatabaseManager()
        df = db.get_chart_signals_today()
        db.close()
        if df.empty:
            return []
        import json as _json
        import math as _math
        out = []
        for _, r in df.iterrows():
            try:
                patterns = _json.loads(r['patterns']) if r['patterns'] else []
            except Exception:
                patterns = []
            try:
                context = _json.loads(r['context']) if r['context'] else {}
            except Exception:
                context = {}

            def _scrub(o):
                if isinstance(o, float):
                    if _math.isinf(o) or _math.isnan(o):
                        return None
                    return o
                if isinstance(o, dict):
                    return {k: _scrub(v) for k, v in o.items()}
                if isinstance(o, list):
                    return [_scrub(v) for v in o]
                return o

            out.append({
                'ticker': r['ticker'],
                'analysis_date': r['analysis_date'],
                'overall_score': int(r['overall_score']),
                'overall_bias': r['overall_bias'],
                'confidence': r['confidence'],
                'pattern_count': int(r['pattern_count']),
                'price': float(r['price']) if r['price'] is not None else None,
                'patterns': _scrub(patterns),
                'context': _scrub(context),
                'explanation': r['explanation'] or '',
            })
        return out
    except Exception as e:
        logger.error(f"get_chart_signals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chart-analysis/{ticker}")
def get_chart_signal_detail(ticker: str):
    """Full chart-analysis breakdown for one ticker (latest analysis_date)."""
    try:
        db = DatabaseManager()
        sig = db.get_chart_signal(ticker.upper())
        db.close()
        if not sig:
            raise HTTPException(status_code=404, detail=f"No chart signal for {ticker}")
        return sig
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_chart_signal_detail({ticker}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chart-analysis/{ticker}/ohlcv")
def get_chart_ohlcv(ticker: str, days: int = 60):
    """OHLCV history for chart rendering. Oldest-first.
    Used by ChartDetailModal to draw the candlestick chart."""
    try:
        days = max(20, min(int(days), 365))  # clamp
        db = DatabaseManager()
        df = db.get_ohlcv_for_chart(ticker.upper(), days=days)
        db.close()
        if df.empty:
            return []
        # Convert NaNs and ints for clean JSON
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.where(pd.notna(df), None)
        rows = []
        for _, r in df.iterrows():
            o = float(r['open']) if r['open'] is not None else None
            h = float(r['high']) if r['high'] is not None else None
            l = float(r['low']) if r['low'] is not None else None
            c = float(r['close']) if r['close'] is not None else None
            # Skip stub rows from non-trading days — DSE scraper sometimes
            # writes a row with open set but high/low/close = 0, which
            # makes the chart auto-scale to absurd ranges.
            if not all(v is not None and v > 0 for v in (o, h, l, c)):
                continue
            # Also skip rows where OHLC integrity is broken
            if h < l or o < l or o > h or c < l or c > h:
                continue
            rows.append({
                'date': r['date'],
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': int(r['volume']) if r['volume'] is not None else 0,
            })
        return rows
    except Exception as e:
        logger.error(f"get_chart_ohlcv({ticker}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickers")
def get_all_tickers():
    """Return all available tickers in DB for dropdown/autocomplete."""
    try:
        db = DatabaseManager()
        tickers = db.get_all_tickers()
        db.close()
        return tickers
    except Exception as e:
        logger.error(f"Error getting tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-ticker")
def analyze_ticker_detailed(request: TickerAnalyzeRequest):
    """Analyze a single ticker and return a detailed calculation breakdown."""
    try:
        ticker = (request.ticker or '').upper().strip()
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker is required")

        db = DatabaseManager()
        analyzer = StockAnalyzer(db)

        # v6: Auto-load paid_up_capital from fundamentals if not provided
        paid_up_capital = request.paid_up_capital
        if paid_up_capital is None:
            fundamentals = db.get_all_fundamentals()
            paid_up_capital = fundamentals.get(ticker)

        result = analyzer.analyze_ticker_detailed(
            ticker=ticker,
            paid_up_capital=paid_up_capital,
            analysis_date=request.analysis_date,
        )

        db.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze_ticker_detailed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
def get_portfolio():
    """Get current portfolio holdings with live P/L and Level 2 sell logic details"""
    try:
        pm = PortfolioManager()
        portfolio_df = pm.get_portfolio()
        
        if portfolio_df.empty:
            return []
        
        # Get current prices and calculate P/L with Level 2 details
        db = DatabaseManager()
        
        results = []
        for _, position in portfolio_df.iterrows():
            try:
                ticker = position['ticker']
                
                # Get market data for ATR calculation
                cursor = db.conn.cursor()
                cursor.execute(
                    "SELECT date, close, high, low, open, volume FROM stock_data WHERE ticker=%s ORDER BY date DESC LIMIT 30",
                    (ticker,)
                )
                market_data = cursor.fetchall()
                
                if not market_data:
                    logger.warning(f"No market data for {ticker}, skipping")
                    continue
                
                # Create DataFrame for ATR calculation
                df_market = pd.DataFrame(market_data, columns=['date', 'close', 'high', 'low', 'open', 'volume'])
                
                current_price = float(df_market.iloc[0]['close'])
                current_open = float(df_market.iloc[0]['open'])
                current_volume = int(df_market.iloc[0]['volume'])
                
                # Calculate profit
                profit_pct = ((current_price - position['buy_price']) / position['buy_price']) * 100
                profit_amount = (current_price - position['buy_price']) * position['quantity']
                
                # Calculate ATR (Level 2) with error handling
                try:
                    atr = pm.calculate_atr(df_market, period=14)
                    if atr is None or pd.isna(atr):
                        atr = 0.0
                except Exception as e:
                    logger.warning(f"ATR calculation failed for {ticker}: {e}")
                    atr = 0.0
                
                # Calculate days held (Level 2)
                try:
                    days_held = pm.calculate_days_held(position['purchase_date'])
                except Exception as e:
                    logger.warning(f"Days held calculation failed for {ticker}: {e}")
                    days_held = 0
                
                # Calculate RVOL
                if len(df_market) >= 20:
                    avg_volume_20 = df_market['volume'].mean()
                    rvol = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
                else:
                    rvol = 0
                
                # Calculate stop prices
                stop_loss_price = position['buy_price'] * 0.93  # -7% Emergency Brake
                
                # Dynamic ATR-based trailing stop
                if atr > 0:
                    atr_stop_distance = 2 * atr
                    trailing_stop_price = position['highest_seen'] - atr_stop_distance
                    stop_type = f"ATR"
                else:
                    trailing_stop_price = position['highest_seen'] * 0.95
                    stop_type = "Fixed 5%"
                
                # Determine status and check for zombie
                status = 'HOLD'
                is_zombie = days_held > 10 and profit_pct < 2
                
                # Check sell conditions
                if current_price <= stop_loss_price:
                    status = 'STOP_LOSS'
                elif current_price <= trailing_stop_price:
                    status = 'TAKE_PROFIT'
                elif is_zombie:
                    status = 'ZOMBIE_WARNING'
                
                # Get total cost and commission from database with defaults
                total_cost = position.get('total_cost', position['buy_price'] * position['quantity'])
                commission_paid = position.get('commission_paid', 0)
                
                # Calculate RSI safely (optional field)
                rsi = None
                try:
                    if 'close' in df_market.columns and len(df_market) >= 14:
                        delta = df_market['close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi = 100 - (100 / (1 + rs.iloc[0]))
                        if pd.isna(rsi):
                            rsi = None
                except Exception as e:
                    logger.debug(f"RSI calculation skipped for {ticker}: {e}")
                    rsi = None
                
                results.append({
                    'ticker': ticker,
                    'buy_price': float(position['buy_price']),
                    'quantity': int(position['quantity']),
                    'highest_seen': float(position['highest_seen']),
                    'purchase_date': str(position['purchase_date']),
                    'current_price': round(current_price, 2),
                    'profit_pct': round(profit_pct, 2),
                    'profit_amount': round(profit_amount, 2),
                    'status': status,
                    # Level 2 details
                    'atr': round(float(atr), 2),
                    'days_held': int(days_held),
                    'rvol': round(float(rvol), 2),
                    'stop_loss_price': round(stop_loss_price, 2),
                    'trailing_stop_price': round(trailing_stop_price, 2),
                    'stop_type': stop_type,
                    'atr_distance': round(2 * float(atr), 2) if atr > 0 else 0,
                    'is_zombie': bool(is_zombie),
                    'volume': int(current_volume),
                    # Commission and cost details
                    'total_cost': round(float(total_cost), 2),
                    'commission_paid': round(float(commission_paid), 2),
                    # RSI (optional)
                    'rsi': round(float(rsi), 1) if rsi is not None else None
                })
                
                logger.debug(f"✅ Portfolio item processed: {ticker}")
                
            except Exception as e:
                logger.error(f"Error processing portfolio item {ticker}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue with next item instead of crashing
                continue
        
        db.close()
        
        logger.info(f"✅ Portfolio API: Returning {len(results)} positions")
        return results
    
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in get_portfolio: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty array instead of crashing
        return []

@app.post("/api/trade")
def add_trade(trade: Trade):
    """Add a new trade to portfolio with commission calculation"""
    try:
        pm = PortfolioManager()
        
        result = pm.add_trade(
            ticker=trade.ticker.upper(),
            buy_price=trade.buy_price,
            quantity=trade.quantity,
            date=trade.date,
            notes=trade.notes or ""
        )
        
        if result.get('success'):
            return {
                "success": True,
                "message": f"Added {trade.ticker.upper()} to portfolio",
                "details": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('error', 'Failed to add trade')
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calculate-buy")
def calculate_buy(request: BudgetBuyRequest):
    """Calculate optimal buy quantity based on budget and signal strength"""
    try:
        pm = PortfolioManager()
        db = DatabaseManager()
        
        # Get current price if not provided
        current_price = request.current_price
        if not current_price:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT close FROM stock_data WHERE ticker=%s ORDER BY date DESC LIMIT 1",
                (request.ticker.upper(),)
            )
            result = cursor.fetchone()
            if result:
                current_price = result[0]
            else:
                raise HTTPException(status_code=404, detail=f"No market data found for {request.ticker}")
        
        # Calculate optimal buy
        recommendation = pm.calculate_optimal_buy(
            ticker=request.ticker.upper(),
            current_price=current_price,
            budget=request.budget,
            signal_strength=request.signal_strength or 50
        )
        
        db.close()
        
        return recommendation
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating buy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/purchase-history/{ticker}")
def get_purchase_history(ticker: str):
    """Get purchase history for a specific ticker"""
    try:
        pm = PortfolioManager()
        history_df = pm.get_purchase_history(ticker.upper())
        
        if history_df.empty:
            return []
        
        return history_df.to_dict(orient="records")
    
    except Exception as e:
        logger.error(f"Error getting purchase history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/volume-history/{ticker}")
def get_volume_history(ticker: str):
    """Get 20-day volume history for a ticker"""
    try:
        db = DatabaseManager()
        
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT date, volume FROM stock_data WHERE ticker=%s ORDER BY date DESC LIMIT 20",
            (ticker.upper(),)
        )
        rows = cursor.fetchall()
        
        db.close()
        
        if not rows:
            return []
        
        # Convert to list of dicts
        history = [{'date': row[0], 'volume': row[1]} for row in rows]
        history.reverse()  # Oldest first
        
        return history
    
    except Exception as e:
        logger.error(f"Error getting volume history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price-history/{ticker}")
def get_price_history(ticker: str):
    """Get 20-day OHLC (open/high/low/close) history for a ticker"""
    try:
        db = DatabaseManager()

        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT date, open, high, low, close FROM stock_data WHERE ticker=%s ORDER BY date DESC LIMIT 20",
            (ticker.upper(),)
        )
        rows = cursor.fetchall()

        db.close()

        if not rows:
            return []

        history = [
            {
                'date': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
            }
            for row in rows
        ]
        history.reverse()  # Oldest first

        return history

    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/trade/{ticker}")
def remove_trade(ticker: str):
    """Remove a position from portfolio"""
    try:
        pm = PortfolioManager()
        pm.remove_position(ticker.upper())
        
        return {
            "success": True,
            "message": f"Removed {ticker.upper()} from portfolio"
        }
    
    except Exception as e:
        logger.error(f"Error removing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
def get_alerts():
    """Get SELL signals (Stop Loss / Take Profit / Climax)"""
    try:
        pm = PortfolioManager()
        signals = pm.check_sell_signals(verbose=False)
        
        # Format for frontend
        alerts = []
        for signal in signals:
            alerts.append({
                'ticker': signal['ticker'],
                'type': signal['signal_type'],
                'value': f"{signal['profit_pct']:+.1f}%",
                'action': signal['action'],
                'reason': signal['reason'],
                'urgency': signal['urgency'],
                'current_price': signal['current_price'],
                'buy_price': signal['buy_price'],
                'profit_amount': signal['profit_amount']
            })
        
        return alerts
    
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return []

@app.get("/api/portfolio/summary")
def get_portfolio_summary():
    """Get portfolio summary statistics"""
    try:
        pm = PortfolioManager()
        stats = pm.get_portfolio_summary()
        return stats
    
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fundamentals")
def get_fundamentals():
    """Get fundamentals for all tickers"""
    try:
        db = DatabaseManager()
        df = db.get_fundamentals_full()
        db.close()
        if df.empty:
            return []
        df = df.replace({float('nan'): None})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error getting fundamentals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fundamentals/{ticker}")
def get_ticker_fundamentals(ticker: str):
    """Get fundamentals for a specific ticker"""
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM fundamentals WHERE ticker = %s", (ticker.upper(),))
        cols = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        db.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"No fundamentals for {ticker}")
        return dict(zip(cols, row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fundamentals for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger-update")
async def trigger_manual_update():
    """Manually trigger data update (for testing)"""
    try:
        logger.info("Manual update triggered...")
        asyncio.create_task(scheduled_scraper_and_analysis())

        return {
            "success": True,
            "message": "Update started in background"
        }

    except Exception as e:
        logger.error(f"Error triggering update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scheduler/status")
def get_scheduler_status():
    """Get scheduler status and next run time"""
    try:
        job = scheduler.get_job('daily_update')
        
        if job:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z') if job.next_run_time else None
            
            return {
                "scheduler_running": scheduler.running,
                "next_update": next_run,
                "update_time": "14:45 (2:45 PM Bangladesh Time)"
            }
        else:
            return {
                "scheduler_running": scheduler.running,
                "next_update": None,
                "update_time": "14:45 (2:45 PM Bangladesh Time)"
            }
    
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=12001)
