"""
DSE Sniper API - FastAPI Backend
Professional full-stack architecture for stock analysis and portfolio management
"""

from fastapi import FastAPI, HTTPException, Depends
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
from src import auth
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
    # Data freshness: age of the newest OHLCV bar. Every signal/verdict in the
    # app is computed from this data, so staleness here means every page is
    # showing yesterday's (or last month's) conclusions.
    data_age_days: Optional[int] = None
    data_stale: Optional[bool] = None


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
    list_cols = ['reasons', 'early_reasons', 'breakout_reasons', 'reversal_reasons', 'overheated_reasons', 'momentum_reasons']
    dict_cols = ['v5_details', 'early_components', 'breakout_checks', 'reversal_checks', 'overheated_checks', 'momentum_checks']
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


def _format_signal_records(df):
    """Shared formatter: raw signals rows (snake_case, from signals_today OR
    signals_history) -> JSON records with frontend PascalCase keys and
    deserialised reasons/components. Used by /api/sniper-signals (today) and
    /api/sniper-signals/by-date (historical replay) so both render identically."""
    import json as _json, math as _math
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.replace({float('nan'): None})

    numeric_columns = ['projected_vol', 'price_change_pct', 'avg_volume_20', 'rvol', 'score', 'volume', 'close']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    for col in ('is_fresh_buy', 'is_fresh_early', 'breakout_signal', 'is_fresh_breakout',
                'reversal_signal', 'is_fresh_reversal', 'overheated_signal', 'is_fresh_overheated',
                'momentum_signal', 'is_fresh_momentum'):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: bool(x) if x is not None and not (isinstance(x, float) and pd.isna(x)) else False
            )

    df = df.rename(columns={
        'ticker': 'Ticker', 'close': 'Price', 'rvol': 'RVOL', 'score': 'Score',
        'signal': 'Signal', 'reasons': 'Reason', 'volume': 'Volume',
        'last_closing_vol': 'LastClosingVol', 'current_vol': 'CurrentVol',
        'projected_vol': 'ProjectedVol', 'is_market_open': 'IsMarketOpen',
        'is_intraday': 'IsIntraday', 'avg_volume_20': 'AvgVolume20',
        'price_change_pct': 'PriceChange', 'sma_200': 'SMA200',
        'nearest_support': 'NearestSupport', 'nearest_resistance': 'NearestResistance',
        'recommended_stop_loss': 'RecommendedStopLoss', 'reward_risk_ratio': 'RewardRiskRatio',
        'atr': 'ATR', 'trend_status': 'TrendStatus', 'raw_score': 'RawScore',
        'early_score': 'EarlyScore', 'early_signal': 'EarlySignal',
        'early_reasons': 'EarlyReasons', 'early_components': 'EarlyComponents',
        'is_fresh_buy': 'IsFreshBuy', 'is_fresh_early': 'IsFreshEarly',
        'prev_signal': 'PrevSignal', 'prev_early_signal': 'PrevEarlySignal',
        'signal_strength': 'SignalStrength',
        'breakout_signal': 'BreakoutSignal', 'breakout_reasons': 'BreakoutReasons',
        'breakout_checks': 'BreakoutChecks', 'is_fresh_breakout': 'IsFreshBreakout',
        'reversal_signal': 'ReversalSignal', 'reversal_reasons': 'ReversalReasons',
        'reversal_checks': 'ReversalChecks', 'is_fresh_reversal': 'IsFreshReversal',
        'overheated_signal': 'OverheatedSignal', 'overheated_reasons': 'OverheatedReasons',
        'overheated_checks': 'OverheatedChecks', 'is_fresh_overheated': 'IsFreshOverheated',
        'momentum_signal': 'MomentumSignal', 'momentum_reasons': 'MomentumReasons',
        'momentum_checks': 'MomentumChecks', 'is_fresh_momentum': 'IsFreshMomentum',
        'prev_close': 'PrevClose', 'day_low': 'DayLow', 'day_high': 'DayHigh',
        'range_position': 'RangePosition', 'recommended_entry': 'RecommendedEntry',
        'entry_quality': 'EntryQuality', 'entry_warning': 'EntryWarning',
    })

    for rcol in ('EarlyReasons', 'BreakoutReasons', 'ReversalReasons', 'OverheatedReasons', 'MomentumReasons'):
        if rcol in df.columns:
            df[rcol] = df[rcol].apply(
                lambda x: eval(x) if isinstance(x, str) and x.startswith('[') else (x or [])
            )
    def _parse_json_obj(x):
        if isinstance(x, str):
            try:
                return _json.loads(x)
            except Exception:
                return {}
        return x if isinstance(x, dict) else {}
    for ocol in ('EarlyComponents', 'BreakoutChecks', 'ReversalChecks', 'OverheatedChecks', 'MomentumChecks'):
        if ocol in df.columns:
            df[ocol] = df[ocol].apply(_parse_json_obj)
    if 'Reason' in df.columns:
        df['Reason'] = df['Reason'].apply(lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x)
    if 'v5_details' in df.columns:
        def _parse_v5(x):
            if isinstance(x, str):
                try:
                    return _json.loads(x)
                except Exception:
                    return {}
            return x if isinstance(x, dict) else {}
        df['v5_details'] = df['v5_details'].apply(_parse_v5)
    else:
        df['v5_details'] = [{}] * len(df)

    result = df.to_dict(orient="records")

    def _sanitize(o):
        if isinstance(o, float):
            return None if (_math.isinf(o) or _math.isnan(o)) else o
        if isinstance(o, dict):
            return {k: _sanitize(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_sanitize(v) for v in o]
        return o
    return _sanitize(result)


# Handle to the most recent chart-pattern scan subprocess, so we never pile
# up overlapping scans (each is a few minutes of CPU).
_pattern_scan_proc = None


def _launch_pattern_scan(label: str = "") -> None:
    """Fire-and-forget the out-of-process chart-pattern scan. No-op if one is
    still running."""
    global _pattern_scan_proc
    import os
    import subprocess
    import sys
    try:
        if _pattern_scan_proc is not None and _pattern_scan_proc.poll() is None:
            logger.info(f"📐 [{label}] Chart-pattern scan still running (pid "
                        f"{_pattern_scan_proc.pid}); skipping launch")
            return
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(root, "scan_patterns.py")
        _pattern_scan_proc = subprocess.Popen(
            [sys.executable, script], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info(f"📐 [{label}] Launched chart-pattern scan subprocess "
                    f"(pid {_pattern_scan_proc.pid})")
    except Exception as e:
        logger.error(f"❌ [{label}] Failed to launch chart-pattern scan: {e}")


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

        # v14: Bulkowski multi-week chart-pattern scan. It's CPU-bound over
        # ~430 tickers, so we run it as a DETACHED SUBPROCESS — running it
        # inline starved the web event loop and 502'd the whole site. The
        # scanner writes chart_pattern_signals on its own and exits. We skip
        # launching a new one if a prior scan is still running.
        _launch_pattern_scan(label)
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

                # v10 live tracker: log fresh reversals (EOD only) + refresh outcomes
                try:
                    from src.reversal_tracker import record_fresh_reversals, update_outcomes
                    if is_final:
                        record_fresh_reversals(db.engine, df_results)
                    update_outcomes(db.engine, db.get_stock_data)
                except Exception as e:
                    logger.error(f"reversal_tracker update failed: {e}")
                
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

            # v10 live tracker: record fresh reversals + refresh all outcomes
            try:
                from src.reversal_tracker import record_fresh_reversals, update_outcomes
                record_fresh_reversals(db.engine, df_results)
                update_outcomes(db.engine, db.get_stock_data)
            except Exception as e:
                logger.error(f"reversal_tracker startup update failed: {e}")
            
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
    
    # Schedule DSE Scraper.
    # DSE trades 10:00 AM → 2:00 PM Asia/Dhaka. Intraday scrape every 8 minutes
    # across the session (hour 10-13, fires at :00 :08 :16 :24 :32 :40 :48 :56 →
    # 10:00 … 13:56). Denser cadence than the old fixed 30-minute slots for a
    # much closer view of live prices. is_final=0. Anything after the 2:05 PM
    # final scrape is wasted, so the cadence stops here.
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour='10-13', minute='*/8', timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='intraday_scrape_8min',
        name='Intraday Scrape (every 8 min, 10:00–13:56)',
        max_instances=1,         # never overlap a still-running scrape
        coalesce=True,           # if fire times were missed, run once, not a burst
        misfire_grace_time=180,  # tolerate up to 3 min of scheduler lag
        replace_existing=True
    )

    # Final EOD scrape at 2:05 PM — 5 min after the 2:00 PM close, the last
    # meaningful read of the day. Marks data final (is_final=1). No later scrape
    # is scheduled; prices don't change once the session ends.
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=14, minute=5, timezone=BANGLADESH_TZ),
        args=[1],  # is_final = 1
        id='final_scrape_1405',
        name='Final Scrape (2:05 PM)',
        max_instances=1,
        coalesce=True,
        misfire_grace_time=180,
        replace_existing=True
    )

    # 5. SQLite -> PG backup sync at 2:30 PM BDT (post-EOD, market closed).
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
        CronTrigger(hour=14, minute=30, timezone=BANGLADESH_TZ),
        id='pg_backup_sync_1430',
        name='PG Backup Sync (2:30 PM)',
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
    logger.info("  - 10:00 AM–1:56 PM (intraday, every 8 min)")
    logger.info("  - 2:05 PM (FINAL)")
    logger.info("  - 2:30 PM (SQLite -> PG backup sync)")
    logger.info("  - Saturday 8 AM (fundamentals refresh)")

    # Get next run times
    for job_id in ['intraday_scrape_8min', 'final_scrape_1405', 'pg_backup_sync_1430']:
        job = scheduler.get_job(job_id)
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            logger.info(f"⏰ Next {job.name}: {next_run}")
    
    yield
    
    # Shutdown
    logger.info("🛑 DSE Sniper API shutting down...")
    scheduler.shutdown()
    logger.info("✅ Scheduler stopped")

