"""
DSE Sniper API - FastAPI Backend
Professional full-stack architecture for stock analysis and portfolio management
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
import sys
from pathlib import Path
import pandas as pd
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
from src.portfolio_manager import PortfolioManager
from src.stocksurfer_fetcher import StockSurferFetcher
from src.dse_scraper import run_daily_scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = str(Path(__file__).parent.parent / 'data' / 'dse_history.db')
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

# Background task using DSE Scraper
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
            db = DatabaseManager(DB_PATH)
            analyzer = StockAnalyzer(db)
            df_results = analyzer.analyze_all_tickers()
            
            if not df_results.empty:
                conn = db.get_connection()
                df_results.to_sql('signals_today', conn, if_exists='replace', index=False)
                conn.close()
                logger.info(f"✅ Analysis: {len(df_results)} signals generated")
            else:
                logger.info("No signals generated")
            
            db.close()
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
        
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
    logger.info(f"📊 Database: {DB_PATH}")
    
    # Run initial analysis on startup
    logger.info("📊 Running initial analysis...")
    try:
        db = DatabaseManager(DB_PATH)
        analyzer = StockAnalyzer(db)
        df_results = analyzer.analyze_all_tickers()
        
        if not df_results.empty:
            # Save results to signals_today table
            # Convert reasons list to string for SQL storage
            df_results_copy = df_results.copy()
            df_results_copy['reasons'] = df_results_copy['reasons'].apply(lambda x: str(x) if isinstance(x, list) else x)
            df_results_copy.to_sql('signals_today', db.conn, if_exists='replace', index=False)
            db.conn.commit()
            logger.info(f"✅ Initial analysis completed: {len(df_results)} signals generated")
        else:
            logger.warning("⚠️  No signals generated on startup")
        
        db.close()
    except Exception as e:
        logger.error(f"❌ Initial analysis failed: {e}")
    
    # Schedule DSE Scraper - 4 times daily
    # 1. Morning scrape at 11:00 AM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=11, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='morning_scrape',
        name='Morning Scrape (11 AM)',
        replace_existing=True
    )
    
    # 2. Afternoon scrape at 1:00 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=13, minute=0, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='afternoon_scrape',
        name='Afternoon Scrape (1 PM)',
        replace_existing=True
    )
    
    # 3. Pre-close scrape at 2:30 PM - INTRADAY (is_final=0)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=14, minute=30, timezone=BANGLADESH_TZ),
        args=[0],  # is_final = 0
        id='preclose_scrape',
        name='Pre-Close Scrape (2:30 PM)',
        replace_existing=True
    )
    
    # 4. Final scrape at 3:15 PM - FINAL EOD (is_final=1)
    scheduler.add_job(
        scheduled_scraper_and_analysis,
        CronTrigger(hour=15, minute=15, timezone=BANGLADESH_TZ),
        args=[1],  # is_final = 1
        id='final_scrape',
        name='Final Scrape (3:15 PM)',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("⏰ Scheduler started: DSE Scraper (4 times daily)")
    logger.info("  - 11:00 AM (intraday)")
    logger.info("  - 1:00 PM (intraday)")
    logger.info("  - 2:30 PM (intraday)")
    logger.info("  - 3:15 PM (FINAL)")
    
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
        db = DatabaseManager(DB_PATH)
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
        db = DatabaseManager(DB_PATH)
        
        # Fetch pre-calculated signals
        df = pd.read_sql(
            "SELECT * FROM signals_today WHERE signal IN ('BUY', 'WAIT') ORDER BY score DESC",
            db.conn
        )
        
        logger.info(f"✅ Fetched {len(df)} signals from signals_today table")
        
        db.close()
        
        if df.empty:
            logger.warning("⚠️  No signals found in database")
            return []
        
        try:
            # Replace ALL NaN values with None for JSON compatibility
            df = df.replace({float('nan'): None})
            
            # Fill numeric columns with 0 (except sma_200 which stays None)
            numeric_columns = ['projected_vol', 'price_change_pct', 'avg_volume_20', 'rvol', 'score', 'volume', 'close']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = df[col].fillna(0)
            
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
                'trend_status': 'TrendStatus'
            })
            
            # Format Reason (convert list to string)
            if 'Reason' in df.columns:
                df['Reason'] = df['Reason'].apply(lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x)
            
            result = df.to_dict(orient="records")
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

@app.get("/api/portfolio")
def get_portfolio():
    """Get current portfolio holdings with live P/L and Level 2 sell logic details"""
    try:
        pm = PortfolioManager(DB_PATH)
        portfolio_df = pm.get_portfolio()
        
        if portfolio_df.empty:
            return []
        
        # Get current prices and calculate P/L with Level 2 details
        db = DatabaseManager(DB_PATH)
        
        results = []
        for _, position in portfolio_df.iterrows():
            ticker = position['ticker']
            
            # Get market data for ATR calculation
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT date, close, high, low, open, volume FROM stock_data WHERE ticker=? ORDER BY date DESC LIMIT 30",
                (ticker,)
            )
            market_data = cursor.fetchall()
            
            if not market_data:
                continue
            
            # Create DataFrame for ATR calculation
            df_market = pd.DataFrame(market_data, columns=['date', 'close', 'high', 'low', 'open', 'volume'])
            
            current_price = df_market.iloc[0]['close']
            current_open = df_market.iloc[0]['open']
            current_volume = df_market.iloc[0]['volume']
            
            # Calculate profit
            profit_pct = ((current_price - position['buy_price']) / position['buy_price']) * 100
            profit_amount = (current_price - position['buy_price']) * position['quantity']
            
            # Calculate ATR (Level 2)
            atr = pm.calculate_atr(df_market, period=14)
            
            # Calculate days held (Level 2)
            days_held = pm.calculate_days_held(position['purchase_date'])
            
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
            
            # Get total cost and commission from database
            total_cost = position.get('total_cost', position['buy_price'] * position['quantity'])
            commission_paid = position.get('commission_paid', 0)
            
            results.append({
                'ticker': ticker,
                'buy_price': position['buy_price'],
                'quantity': position['quantity'],
                'highest_seen': position['highest_seen'],
                'purchase_date': position['purchase_date'],
                'current_price': round(current_price, 2),
                'profit_pct': round(profit_pct, 2),
                'profit_amount': round(profit_amount, 2),
                'status': status,
                # Level 2 details
                'atr': round(atr, 2),
                'days_held': days_held,
                'rvol': round(rvol, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'trailing_stop_price': round(trailing_stop_price, 2),
                'stop_type': stop_type,
                'atr_distance': round(2 * atr, 2) if atr > 0 else 0,
                'is_zombie': is_zombie,
                'volume': int(current_volume),
                # Commission and cost details
                'total_cost': round(total_cost, 2),
                'commission_paid': round(commission_paid, 2)
            })
        
        db.close()
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return []

@app.post("/api/trade")
def add_trade(trade: Trade):
    """Add a new trade to portfolio with commission calculation"""
    try:
        pm = PortfolioManager(DB_PATH)
        
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
        pm = PortfolioManager(DB_PATH)
        db = DatabaseManager(DB_PATH)
        
        # Get current price if not provided
        current_price = request.current_price
        if not current_price:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT close FROM stock_data WHERE ticker=? ORDER BY date DESC LIMIT 1",
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
        pm = PortfolioManager(DB_PATH)
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
        db = DatabaseManager(DB_PATH)
        
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT date, volume FROM stock_data WHERE ticker=? ORDER BY date DESC LIMIT 20",
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

@app.delete("/api/trade/{ticker}")
def remove_trade(ticker: str):
    """Remove a position from portfolio"""
    try:
        pm = PortfolioManager(DB_PATH)
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
        pm = PortfolioManager(DB_PATH)
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
        pm = PortfolioManager(DB_PATH)
        stats = pm.get_portfolio_summary()
        return stats
    
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger-update")
async def trigger_manual_update():
    """Manually trigger data update (for testing)"""
    try:
        logger.info("🔄 Manual update triggered...")
        asyncio.create_task(scheduled_data_update())
        
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