# Create FastAPI app.
# The global `authenticate` dependency protects EVERY route by default — it
# only lets through CORS preflight and the login endpoint (see src/auth.py).
# This fail-closed design means new routes are authenticated unless explicitly
# added to auth._PUBLIC_PATHS.
app = FastAPI(
    title="DSE Sniper API",
    description="Algorithmic Volume Analysis System for Dhaka Stock Exchange",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(auth.authenticate)],
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

# ---------------------------------------------------------------------------
# Authentication routes
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginRequest):
    """Exchange email + password for a JWT bearer token. (Public route.)"""
    user = auth.authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth.create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


@app.get("/api/auth/me")
def read_me(user: dict = Depends(auth.current_user)):
    """Return the currently authenticated user."""
    return {"id": user["id"], "email": user["email"]}


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

        # Data freshness — calendar days since the newest bar. DSE trades
        # Sun–Thu, so >3 days means we've missed at least one full session
        # (2-day Fri/Sat weekend + buffer for a holiday).
        data_age_days = None
        data_stale = None
        if last_update:
            try:
                last_dt = datetime.strptime(str(last_update)[:10], '%Y-%m-%d')
                data_age_days = (now.date() - last_dt.date()).days
                data_stale = data_age_days > 3
            except ValueError:
                pass

        return SystemStatus(
            status="ONLINE",
            market_status=market_status,
            last_update=last_update,
            next_update=next_update,
            data_age_days=data_age_days,
            data_stale=data_stale
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
        has_breakout = 'breakout_signal' in cols
        has_reversal = 'reversal_signal' in cols
        has_overheated = 'overheated_signal' in cols
        has_momentum = 'momentum_signal' in cols

        if has_v7:
            where = ("WHERE signal IN ('BUY', 'WAIT') "
                     "OR early_signal IN ('EARLY', 'WATCH')")
            if has_breakout:
                # also surface proven breakout setups even if their legacy
                # score is low (v9 — breakout is independent of the score)
                where += " OR breakout_signal = 1"
            if has_reversal:
                # v10 — surface reversals too; oversold stocks score low on the
                # legacy engine, so without this they'd be filtered out entirely.
                where += " OR reversal_signal = 1"
            if has_overheated:
                where += " OR overheated_signal = 1"   # v11 take-profit warning
            if has_momentum:
                where += " OR momentum_signal = 1"      # v13 cheap movers
            # Rank by measured net-of-cost edge, not the legacy score: reversal
            # (+5.1%/trade net) first, breakout (+0.3% net) second, legacy
            # BUY/EARLY (negative edge) last (docs/PROFITABILITY_AUDIT.md §6-M2).
            order = "ORDER BY signal_strength DESC"
            if has_reversal and has_breakout:
                order = ("ORDER BY reversal_signal DESC, breakout_signal DESC, "
                         "signal_strength DESC")
            df = pd.read_sql_query(
                text(f"SELECT * FROM signals_today {where} {order}"),
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
            result = _format_signal_records(df)
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
# HISTORICAL REPLAY — "time machine" for past-day signals
#
# Lets the dashboard show the exact signals the system WOULD have produced on
# any past trading day (lookahead-free: the analyzer is wrapped so it only sees
# data up to that day). Results are cached per date in `signals_history` so
# stepping forward day-by-day is instant after the first (slow) computation.
# ====================================================================== #

def _compute_and_cache_signals_for_date(date: str):
    """Analyze every ticker as of `date` (data wrapped to <= date), cache rows in
    `signals_history`, and return the formatted actionable records for that day."""
    from sqlalchemy import text as _text
    db = DatabaseManager()
    try:
        cached = False
        try:
            c = pd.read_sql_query(_text("SELECT COUNT(*) AS c FROM signals_history WHERE date = :d"),
                                  db.engine, params={"d": date})
            cached = int(c['c'].iloc[0]) > 0
        except Exception:
            cached = False  # table not created yet

        if not cached:
            logger.info(f"🕰️  Computing historical signals for {date} (first time)...")
            analyzer = StockAnalyzer(db)
            try:
                paid_up_data = db.get_all_fundamentals()
            except Exception:
                paid_up_data = {}
            # Wrap get_stock_data so the WHOLE analyzer pipeline only sees data
            # up to `date` — no lookahead. analyzer.db IS this db instance.
            orig = db.get_stock_data
            db.get_stock_data = lambda t, start_date=None, end_date=None, _d=date: orig(t, end_date=_d)
            try:
                df_all = analyzer.analyze_all_tickers(paid_up_data=paid_up_data)
            finally:
                db.get_stock_data = orig
            # Keep only tickers that actually TRADED on `date` (their latest
            # capped row is `date`); others would mislabel an earlier row.
            if not df_all.empty:
                df_all = df_all[df_all['date'] == date]
            if not df_all.empty:
                prepped = _prepare_signals_for_sqlite(df_all)
                try:
                    prepped.to_sql('signals_history', db.engine, if_exists='append', index=False)
                except Exception as e:
                    # Column drift vs an older cached schema → rebuild the table.
                    logger.warning(f"signals_history append failed ({e}); rebuilding table")
                    with db.engine.begin() as conn:
                        conn.execute(_text("DROP TABLE IF EXISTS signals_history"))
                    prepped.to_sql('signals_history', db.engine, if_exists='append', index=False)
            logger.info(f"🕰️  Cached {0 if df_all.empty else len(df_all)} signals for {date}")

        # Surface reversal-only rows too (guard on column for old cached schemas).
        try:
            hcols = pd.read_sql_query(_text("SELECT * FROM signals_history WHERE date = :d LIMIT 1"),
                                      db.engine, params={"d": date}).columns.tolist()
        except Exception:
            hcols = []
        rev_clause = " OR reversal_signal = 1" if 'reversal_signal' in hcols else ""
        oh_clause = " OR overheated_signal = 1" if 'overheated_signal' in hcols else ""
        mo_clause = " OR momentum_signal = 1" if 'momentum_signal' in hcols else ""
        df = pd.read_sql_query(_text(
            "SELECT * FROM signals_history WHERE date = :d AND ("
            "signal IN ('BUY','WAIT') OR early_signal IN ('EARLY','WATCH') "
            "OR breakout_signal = 1" + rev_clause + oh_clause + mo_clause + ") ORDER BY signal_strength DESC"),
            db.engine, params={"d": date})
        if df.empty:
            return []
        return _format_signal_records(df)
    finally:
        db.close()


@app.get("/api/trading-dates")
def get_trading_dates(limit: int = 150):
    """Recent trading dates (newest first) for the historical date picker."""
    from sqlalchemy import text as _text
    db = DatabaseManager()
    try:
        df = pd.read_sql_query(
            _text("SELECT DISTINCT date FROM stock_data ORDER BY date DESC LIMIT :n"),
            db.engine, params={"n": int(limit)})
        return df['date'].astype(str).str.slice(0, 10).tolist()
    except Exception as e:
        logger.error(f"get_trading_dates failed: {e}")
        return []
    finally:
        db.close()


def _compute_market_breadth(as_of: str = None):
    """Market-health = % of liquid stocks trading above their 50-day average,
    as of `as_of` (or latest). Breakouts have a much higher hit-rate when this
    is high (the regime filter from the win-rate study). Returns a dict."""
    from sqlalchemy import text as _t
    db = DatabaseManager()
    try:
        if as_of:
            mx = pd.read_sql_query(_t("SELECT MAX(date) m FROM stock_data WHERE date <= :d"),
                                   db.engine, params={"d": as_of})
        else:
            mx = pd.read_sql_query(_t("SELECT MAX(date) m FROM stock_data"), db.engine)
        maxd = str(mx['m'].iloc[0])[:10] if mx['m'].iloc[0] is not None else None
        if not maxd:
            return {'date': None, 'breadth_pct': None, 'above': 0, 'total': 0, 'label': 'UNKNOWN', 'healthy': False}
        dts = pd.read_sql_query(
            _t("SELECT DISTINCT date FROM stock_data WHERE date <= :d ORDER BY date DESC LIMIT 55"),
            db.engine, params={"d": maxd})
        start = str(dts['date'].min())[:10]
        df = pd.read_sql_query(
            _t("SELECT date, ticker, close, volume FROM stock_data WHERE date BETWEEN :s AND :e"),
            db.engine, params={"s": start, "e": maxd})
        df = df[df['close'] > 0]
        above = total = 0
        for _tkr, g in df.groupby('ticker'):
            g = g.sort_values('date')
            if len(g) < 50:
                continue
            sma50 = g['close'].tail(50).mean()
            av20 = g['volume'].tail(20).mean()
            close = g['close'].iloc[-1]
            if av20 < 50000 or close < 5:
                continue
            total += 1
            if close > sma50:
                above += 1
        breadth = round(above / total * 100, 1) if total else None
        label = ('HEALTHY' if breadth is not None and breadth >= 65
                 else 'MIXED' if breadth is not None and breadth >= 45 else 'WEAK')
        # SEASON = the master switch found in the 2026-07 weekly-system + regime
        # studies (docs/PROFITABILITY_AUDIT.md §9, [[weekly-system-regime-study]]).
        # The reversal edge — the ONLY validated net-of-cost edge on DSE — is
        # breadth-gated: it PAYS in weak tape (breadth <45: +2.5% to +7.9% net)
        # and is ≈0 in strong tape (breadth >=45). So <45 = harvest ("REVERSAL"),
        # >=45 = capital-preservation ("PRESERVATION"). This deliberately INVERTS
        # the old "high breadth = good for buying" framing, which was measured
        # backwards for the strategy that actually makes money.
        season = None
        season_note = None
        if breadth is not None:
            if breadth < 45:
                season = 'REVERSAL'
                season_note = ('Reversal season — deep-oversold bounces have a real net edge in '
                               'weak tape. Trade reversal fires; this is where the money is made.')
            else:
                season = 'PRESERVATION'
                season_note = ('Preservation season — the reversal edge is ≈0 when the market is this '
                               'strong. Ride existing winners, build the watchlist, do NOT force new buys.')
        return {'date': maxd, 'breadth_pct': breadth, 'above': above, 'total': total,
                'label': label, 'healthy': bool(breadth is not None and breadth >= 65),
                'season': season, 'season_note': season_note}
    finally:
        db.close()


# Prior (immutable) trading days are safe to cache forever; the current day is
# always recomputed. Lets the season-change flag be cheap without a new table.
_BREADTH_PRIOR_CACHE: dict = {}


def _prior_breadth(before_date: str):
    """Breadth for the latest trading day strictly before `before_date` (cached)."""
    if not before_date:
        return None
    if before_date in _BREADTH_PRIOR_CACHE:
        return _BREADTH_PRIOR_CACHE[before_date]
    from sqlalchemy import text as _t
    db = DatabaseManager()
    try:
        pv = pd.read_sql_query(
            _t("SELECT MAX(date) m FROM stock_data WHERE date < :d"),
            db.engine, params={"d": before_date})
        pd_date = str(pv['m'].iloc[0])[:10] if pv['m'].iloc[0] is not None else None
    finally:
        db.close()
    res = _compute_market_breadth(pd_date) if pd_date else None
    _BREADTH_PRIOR_CACHE[before_date] = res
    return res


@app.get("/api/market-health")
def get_market_health(date: str = None):
    """Market breadth / regime gauge (optionally as-of a past date for replay).

    Adds `season_changed` when today's season differs from the previous trading
    day's — the 'season just opened' bell so the user never has to watch breadth
    manually (weekly-system study: reversal season = the whole edge)."""
    try:
        cur = _compute_market_breadth(date)
        try:
            prev = _prior_breadth(cur.get('date')) if cur.get('season') else None
            prev_season = prev.get('season') if prev else None
            cur['prev_season'] = prev_season
            cur['season_changed'] = bool(prev_season and cur.get('season')
                                         and prev_season != cur['season'])
        except Exception as _se:
            logger.debug(f"season-change check skipped: {_se}")
            cur['prev_season'] = None
            cur['season_changed'] = False
        return cur
    except Exception as e:
        logger.error(f"market-health failed: {e}")
        return {'date': None, 'breadth_pct': None, 'above': 0, 'total': 0, 'label': 'UNKNOWN', 'healthy': False}


def _compute_sector_health(as_of: str = None):
    """Per-sector 'where is the money and how healthy is it' snapshot.

    For each sector (fundamentals.sector), over its LIQUID stocks:
      - turnover_mn / turnover_share : today's traded value — 'most trades'
      - breadth_pct                  : % above their 50-day average (health)
      - ret5 / ret20 (median)        : recent trend
      - adv_pct                      : % green today (today's direction)
      - rvol                         : today's volume vs its own 20d avg (activity)
      - strength (0-100) + condition : 0.6*breadth + 0.4*scaled-20d-momentum
    Sector breadth is just the market-breadth regime dial (the one validated
    switch) sliced by sector — descriptive context, NOT a per-sector buy edge.
    """
    from sqlalchemy import text as _t
    import numpy as _np
    db = DatabaseManager()
    try:
        sec = pd.read_sql_query(
            _t("SELECT ticker, sector FROM fundamentals WHERE sector IS NOT NULL"), db.engine)
        if as_of:
            mx = pd.read_sql_query(_t("SELECT MAX(date) m FROM stock_data WHERE date <= :d"),
                                   db.engine, params={"d": as_of})
        else:
            mx = pd.read_sql_query(_t("SELECT MAX(date) m FROM stock_data"), db.engine)
        maxd = str(mx['m'].iloc[0])[:10] if mx['m'].iloc[0] is not None else None
        if not maxd:
            return {'as_of': None, 'sectors': [], 'total_turnover_mn': 0}
        dts = pd.read_sql_query(
            _t("SELECT DISTINCT date FROM stock_data WHERE date <= :d ORDER BY date DESC LIMIT 55"),
            db.engine, params={"d": maxd})
        start = str(dts['date'].min())[:10]
        df = pd.read_sql_query(
            _t("SELECT date, ticker, close, volume, value_mn FROM stock_data "
               "WHERE date BETWEEN :s AND :e"),
            db.engine, params={"s": start, "e": maxd})
    finally:
        db.close()

    df = df[df['close'] > 0].sort_values(['ticker', 'date'])
    sector_of = dict(zip(sec['ticker'], sec['sector']))
    per = []
    for tk, g in df.groupby('ticker', sort=False):
        if len(g) < 25 or tk not in sector_of:
            continue
        close = g['close'].to_numpy(float)
        vol = g['volume'].to_numpy(float)
        val = g['value_mn'].to_numpy(float)
        sma50 = float(_np.mean(close[-50:])) if len(close) >= 50 else float(_np.mean(close))
        avgv20 = float(_np.mean(vol[-21:-1])) if len(vol) >= 21 else float(_np.mean(vol[:-1])) if len(vol) > 1 else 0.0
        c = close[-1]
        if avgv20 < 50000 or c < 5:            # same liquidity floor as market breadth
            continue
        prev = close[-2] if len(close) >= 2 else c
        ret5 = (c / close[-6] - 1) * 100 if len(close) >= 6 and close[-6] > 0 else _np.nan
        ret20 = (c / close[-21] - 1) * 100 if len(close) >= 21 and close[-21] > 0 else _np.nan
        tv = val[-1]
        if not (tv == tv) or tv <= 0:          # value_mn missing → approximate
            tv = vol[-1] * c / 1e6
        rvol = (vol[-1] / avgv20) if avgv20 > 0 else _np.nan
        per.append(dict(sector=sector_of[tk], above=c > sma50, green=c > prev,
                        ret5=ret5, ret20=ret20, turnover=tv, rvol=rvol))

    if not per:
        return {'as_of': maxd, 'sectors': [], 'total_turnover_mn': 0}
    p = pd.DataFrame(per)
    total_turnover = float(p['turnover'].sum()) or 1.0
    out = []
    for sname, g in p.groupby('sector'):
        n = len(g)
        breadth = round(100.0 * g['above'].mean(), 1)
        ret20 = float(_np.nanmedian(g['ret20']))
        ret5 = float(_np.nanmedian(g['ret5']))
        turnover = float(g['turnover'].sum())
        mom = max(0.0, min(100.0, (ret20 + 15.0) / 30.0 * 100.0))   # -15%..+15% → 0..100
        strength = round(0.6 * breadth + 0.4 * mom, 1)
        condition = ('STRONG' if strength >= 65 else 'FIRM' if strength >= 50
                     else 'SOFT' if strength >= 35 else 'WEAK')
        trend = ('up' if ret5 > 1 else 'down' if ret5 < -1 else 'flat')
        out.append({
            'sector': sname, 'stocks': n,
            'turnover_mn': round(turnover, 1),
            'turnover_share': round(100.0 * turnover / total_turnover, 1),
            'breadth_pct': breadth, 'advancers_pct': round(100.0 * g['green'].mean(), 1),
            'ret5': round(ret5, 2) if ret5 == ret5 else None,
            'ret20': round(ret20, 2) if ret20 == ret20 else None,
            'rvol': round(float(_np.nanmedian(g['rvol'])), 2),
            'strength': strength, 'condition': condition, 'trend': trend,
        })
    out.sort(key=lambda s: -s['turnover_mn'])   # most trades first
    return {'as_of': maxd, 'total_turnover_mn': round(total_turnover, 1),
            'sectors': out}


@app.get("/api/sector-health")
def get_sector_health(date: str = None):
    """Sector-rotation snapshot: which sectors have the most trades + their
    condition, so the user knows where to focus (see SectorHealth on the dash)."""
    try:
        return _compute_sector_health(date)
    except Exception as e:
        logger.error(f"sector-health failed: {e}")
        return {'as_of': None, 'sectors': [], 'total_turnover_mn': 0}


@app.get("/api/analyzed-dates")
def get_analyzed_dates():
    """Dates already cached in signals_history — these replay INSTANTLY with no
    recompute. The frontend uses this to mark which days are 'ready'."""
    from sqlalchemy import text as _text
    db = DatabaseManager()
    try:
        df = pd.read_sql_query(
            _text("SELECT DISTINCT date FROM signals_history ORDER BY date DESC"), db.engine)
        return df['date'].astype(str).str.slice(0, 10).tolist()
    except Exception:
        return []  # table doesn't exist until the first historical analysis
    finally:
        db.close()


@app.get("/api/quality-screen")
def get_quality_screen():
    """v12: 6-step fundamental quality screen (Graham/value style) over all stocks.
    Market Cap >1000Cr · Sponsor >=30% · EPS growth >=10%/yr · ROE >=15% ·
    Debt/Equity <50% · P/E <15. Returns each stock's per-step pass/fail + score."""
    from sqlalchemy import text as _t
    import math as _m
    db = DatabaseManager()
    try:
        f = pd.read_sql_query(_t("SELECT * FROM fundamentals"), db.engine)
        if f.empty:
            return {"stocks": [], "total": 0}
        def _num(x):
            try:
                x = float(x)
                return None if (_m.isnan(x) or _m.isinf(x)) else x
            except Exception:
                return None
        rows = []
        for _, r in f.iterrows():
            mc, sp = _num(r.get('market_cap')), _num(r.get('sponsor_pct'))
            g, roe = _num(r.get('eps_growth_pa')), _num(r.get('roe'))
            de, pe = _num(r.get('debt_to_equity')), _num(r.get('pe_ratio'))
            steps = {
                'market_cap': {'value': mc, 'pass': mc is not None and mc >= 10000},       # 1000 Cr (mn)
                'sponsor':    {'value': sp, 'pass': sp is not None and sp >= 30},
                'eps_growth': {'value': g,  'pass': g is not None and g >= 10},
                'roe':        {'value': roe,'pass': roe is not None and roe >= 15},
                'debt_equity':{'value': de, 'pass': de is not None and de < 50},
                'pe':         {'value': pe, 'pass': pe is not None and 0 < pe < 15},
            }
            passed = sum(1 for s in steps.values() if s['pass'])
            have = sum(1 for s in steps.values() if s['value'] is not None)
            rows.append({'ticker': r['ticker'], 'sector': r.get('sector'),
                         'passed': passed, 'have_data': have, 'steps': steps})
        rows.sort(key=lambda x: (-x['passed'], -x['have_data'], x['ticker']))
        return {"stocks": rows, "total": len(rows),
                "perfect": sum(1 for x in rows if x['passed'] == 6),
                "strong": sum(1 for x in rows if x['passed'] >= 5)}
    except Exception as e:
        logger.error(f"quality-screen failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ====================================================================== #
# LONG-TERM INVESTING — "Dividend Fortress" list
#
# Thesis (docs/LONG_TERM_STRATEGY.md): in a manipulated, mean-reverting
# market, a long unbroken CASH-dividend record is the strongest honesty
# signal available — sponsors can paint prices, but a cash dividend costs
# them real taka every year. The list ranks liquid, dividend-paying
# companies by reliability, yield, growth and balance-sheet quality.
# NOT a trading signal — a buy-and-hold shortlist refreshed weekly with
# the fundamentals scrape (dividend_history table).
# ====================================================================== #

# Bank FDR (fixed-deposit) reference rate — the risk-free bar a dividend yield
# must clear to be worth the equity risk (docs/LONG_TERM_STRATEGY.md §1). Update
# as rates move.
LT_FDR_RATE = 8.0
LT_BASKET_SIZE = 10             # §5.2: 8-12 names
LT_BASKET_MAX_PER_SECTOR = 2    # §5.2: diversify across >=4 sectors


def _compute_long_term_list():
    from sqlalchemy import text as _t
    import math as _m
    db = DatabaseManager()
    try:
        fund = pd.read_sql_query(_t("SELECT * FROM fundamentals"), db.engine)
        divs = pd.read_sql_query(
            _t("SELECT ticker, year, cash_pct, stock_pct FROM dividend_history ORDER BY ticker, year"),
            db.engine)
        # latest close + 20d avg volume per ticker (one 40-day window scan)
        mx = pd.read_sql_query(_t("SELECT MAX(date) m FROM stock_data"), db.engine)
        maxd = str(mx['m'].iloc[0])[:10]
        dts = pd.read_sql_query(
            _t("SELECT DISTINCT date FROM stock_data WHERE date <= :d ORDER BY date DESC LIMIT 25"),
            db.engine, params={"d": maxd})
        start = str(dts['date'].min())[:10]
        px = pd.read_sql_query(
            _t("SELECT ticker, date, close, volume FROM stock_data "
               "WHERE date BETWEEN :s AND :e AND close > 0"),
            db.engine, params={"s": start, "e": maxd})
    finally:
        db.close()

    latest = px.sort_values('date').groupby('ticker').agg(
        close=('close', 'last'), avg_vol20=('volume', 'mean')).reset_index()
    div_by_tk = {tk: g.set_index('year') for tk, g in divs.groupby('ticker')}
    cur_year = int(maxd[:4])

    def _n(x):
        try:
            v = float(x)
            return v if (v == v and not _m.isinf(v)) else None
        except (TypeError, ValueError):
            return None

    rows = []
    for _, f in fund.merge(latest, on='ticker', how='inner').iterrows():
        tk = f['ticker']
        g = div_by_tk.get(tk)
        if g is None or len(g) == 0:
            continue
        price, av20 = _n(f['close']), _n(f['avg_vol20'])
        face = _n(f.get('face_value'))
        eps, pe, nav = _n(f.get('eps')), _n(f.get('pe_ratio')), _n(f.get('nav'))
        roe, de, sp = _n(f.get('roe')), _n(f.get('debt_to_equity')), _n(f.get('sponsor_pct'))
        cat = (f.get('market_category') or '').strip().upper()
        mcap = _n(f.get('market_cap'))

        cash = {int(y): _n(r['cash_pct']) or 0.0 for y, r in g.iterrows()}
        years = sorted(cash)
        last_div_year = max((y for y in years if cash[y] > 0), default=None)

        # --- HARD GATES (must pass to appear at all) ---
        if price is None or face is None or face <= 0 or price <= 0:
            continue
        if cat == 'Z':
            continue                          # junk category
        if last_div_year is None or last_div_year < cur_year - 1:
            continue                          # must have paid recently
        # last-5-declared-years reliability window (uses the years DSE reports)
        win5 = [y for y in range(cur_year - 5, cur_year)]
        paid5 = sum(1 for y in win5 if cash.get(y, 0) > 0)
        if paid5 < 3:
            continue                          # too unreliable for "long-term"
        if eps is None or eps <= 0:
            continue                          # loss-makers don't compound
        if av20 is None or av20 < 10000:
            continue                          # must be sellable

        # streak of consecutive payout years ending at the last paid year
        streak = 0
        y = last_div_year
        while cash.get(y, 0) > 0:
            streak += 1
            y -= 1

        latest_cash = cash[last_div_year]
        latest_stock = _n(g.loc[last_div_year, 'stock_pct']) if last_div_year in g.index else None
        dps = latest_cash / 100.0 * face                 # taka per share
        yield_pct = dps / price * 100.0
        payout_pct = (dps / eps * 100.0) if eps and eps > 0 else None
        cash_5ago = cash.get(cur_year - 5, None)
        div_growth = ((latest_cash / cash_5ago - 1) * 100.0
                      if cash_5ago and cash_5ago > 0 else None)
        p_nav = (price / nav) if nav and nav > 0 else None

        # --- SCORE (0-100) ---
        parts = {}
        parts['reliability'] = (25 if paid5 == 5 else 15 if paid5 == 4 else 5)
        parts['streak'] = 15 if streak >= 10 else 10 if streak >= 7 else 5 if streak >= 5 else 0
        parts['yield'] = (20 if yield_pct >= 8 else 16 if yield_pct >= 6 else
                          10 if yield_pct >= 4 else 5 if yield_pct >= 2.5 else 0)
        parts['growth'] = (10 if div_growth is not None and div_growth >= 25 else
                           6 if div_growth is not None and div_growth >= 0 else 0)
        parts['earnings'] = ((5)
                             + (8 if payout_pct is not None and payout_pct <= 80 else
                                4 if payout_pct is not None and payout_pct <= 100 else 0)
                             + (7 if roe is not None and roe >= 12 else
                                4 if roe is not None and roe >= 8 else 0))
        parts['balance'] = ((4 if de is not None and de < 50 else 0)
                            + (3 if sp is not None and sp >= 30 else 0)
                            + (3 if cat == 'A' else 0))
        score = sum(parts.values())
        grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D'

        hist5 = [{'year': y, 'cash': cash.get(y) if cash.get(y, 0) > 0 else None,
                  'stock': _n(g.loc[y, 'stock_pct']) if y in g.index else None}
                 for y in range(cur_year - 5, cur_year + 1)]

        rows.append({
            'ticker': tk, 'sector': f.get('sector'), 'category': cat or None,
            'price': round(price, 2), 'face_value': face,
            'latest_div_year': last_div_year,
            'latest_cash_pct': latest_cash, 'latest_stock_pct': latest_stock,
            'dps': round(dps, 2), 'yield_pct': round(yield_pct, 2),
            'paid_5y': paid5, 'streak_years': streak,
            'div_growth_5y_pct': round(div_growth, 1) if div_growth is not None else None,
            'payout_pct': round(payout_pct, 1) if payout_pct is not None else None,
            'eps': eps, 'pe': pe, 'nav': nav,
            'p_nav': round(p_nav, 2) if p_nav is not None else None,
            'roe': roe, 'debt_to_equity': de, 'sponsor_pct': sp,
            'market_cap_cr': round(mcap / 10, 0) if mcap else None,   # mn -> Cr
            'avg_vol20': int(av20),
            'history_5y': hist5, 'total_div_years': len([y for y in years if cash[y] > 0]),
            'score': score, 'grade': grade, 'score_parts': parts,
            # §1 benchmark: does the cash yield clear a risk-free bank FDR?
            'beats_fdr': yield_pct >= LT_FDR_RATE,
        })

    rows.sort(key=lambda r: (-r['score'], -r['yield_pct']))

    # STARTER BASKET (docs/LONG_TERM_STRATEGY.md §5.2 + §6.1): the actionable
    # output of the whole list. §6.1 validated that weighting YIELD among the
    # reliable payers (the "FORT-HY" subset) was the strategy's best risk profile
    # (positive 6/6 years incl. both bears). §5.2 says diversify across >=4
    # sectors. So: from fortress-grade (A/B) names, take highest-yield first,
    # capped at 2 per sector, up to 10 names — a ready-to-buy, diversified,
    # yield-tilted portfolio. Equal-weighted, so blended yield = simple mean.
    basket, per_sector = [], {}
    for r in sorted([x for x in rows if x['grade'] in ('A', 'B')],
                    key=lambda r: -r['yield_pct']):
        sec = r['sector'] or 'Other'
        if per_sector.get(sec, 0) >= LT_BASKET_MAX_PER_SECTOR:
            continue
        basket.append(r)
        per_sector[sec] = per_sector.get(sec, 0) + 1
        if len(basket) >= LT_BASKET_SIZE:
            break
    blended_yield = round(sum(b['yield_pct'] for b in basket) / len(basket), 2) if basket else None
    basket_summary = {
        'count': len(basket),
        'sectors': sorted(per_sector.keys()),
        'sector_count': len(per_sector),
        'blended_yield_pct': blended_yield,
        'beats_fdr': bool(blended_yield is not None and blended_yield >= LT_FDR_RATE),
        # equal-weight tickers with their share of a 100% allocation
        'tickers': [{'ticker': b['ticker'], 'sector': b['sector'], 'grade': b['grade'],
                     'yield_pct': b['yield_pct'], 'price': b['price'], 'dps': b['dps'],
                     'weight_pct': round(100.0 / len(basket), 1)} for b in basket],
    }

    return {'as_of': maxd, 'universe': int(len(fund)), 'qualified': len(rows),
            'fdr_rate': LT_FDR_RATE, 'beats_fdr_count': sum(1 for r in rows if r['beats_fdr']),
            'starter_basket': basket_summary, 'stocks': rows}


@app.get("/api/long-term")
def get_long_term():
    """Dividend-fortress long-term investing list (see docs/LONG_TERM_STRATEGY.md)."""
    try:
        return _compute_long_term_list()
    except Exception as e:
        logger.error(f"long-term list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/long-term/{ticker}/dividends")
def get_dividend_history(ticker: str):
    """Full per-year dividend history for one ticker (modal drill-down)."""
    from sqlalchemy import text as _t
    import math as _m
    db = DatabaseManager()

    def _sf(v):
        # NaN/inf -> None. df.where(notna, None) does NOT work on float columns
        # (pandas re-coerces None back to NaN), and NaN is invalid JSON -> 500.
        try:
            f = float(v)
            return None if (f != f or _m.isinf(f)) else f
        except (TypeError, ValueError):
            return None

    try:
        df = pd.read_sql_query(
            _t("SELECT year, cash_pct, stock_pct FROM dividend_history "
               "WHERE ticker = :t ORDER BY year"),
            db.engine, params={"t": ticker.upper()})
        history = [{'year': int(r['year']),
                    'cash_pct': _sf(r['cash_pct']),
                    'stock_pct': _sf(r['stock_pct'])}
                   for _, r in df.iterrows()]
        return {'ticker': ticker.upper(), 'history': history}
    except Exception as e:
        logger.error(f"dividend history failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/reversal-tracker")
def get_reversal_tracker():
    """Live journal of every reversal signal + its real forward outcome.
    The honest, prospective record of whether the reversal signal works."""
    from src.reversal_tracker import get_journal
    db = DatabaseManager()
    try:
        return get_journal(db.engine)
    except Exception as e:
        logger.error(f"reversal-tracker fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/sniper-signals/by-date")
def get_sniper_signals_by_date(date: str):
    """Historical replay: the signals the system would have shown on `date`.
    Same response shape as /api/sniper-signals. Cached after first compute."""
    from sqlalchemy import text as _text
    if not date or len(date) != 10:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    db = DatabaseManager()
    try:
        has = pd.read_sql_query(_text("SELECT 1 FROM stock_data WHERE date = :d LIMIT 1"),
                                db.engine, params={"d": date})
    finally:
        db.close()
    if has.empty:
        raise HTTPException(status_code=404, detail=f"No trading data for {date} (not a trading day)")
    try:
        return _compute_and_cache_signals_for_date(date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"by-date {date} failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        # v9: confluence — which tickers also fired the proven quant breakout?
        breakout_tickers = set()
        try:
            from sqlalchemy import text as _text
            cols = pd.read_sql_query(_text("SELECT * FROM signals_today LIMIT 1"), db.engine).columns.tolist()
            if 'breakout_signal' in cols:
                bdf = pd.read_sql_query(
                    _text("SELECT ticker FROM signals_today WHERE breakout_signal = 1"), db.engine)
                breakout_tickers = set(bdf['ticker'].tolist())
        except Exception as _e:
            logger.debug(f"breakout confluence lookup skipped: {_e}")
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
                # v9: True when the independent quant engine ALSO flags a
                # breakout for this ticker — a high-conviction confluence.
                'breakout': r['ticker'] in breakout_tickers,
            })
        return out
    except Exception as e:
        logger.error(f"get_chart_signals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chart-analysis/patterns")
def get_chart_pattern_signals():
    """v14: today's Bulkowski multi-week CHART-pattern scanner. One row per
    ticker with ≥1 active formation (double bottom, H&S, triangle, flag,
    dead-cat bounce…), each with its measure-rule target and win-rate stats."""
    try:
        db = DatabaseManager()
        df = db.get_chart_pattern_signals_today()
        # v14: confluence — which tickers ALSO fire the proven quant breakout /
        # reversal signals? When a chart pattern agrees with the engine that has
        # the only positive edge in every backtest, that's the strongest tell.
        breakout_tickers, reversal_tickers = set(), set()
        risk_info = {}   # ticker -> live state for the DON'T-CHASE tags
        sector_map = {}  # ticker -> sector (for the chart-page category filter)
        try:
            sdf = pd.read_sql_query(
                "SELECT ticker, sector FROM fundamentals WHERE sector IS NOT NULL", db.engine)
            sector_map = dict(zip(sdf['ticker'], sdf['sector']))
        except Exception:
            sector_map = {}
        try:
            from sqlalchemy import text as _text
            cols = pd.read_sql_query(_text("SELECT * FROM signals_today LIMIT 1"), db.engine).columns.tolist()
            if 'breakout_signal' in cols:
                bdf = pd.read_sql_query(_text("SELECT ticker FROM signals_today WHERE breakout_signal = 1"), db.engine)
                breakout_tickers = set(bdf['ticker'].tolist())
            if 'reversal_signal' in cols:
                rdf = pd.read_sql_query(_text("SELECT ticker FROM signals_today WHERE reversal_signal = 1"), db.engine)
                reversal_tickers = set(rdf['ticker'].tolist())
            # Live state so a "rising, big target" row can warn when the stock
            # is actually LATE (overbought / extended / climax volume / thin) —
            # the decliner-anatomy markers (docs/WINNER_ANATOMY.md part 2).
            if 'overheated_checks' in cols:
                sdf = pd.read_sql_query(
                    _text("SELECT ticker, rvol, avg_volume_20, overheated_checks FROM signals_today"),
                    db.engine)
                import json as _j
                for _, sr in sdf.iterrows():
                    try:
                        oc = _j.loads(sr['overheated_checks']) if sr['overheated_checks'] else {}
                    except Exception:
                        oc = {}
                    risk_info[sr['ticker']] = {
                        'rvol': sr.get('rvol'), 'av20': sr.get('avg_volume_20'),
                        'rsi': oc.get('rsi'), 'ret20': oc.get('ret20'),
                        'ext20': oc.get('ext20'), 'heat': oc.get('heat_score'),
                    }
        except Exception as _ce:
            logger.debug(f"confluence lookup skipped: {_ce}")
        db.close()

        def _risk_tags(tk, bias):
            """Late-stage / untradeable warnings for a bullish pattern row."""
            if bias != 'bullish':
                return []
            ri = risk_info.get(tk)
            if ri is None:
                return ['NO QUANT DATA — not tracked (too thin or invalid)'] if risk_info else []
            tags = []
            def _n(x):
                try:
                    v = float(x)
                    return v if v == v else None
                except (TypeError, ValueError):
                    return None
            av20, rsi = _n(ri['av20']), _n(ri['rsi'])
            ret20, ext20, rvol = _n(ri['ret20']), _n(ri['ext20']), _n(ri['rvol'])
            if av20 is not None and av20 < 50000:
                tags.append(f'THIN {av20/1000:.0f}k shares/day — untradeable size')
            if rsi is not None and rsi >= 65:
                tags.append(f'OVERBOUGHT RSI {rsi:.0f}')
            if ret20 is not None and ret20 >= 15:
                tags.append(f'ALREADY RAN +{ret20:.0f}%/20d — you would be late')
            if ext20 is not None and ext20 >= 12:
                tags.append(f'STRETCHED +{ext20:.0f}% above 20-SMA')
            if rvol is not None and rvol >= 3:
                tags.append(f'CLIMAX VOLUME {rvol:.1f}x — how tops form')
            return tags
        if df.empty:
            return []
        from src.pattern_analyzer import DSE_STATS as _DSE_STATS
        import json as _json
        import math as _math

        def _scrub(o):
            if isinstance(o, float):
                return None if (_math.isinf(o) or _math.isnan(o)) else o
            if isinstance(o, dict):
                return {k: _scrub(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_scrub(v) for v in o]
            return o

        def _f(v):
            """JSON-safe float: NULL/NaN/inf -> None (pandas reads SQL NULL as NaN)."""
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            return None if (_math.isinf(fv) or _math.isnan(fv)) else fv

        out = []
        for _, r in df.iterrows():
            try:
                patterns = _json.loads(r['patterns']) if r['patterns'] else []
            except Exception:
                patterns = []
            try:
                summary = _json.loads(r['summary']) if r['summary'] else {}
            except Exception:
                summary = {}
            tk = r['ticker']
            # Confluence with the proven quant engine (bullish patterns only).
            confluence = None
            if r['bias'] == 'bullish':
                if tk in breakout_tickers:
                    confluence = 'breakout'
                elif tk in reversal_tickers:
                    confluence = 'reversal'
            edge = int(r['edge']) if ('edge' in r and r['edge'] is not None) else 0
            grade = r['grade'] if 'grade' in r else None
            verdict = r['verdict'] if 'verdict' in r else None
            verdict_reason = r['verdict_reason'] if 'verdict_reason' in r else None
            # 2026-07-07: confluence NO LONGER boosts edge/grade/verdict in EITHER
            # direction. The dense pattern re-validation (24,781 PIT samples,
            # docs/PROFITABILITY_AUDIT.md §9) showed confirmed bullish patterns
            # return EXACTLY the universe baseline (−0.21% gross, −1.0% net) — the
            # pattern layer carries no information, so a pattern verdict must never
            # be upgraded to a buy. The reversal confluence tag is kept purely as
            # INFORMATION ("this charted stock also fired the quant reversal");
            # the buy decision belongs to the Reversals list, not this page.
            if confluence == 'reversal':
                verdict_reason = ((verdict_reason + '  ') if verdict_reason else '') + (
                    'Note: the quant REVERSAL signal also fired on this stock — that is the '
                    'validated edge (+3–4%/trade net). Act on it from the Reversals list; the '
                    'chart pattern here is visual context only.')
            out.append({
                'ticker': tk,
                'sector': sector_map.get(tk),
                'analysis_date': r['analysis_date'],
                'price': _f(r['price']),
                'bias': r['bias'],
                'has_conflict': bool(r['has_conflict']) if 'has_conflict' in r and r['has_conflict'] is not None else False,
                'confidence': r['confidence'],
                'edge': edge,
                'grade': grade,
                'verdict': verdict,
                'verdict_reason': verdict_reason,
                'room_pct': _f(r['room_pct']) if 'room_pct' in r else None,
                'confluence': confluence,
                'risk_tags': _risk_tags(tk, r['bias']),
                'dse_stats': _DSE_STATS.get(r['top_code']),
                'top_code': r['top_code'],
                'top_name': r['top_name'],
                'status': r['status'],
                'target': _f(r['target']),
                'target_pct': _f(r['target_pct']),
                'pattern_count': int(r['pattern_count']),
                'confirmed_count': int(r['confirmed_count']),
                'has_dcb': bool(r['has_dcb']),
                'patterns': _scrub(patterns),
                'summary': _scrub(summary),
            })
        # Re-sort so confluence + edge lead the list (grade already reflects it).
        out.sort(key=lambda x: (x['edge'], x['status'] == 'confirmed'), reverse=True)
        return out
    except Exception as e:
        logger.error(f"get_chart_pattern_signals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chart-analysis/{ticker}")
def get_chart_signal_detail(ticker: str):
    """Full chart-analysis breakdown for one ticker.

    Lookup order:
      1. Cached row in chart_signals (latest analysis_date)
      2. If not found, run ChartAnalyzer.analyze_ticker() on demand.
         This supports user-initiated search for tickers that didn't
         fire any patterns today (they're filtered out of the stored
         signals list) but still have valid OHLCV history.
      3. If even on-demand analysis can't produce a result (no data /
         insufficient history / broken OHLC) → 404."""
    ticker_u = ticker.upper()
    try:
        db = DatabaseManager()

        # Full history — the chart-pattern engine needs months of bars.
        hist = db.get_stock_data(ticker_u)

        sig = db.get_chart_signal(ticker_u)
        if not sig:
            # Fall through: on-demand candlestick analysis
            from src.chart_analyzer import ChartAnalyzer
            analyzer = ChartAnalyzer(db)
            sig = analyzer.analyze_ticker(ticker_u, df=hist if hist is not None and not hist.empty else None)

        # Multi-week Bulkowski chart patterns — merged onto the same payload.
        chart_patterns, chart_summary = [], None
        try:
            from src.pattern_analyzer import PatternAnalyzer
            if hist is not None and not hist.empty:
                pa = PatternAnalyzer().analyze(hist)
                chart_patterns = pa.get('chart_patterns', [])
                chart_summary = pa.get('chart_pattern_summary')
        except Exception as _pe:
            logger.warning(f"pattern engine failed for {ticker_u}: {_pe}")

        # Confluence + live-state risk tags — the SAME logic the list endpoint
        # applies, so the modal never disagrees with the row the user clicked
        # (list said "BUY SETUP 🚀 REV" → modal must too, and vice versa).
        confluence = None
        risk_tags = []
        try:
            from sqlalchemy import text as _text
            srow = pd.read_sql_query(
                _text("SELECT * FROM signals_today WHERE ticker = :t"),
                db.engine, params={'t': ticker_u})
            if not srow.empty:
                sr = srow.iloc[0]
                if 'reversal_signal' in srow.columns and sr.get('reversal_signal') == 1:
                    confluence = 'reversal'
                elif 'breakout_signal' in srow.columns and sr.get('breakout_signal') == 1:
                    confluence = 'breakout'
                # Decliner-anatomy tags (docs/WINNER_ANATOMY.md part 2).
                import json as _j
                import math as _m
                try:
                    oc = _j.loads(sr['overheated_checks']) if ('overheated_checks' in srow.columns and sr['overheated_checks']) else {}
                except Exception:
                    oc = {}
                def _n(x):
                    try:
                        v = float(x)
                        return v if (v == v and not _m.isinf(v)) else None
                    except (TypeError, ValueError):
                        return None
                av20 = _n(sr.get('avg_volume_20'))
                rsi, ret20 = _n(oc.get('rsi')), _n(oc.get('ret20'))
                ext20, rvol = _n(oc.get('ext20')), _n(sr.get('rvol'))
                if av20 is not None and av20 < 50000:
                    risk_tags.append(f'THIN {av20/1000:.0f}k shares/day — untradeable size')
                if rsi is not None and rsi >= 65:
                    risk_tags.append(f'OVERBOUGHT RSI {rsi:.0f}')
                if ret20 is not None and ret20 >= 15:
                    risk_tags.append(f'ALREADY RAN +{ret20:.0f}%/20d — you would be late')
                if ext20 is not None and ext20 >= 12:
                    risk_tags.append(f'STRETCHED +{ext20:.0f}% above 20-SMA')
                if rvol is not None and rvol >= 3:
                    risk_tags.append(f'CLIMAX VOLUME {rvol:.1f}x — how tops form')
            else:
                # Same tag the list shows: the quant engine skipped this ticker
                # entirely (too thin / broken data), so none of the live-state
                # checks above could even run. Only meaningful if the quant
                # scan ran at all today.
                nrow = pd.read_sql_query(_text("SELECT COUNT(*) AS c FROM signals_today"), db.engine)
                if int(nrow.iloc[0]['c']) > 0:
                    risk_tags.append('NO QUANT DATA — not tracked (too thin or invalid)')
        except Exception as _cfe:
            logger.debug(f"detail confluence lookup skipped for {ticker_u}: {_cfe}")

        # 2026-07-07: no confluence upgrade in either direction (mirrors the list
        # endpoint). The dense pattern re-validation (PROFITABILITY_AUDIT §9)
        # showed bullish patterns carry no net edge, so a pattern verdict is never
        # upgraded to a buy. Reversal confluence stays an informational note only;
        # the buy belongs to the Reversals list.
        if confluence == 'reversal':
            for p in chart_patterns:
                if p.get('bias') == 'bullish':
                    p['verdict_reason'] = ((p.get('verdict_reason') + '  ') if p.get('verdict_reason') else '') + (
                        'Note: the quant REVERSAL signal also fired on this stock — that is the '
                        'validated edge. Act on it from the Reversals list; this pattern is visual '
                        'context only.')

        # Wyckoff structure CONTEXT (annotation only — validated 2019-26:
        # these entries have no net edge on DSE, so this never says "buy";
        # it describes the accumulation structure. PROFITABILITY_AUDIT §7.)
        wyckoff = None
        try:
            from src.wyckoff_analyzer import detect_wyckoff_long
            if hist is not None and not hist.empty:
                w = detect_wyckoff_long(hist)
                if w['checks'].get('support') is not None or w['event']:
                    wyckoff = {
                        'event': w['event'],
                        'in_structure': w['checks'].get('support') is not None,
                        'checks': w['checks'],
                        'note': ('Structure context only — a 2019–2026 DSE backtest of '
                                 'these Wyckoff entries showed no positive edge net of '
                                 'costs. Use the range/spring info as context, not as a '
                                 'buy trigger.'),
                    }
        except Exception as _we:
            logger.warning(f"wyckoff context failed for {ticker_u}: {_we}")

        db.close()

        if not sig:
            # No candlestick signal — but chart patterns alone may exist.
            if chart_patterns:
                return {
                    'ticker': ticker_u, 'analysis_date': None,
                    'overall_score': 0, 'overall_bias': chart_summary.get('bias') if chart_summary else 'neutral',
                    'confidence': 'NONE', 'pattern_count': 0, 'price': None,
                    'patterns': [], 'context': {}, 'explanation': '',
                    'chart_patterns': chart_patterns, 'chart_pattern_summary': chart_summary,
                    'wyckoff': wyckoff,
                    'confluence': confluence, 'risk_tags': risk_tags,
                }
            raise HTTPException(
                status_code=404,
                detail=f"Cannot analyse {ticker_u}: ticker not found, insufficient history, or stale data."
            )
        sig['chart_patterns'] = chart_patterns
        sig['chart_pattern_summary'] = chart_summary
        sig['wyckoff'] = wyckoff
        sig['confluence'] = confluence
        sig['risk_tags'] = risk_tags
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

@app.get("/api/score-history/{ticker}")
def get_score_history(ticker: str, days: int = 20):
    """Replay the analyzer day-by-day to show how a ticker's MAIN score and
    EarlyScore evolved over the last `days` trading days."""
    try:
        ticker_u = (ticker or '').upper().strip()
        if not ticker_u:
            raise HTTPException(status_code=400, detail="ticker is required")

        db = DatabaseManager()
        analyzer = StockAnalyzer(db)

        paid_up_capital = db.get_all_fundamentals().get(ticker_u)
        result = analyzer.score_history(
            ticker=ticker_u,
            days=days,
            paid_up_capital=paid_up_capital,
        )
        db.close()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_score_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio")
def get_portfolio(user_id: int = Depends(auth.current_user_id)):
    """Get current portfolio holdings with live P/L and Level 2 sell logic details"""
    try:
        pm = PortfolioManager()
        portfolio_df = pm.get_portfolio(user_id)
        
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
                    # A trailing stop is only "taking profit" if we are actually
                    # in profit. If price pulled back below entry, it's a trend
                    # exit AT A LOSS — labelling it TAKE_PROFIT is misleading.
                    status = 'TAKE_PROFIT' if profit_pct > 0 else 'TREND_EXIT'
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
def add_trade(trade: Trade, user_id: int = Depends(auth.current_user_id)):
    """Add a new trade to portfolio with commission calculation"""
    try:
        pm = PortfolioManager()

        result = pm.add_trade(
            user_id=user_id,
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

@app.get("/api/entry-guidance/{ticker}")
def get_entry_guidance(ticker: str):
    """Advisory buy-price guidance for the trade form.

    Returns the previous close, the current/live price, today's range, a
    recommended buy-limit and a warning when the price isn't near the day's
    low. Purely advisory — it never blocks a trade.
    """
    try:
        from src.analyzer import compute_entry_guidance
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT date, open, high, low, close, volume FROM stock_data "
            "WHERE ticker=%s ORDER BY date DESC LIMIT 5",
            (ticker.upper(),)
        )
        rows = cursor.fetchall()
        db.close()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No market data for {ticker}")

        latest = rows[0]
        d_open, d_high, d_low, d_close = latest[1], latest[2], latest[3], latest[4]
        prev_close = rows[1][4] if len(rows) >= 2 else d_open
        # 5-day VWAP from the latest rows (descending order, so just take all).
        num = sum((r[4] or 0) * (r[5] or 0) for r in rows)
        den = sum((r[5] or 0) for r in rows)
        vwap = (num / den) if den else d_close

        guidance = compute_entry_guidance(
            current_price=d_close, day_low=d_low, day_high=d_high,
            prev_close=prev_close, vwap=vwap,
        )
        guidance['ticker'] = ticker.upper()
        guidance['date'] = latest[0]
        return guidance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing entry guidance for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/purchase-history/{ticker}")
def get_purchase_history(ticker: str, user_id: int = Depends(auth.current_user_id)):
    """Get purchase history for a specific ticker"""
    try:
        pm = PortfolioManager()
        history_df = pm.get_purchase_history(user_id, ticker.upper())
        
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
def remove_trade(ticker: str, sell_price: Optional[float] = None, notes: str = "",
                 user_id: int = Depends(auth.current_user_id)):
    """Sell/remove a position — journals the sale + realized P&L in sale_history.

    sell_price is the actual fill; if omitted the latest final close is used.
    """
    try:
        pm = PortfolioManager()
        sale = pm.remove_position(user_id, ticker.upper(), sell_price=sell_price, notes=notes)

        return {
            "success": True,
            "message": f"Removed {ticker.upper()} from portfolio",
            "sale": sale,
        }

    except Exception as e:
        logger.error(f"Error removing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sale-history")
def get_sale_history(user_id: int = Depends(auth.current_user_id)):
    """Realized-P&L journal: every recorded sell + aggregate stats."""
    try:
        db = DatabaseManager()
        from sqlalchemy import text as _text
        df = pd.read_sql_query(
            _text("SELECT ticker, sell_price, quantity, commission, proceeds, cost_basis, "
                  "realized_pnl, buy_price, purchase_date, sale_date, notes "
                  "FROM sale_history WHERE user_id = :u ORDER BY sale_date DESC, id DESC"),
            db.engine, params={"u": user_id})
        db.close()
        sales = df.where(pd.notna(df), None).to_dict(orient='records')
        total = float(df['realized_pnl'].sum()) if len(df) else 0.0
        wins = int((df['realized_pnl'] > 0).sum()) if len(df) else 0
        return {
            "sales": sales,
            "total_realized_pnl": round(total, 2),
            "trades": len(sales),
            "wins": wins,
            "win_rate_pct": round(100.0 * wins / len(sales), 1) if sales else None,
        }
    except Exception as e:
        logger.error(f"Error getting sale history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
def get_alerts(user_id: int = Depends(auth.current_user_id)):
    """Get SELL signals (Stop Loss / Take Profit / Climax)"""
    try:
        pm = PortfolioManager()
        signals = pm.check_sell_signals(user_id, verbose=False)
        
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
def get_portfolio_summary(user_id: int = Depends(auth.current_user_id)):
    """Get portfolio summary statistics"""
    try:
        pm = PortfolioManager()
        stats = pm.get_portfolio_summary(user_id)
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
